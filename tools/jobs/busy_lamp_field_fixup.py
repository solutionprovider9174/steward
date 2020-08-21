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


class BusyLampFieldFixup():
    def __init__(self, process):
        self._process = process
        self._bw = BroadWorks(url=self._process.platform.uri,
                              username=self._process.platform.username,
                              password=self._process.platform.password)
        self._bw.LoginRequest14sp4()

    def run(self):
        log = io.StringIO()
        summary = io.StringIO()

        # parameters
        provider_id = self._process.parameters.get('provider_id', None)
        group_id = self._process.parameters.get('group_id', None)
        # provider check
        if not provider_id:
            raise RuntimeException("Provider Id not provided")
        # get groups
        if group_id:
            groups = [group_id]
        else:
            groups = self._get_group_ids(provider_id)

        # process groups
        for _group_id in groups:
            log.write("Provider {} Group {}\n".format(provider_id, _group_id))
            logs = self._run_group(provider_id, _group_id)
            log.write(logs['log'])
            summary.write(logs['summary'])

        rval = {'log': log.getvalue(), 'summary': summary.getvalue()}
        log.close()
        summary.close()
        return rval

    def _run_group(self, provider_id, group_id):
        log = io.StringIO()
        summary = io.StringIO()
        level = 0

        # Get users
        log.write('{}UserGetListInGroupRequest({}, {}) '.format('    '*(level+1), provider_id, group_id))
        resp1 = self._bw.UserGetListInGroupRequest(provider_id, group_id)
        log.write(self.parse_response(resp1, level))
        users = resp1['data'].get('userTable', [])
        for user in users:
            user_id = user['User Id']
            log.write("{}User {}\n".format('    '*(level+2), user_id))
            logs = self._run_user(provider_id, group_id, user_id)
            log.write(logs['log'])
            summary.write(logs['summary'])

        rval = {'log': log.getvalue(), 'summary': summary.getvalue()}
        log.close()
        summary.close()
        return rval

    def _run_user(self, provider_id, group_id, user_id):
        log = io.StringIO()
        summary = io.StringIO()
        level = 2

        # Check BLF settings
        log.write('{}UserBusyLampFieldGetRequest16sp2({}) '.format('    '*(level+1), user_id))
        resp1 = self._bw.UserBusyLampFieldGetRequest16sp2(user_id)
        log.write(self.parse_response(resp1, level))

        blf_data = resp1['data']
        blf_list_uri = blf_data.get('listURI')
        blf_monitored_users = blf_data.get('monitoredUserTable')
        if blf_list_uri and not blf_monitored_users:
            log.write('{}User Id {}, matches criteria! listUri: {} monitoredUserCount: {}\n'.format(
                '    '*(level+1),
                user_id,
                blf_list_uri,
                len(blf_monitored_users)))
            # Clear User
            logs = self._clear_user_blf_uri(provider_id, group_id, user_id)
            log.write(logs['log'])
            summary.write(logs['summary'])
        else:
            summary.write('"{}","{}","{}","{}"\n'.format(provider_id, group_id, user_id, 'Ok'))

        rval = {'log': log.getvalue(), 'summary': summary.getvalue()}
        log.close()
        return rval

    def _clear_user_blf_uri(self, provider_id, group_id, user_id):
        log = io.StringIO()
        summary = io.StringIO()
        level = 2

        # Clear BLF List URI
        log.write('{}UserBusyLampFieldModifyRequest({}) '.format('    '*(level+1), user_id))
        resp1 = self._bw.UserBusyLampFieldModifyRequest(user_id, listURI=Nil())
        log.write(self.parse_response(resp1, level))
        if resp1['type'] == 'c:ErrorResponse':
            # Could not clear List URI
            summary.write('"{}","{}","{}","{}"\n'.format(
                provider_id,
                group_id,
                user_id,
                'ERROR: Could not clear listURI'))
        else:
            # Could not clear List URI
            summary.write('"{}","{}","{}","{}"\n'.format(
                provider_id,
                group_id,
                user_id,
                'Success: Cleared'))

        rval = {'log': log.getvalue(), 'summary': summary.getvalue()}
        log.close()
        summary.close()
        return rval

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

    def _get_group_ids(self, provider_id):
        resp0 = self._bw.GroupGetListInServiceProviderRequest(serviceProviderId=provider_id)
        return [group['Group Id'] for group in resp0['data']['groupTable']]


def blf_fixup(process_id):
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

        # Initial Summary Tab content
        summary_html.write('<table class="table table-striped table-bordered table-hover">\n')
        summary_html.write('<tr>\n')
        summary_html.write('\t<th>Provider Id</th><th>Group Id</th><th>User Id</th><th>Result</th>\n')
        summary_html.write('</tr>\n')
        summary_html.write('<tbody>\n')
        summary_raw.write('"Provider Id","Group Id","User Id","Result"\n')

        # Run Process
        blf_fixup = BusyLampFieldFixup(process)
        data = blf_fixup.run()

        # Write data
        log_raw.write(data['log'])
        summary_raw.write(data['summary'])
        for row in csv.reader(data['summary'].split('\n')):
            if row:
                summary_html.write('<tr>\n\t')
                for cell in row:
                    summary_html.write('<td>{}</td>'.format(cell))
                summary_html.write('\n</tr>\n')

        # Ending Summary Tab content
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
