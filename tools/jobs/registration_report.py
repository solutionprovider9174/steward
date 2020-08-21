# Python
import io
import os
import csv
import sys
import time
import requests
import datetime
import traceback
from collections import OrderedDict

# Django
from django.utils import timezone
from django.conf import settings

# Application
from tools.models import Process, ProcessContent

# Third Party
from lib.pyutil.util import Util
from lib.pybw.broadworks import BroadWorks, Nil
from lib.pypalladion.palladion import Palladion


class RegistrationReport:
    _palladion = None
    _pl_devices = None
    _bw = None
    _process = None

    def __init__(self, process):
        self._process = process
        self._palladion = Palladion(**settings.PLATFORMS['palladion'])
        self._pl_devices = { x['id']: x for x in self._palladion.devices() }
        requests.packages.urllib3.disable_warnings()
        self._bw = BroadWorks(url=self._process.platform.uri,
                              username=self._process.platform.username,
                              password=self._process.platform.password)
        self._bw.LoginRequest14sp4()

    def parse_response(self, response, level):
        content = io.StringIO()
        content.write('{}\n'.format(response['type']))
        if response['type'] == 'c:ErrorResponse':
            if 'summaryEnglish' in response['data'] and 'errorCode' in response['data']:
                content.write('{}[{}] {}\n'.format('    '*(level+1), response['data']['errorCode'], response['data']['summaryEnglish']))
            elif 'summaryEnglish' in response['data']:
                content.write('{}{}\n'.format('    '*level, response['data']['summaryEnglish']))
            elif 'summary' in response['data'] and 'errorCode' in response['data']:
                content.write('{}[{}] {}\n'.format('    '*(level+1), response['data']['errorCode'], response['data']['summary']))
            elif 'summary' in response['data']:
                content.write('{}{}\n'.format('    '*(level+1), response['data']['summary']))
        rval = content.getvalue()
        content.close()
        return rval

    def groups(self, provider_id):
        resp0 = self._bw.GroupGetListInServiceProviderRequest(serviceProviderId=provider_id)
        return resp0['data']['groupTable']

    def group_report(self, provider_id, group_id, level=0):
        log = io.StringIO()
        summary = io.StringIO()

        log.write('{}GroupAccessDeviceGetListRequest({}, {}) '.format('    '*level, provider_id, group_id))
        resp0 = self._bw.GroupAccessDeviceGetListRequest(provider_id, group_id)
        log.write(self.parse_response(resp0, level))
        devices = resp0['data']['accessDeviceTable']
        for device in devices:
            device_name = device['Device Name']
            device_type = device['Device Type']
            log.write('{}Device: {}::{}::{}\n'.format('    '*level, provider_id, group_id, device_name))
            log.write('{}GroupAccessDeviceGetUserListRequest({}, {}, {}) '.format('    '*(level+1), provider_id, group_id, device_name))
            resp1 = self._bw.GroupAccessDeviceGetUserListRequest(provider_id, group_id, device_name)
            log.write(self.parse_response(resp1, level))
            if 'deviceUserTable' in resp1['data'] and len(resp1['data']['deviceUserTable']) > 0:
                line_ports = sorted(resp1['data']['deviceUserTable'], key=lambda k: "None" if k['Order'] is None else k['Order'])
                for line_port in line_ports:
                    user_line_id = line_port['Line/Port'].split('@')[0]
                    log.write('{}{} :: '.format('    '*(level+2), user_line_id))
                    registrars = list()
                    registrations = sorted(self._palladion.registrations(user_line_id), key=lambda reg: reg['dev_id'])
                    user_agents = set()
                    for registration in registrations:
                        if 'usrdev' in registration:
                            user_agents.add(registration['usrdev'])
                        registrar_name = "???"
                        if registration['dev_id'] in self._pl_devices:
                            registrar_name = self._pl_devices[registration['dev_id']]['name']
                        registrars.append(registrar_name)
                    if len(registrars) > 0:
                        log.write('{}\n'.format('Registered'))
                        summary.write('"{}","{}","{}","{}","{}","{}","{}","{}"\n'.format(provider_id, group_id, device_name, device_type, user_line_id, 'Registered', ','.join(registrars), ','.join(user_agents)))
                    else:
                        log.write('{}\n'.format('Not Registered'))
                        summary.write('"{}","{}","{}","{}","{}","{}","{}","{}"\n'.format(provider_id, group_id, device_name, device_type, user_line_id, 'Not Registered', '', ''))

        return {'log': log.getvalue(), 'summary': summary.getvalue()}

