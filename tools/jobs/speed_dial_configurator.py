# Python
import io
import os
import csv
import sys
import time
import pprint
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


class SpeedDialConfigurator():
    _bw = None
    _process = None
    _speed_dials = None

    def __init__(self, process, speed_dials):
        self._process = process
        self._speed_dials = speed_dials
        self._bw = BroadWorks(url=self._process.platform.uri,
                              username=self._process.platform.username,
                              password=self._process.platform.password)
        self._bw.LoginRequest14sp4()

    def provider_check(self, provider_id):
        resp0 = self._bw.ServiceProviderGetRequest17sp1(provider_id)
        provider_info = resp0['data']
        print(provider_info)
        if 'isEnterprise' in provider_info and provider_info['isEnterprise'] != True:
            raise Exception('Provider Id is not an Enterprise')
        elif 'isEnterprise' not in provider_info:
            raise Exception('Provider Id is not an Enterprise')

    def groups(self, provider_id):
        resp0 = self._bw.GroupGetListInServiceProviderRequest(serviceProviderId=provider_id)
        return resp0['data']['groupTable']

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

    def process_group(self, provider_id, group_id, level=0):
        log = io.StringIO()
        summary = io.StringIO()

        # Get list of users
        log.write('{}UserGetListInGroupRequest(serviceProviderId={}, groupId={}) >> '.format('    '*level, provider_id, group_id)),
        resp1 = self._bw.UserGetListInGroupRequest(serviceProviderId=provider_id, groupId=group_id)
        log.write(self.parse_response(resp1, level))
        users = resp1['data']['userTable']

        # Add speed dials to all users
        for user in users:
            user_id = user['User Id']

            # Get User Speed Dials

            log.write('{}UserSpeedDial100GetListRequest17sp1(user_id={}) >> '.format('    '*(level+1), user_id)),
            resp2 = self._bw.UserSpeedDial100GetListRequest17sp1(user_id)
            log.write(self.parse_response(resp2, (level+1)))
            data = resp2['data']
            if 'speedDialEntry' in data:
                entries = {x['speedCode']: x for x in resp2['data']['speedDialEntry']}
            else:
                entries = {}

            # Build add/modify lists
            speed_dial_add_entries = [OrderedDict([('speedCode', e['code']), ('phoneNumber', e['destination_number']), ('description', e['description'])]) for e in self._speed_dials if e['code'] not in entries]
            speed_dial_mod_entries = [OrderedDict([('speedCode', e['code']), ('phoneNumber', e['destination_number']), ('description', e['description'])]) for e in self._speed_dials if e['code'] in entries]

            # Add
            if speed_dial_add_entries:
                log.write('{}UserSpeedDial100AddListRequest({}, speedDialEntry={{...}}) '.format('    '*(level+1), user_id))
                resp3 = self._bw.UserSpeedDial100AddListRequest(user_id, speedDialEntry=speed_dial_add_entries)
                log.write(self.parse_response(resp3, level))
                summary.write('"{}","{}","{}","Add: {}"\n'.format(provider_id, group_id, user_id, resp3['type']))

            # Modify
            if speed_dial_mod_entries:
                log.write('{}UserSpeedDial100ModifyListRequest({}, speedDialEntry={{...}}) '.format('    '*(level+1), user_id))
                resp4 = self._bw.UserSpeedDial100ModifyListRequest(user_id, speedDialEntry=speed_dial_mod_entries)
                log.write(self.parse_response(resp4, level))
                summary.write('"{}","{}","{}","Mod: {}"\n'.format(provider_id, group_id, user_id, resp4['type']))
                pass

        rval = {'log': log.getvalue(), 'summary': summary.getvalue()}
        log.close()
        summary.close()
        return rval


def speed_dial_configurator(process_id):
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

        # Retrieve Data

        # Retrieve Data
        provider_type = process.parameters.get('provider_type', None)
        provider_id = process.parameters.get('provider_id', None)
        group_id = process.parameters.get('group_id', None)
        speed_dials = process.parameters.get('data', None)
        sdc = SpeedDialConfigurator(process, speed_dials)

        # Initial content
        summary_html.write('<table class="table table-striped table-bordered table-hover">\n')
        summary_html.write('<tr>\n')
        summary_html.write('\t<th>Provider Id</th><th>Group Id</th><th>User Id</th><th>Result</th>\n')
        summary_html.write('</tr>\n')
        summary_html.write('<tbody>\n')
        summary_raw.write('"Provider Id","Group Id","User Id","Result"\n')

        # Determine what to do
        if provider_id and group_id:
            log_raw.write('Group {}::{}\n'.format(provider_id, group_id))
            data = sdc.process_group(provider_id=provider_id, group_id=group_id, level=1)
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
            sdc.provider_check(provider_id)
            groups = sdc.groups(provider_id)
            for group in groups:
                group_id = group['Group Id']
                log_raw.write('    Group {}::{}\n'.format(provider_id, group_id))
                data = sdc.process_group(provider_id=provider_id, group_id=group_id, level=1)
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