def registration_report(process_id):
    process = Process.objects.get(id=process_id)

    # Summary Tab
    summary_content = ProcessContent.objects.create(process=process, tab='Summary', priority=1)
    dir_path = os.path.join(settings.PROTECTED_ROOT, 'process')
    filename_html = '{}_{}'.format(process.id, 'summary.html')
    pathname_html = os.path.join(dir_path, filename_html)
    filename_raw = '{}_{}'.format(process.id, 'summary.csv')
    pathname_raw = os.path.join(dir_path, filename_raw)
    if not os.path.isdir(dir_path):
        os.makedirs(dir_path)
    summary_html = open(pathname_html, "w")
    summary_content.html.name = os.path.join('process', filename_html)
    summary_raw = open(pathname_raw, "w")
    summary_content.raw.name = os.path.join('process', filename_raw)
    summary_content.save()

    # Log Tab
    log_content = ProcessContent.objects.create(process=process, tab='Log', priority=2)
    dir_path = os.path.join(settings.PROTECTED_ROOT, 'process')
    filename_raw = '{}_{}'.format(process.id, 'log.txt')
    pathname_raw = os.path.join(dir_path, filename_raw)
    if not os.path.isdir(dir_path):
        os.makedirs(dir_path)
    log_raw = open(pathname_raw, "w")
    log_content.raw.name = os.path.join('process', filename_raw)
    log_content.save()

    try:
        print("Process {}: {} -> {}".format(process_id, process.method, process.parameters))
        process.status = process.STATUS_RUNNING
        process.save(update_fields=['status'])

        rp = RegistrationReport(process=process)

        # Retrieve Data
        provider_type = process.parameters.get('provider_type', None)
        provider_id = process.parameters.get('provider_id', None)
        group_id = process.parameters.get('group_id', None)

        # Initial content
        summary_html.write('<table class="table table-striped table-bordered table-hover">\n')
        summary_html.write('<tr>\n')
        summary_html.write('\t<th>Provider Id</th><th>Group Id</th><th>Device Name</th><th>Device Type</th><th>Line/Port</th><th>Status</th><th>Proxy/Registrar</th><th>User Agents</th>\n')
        summary_html.write('</tr>\n')
        summary_html.write('<tbody>\n')
        summary_raw.write('"{}","{}","{}","{}","{}","{}","{}","{}"\n'.format('Provider Id', 'Group Id', 'Device Name', 'Device Type', 'Line/Port', 'Status', 'Proxy/Registrar', 'User Agents'))

        if provider_id and group_id:
            log_raw.write('Group {}::{}\n'.format(provider_id, group_id))
            data = rp.group_report(provider_id=provider_id, group_id=group_id, level=1)
            log_raw.write(data['log'])
            summary_raw.write(data['summary'])
            for row in csv.reader(data['summary'].split('\n')):
                if row:
                    summary_html.write('<tr>\n\t')
                    for d in row:
                        summary_html.write('<td>{}</td>'.format(d))
                    summary_html.write('\n</tr>\n')
        elif provider_id:
            log_raw.write('Provider {}\n'.format(provider_id))
            groups = rp.groups(provider_id)
            for group in groups:
                group_id = group['Group Id']
                log_raw.write('    Group {}::{}\n'.format(provider_id, group_id))
                data = rp.group_report(provider_id=provider_id, group_id=group_id, level=2)
                log_raw.write(data['log'])
                summary_raw.write(data['summary'])
                for row in csv.reader(data['summary'].split('\n')):
                    if row:
                        summary_html.write('<tr>\n\t')
                        for d in row:
                            summary_html.write('<td>{}</td>'.format(d))
                        summary_html.write('\n</tr>\n')

        # after things are finished
        # end html
        summary_html.write('</tbody>\n')
        summary_html.write('</table>\n')
        # save data
        process.status = process.STATUS_COMPLETED
        process.end_timestamp = timezone.now()
        process.save(update_fields=['status', 'end_timestamp'])
    except Exception:
        process.status = process.STATUS_ERROR
        process.end_timestamp = timezone.now()
        process.exception = traceback.format_exc()
        process.save(update_fields=['status', 'exception', 'end_timestamp'])

    # Cleanup
    log_raw.close()
    summary_html.close()
    summary_raw.close()
