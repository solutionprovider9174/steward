# Python
from collections import OrderedDict
import csv
import datetime
import io
import os
import pprint
import re
import requests
import sys
import time
import traceback

# Django
from django.utils import timezone
from django.conf import settings

# Application
from tools.models import Process, ProcessContent

# Third Party
from lib.pyutil.util import Util
from lib.pybw.broadworks import BroadWorks, Nil


class DectConfigurator():
    _bw = None
    _process = None

    def __init__(self, process):
        self._process = process
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

    def get_lineports(self, provider_id, group_id, device_name):
        # Get line ports
        resp0 = self._bw.GroupAccessDeviceGetUserListRequest(provider_id, group_id, device_name)
        if 'deviceUserTable' in resp0['data']:
            return { x['Line/Port']: x for x in sorted(resp0['data']['deviceUserTable'], key=lambda k: k['Order']) }
        else:
            return {}

    def process(self, provider_id, group_id, device_name, handsets, level=0):
        log = io.StringIO()

        # Check that provider exists
        log.write('{}ServiceProviderGetRequest17sp1({}) >> '.format('    '*level, provider_id)),
        resp = self._bw.ServiceProviderGetRequest17sp1(provider_id)
        log.write(self.parse_response(resp, level))
        if resp['type'] == 'ServiceProviderGetResponse17sp1':
            provider_data = resp['data']
        else:
            log.write('ERROR: Service Provider "{}" could not be found :-(\n'.format(provider_id))
            rval = {'log': log.getvalue()}
            log.close()
            return rval
        # Check that group exists
        log.write('{}GroupGetRequest14sp7({}, {}) >> '.format('    '*level, provider_id, group_id)),
        resp = self._bw.GroupGetRequest14sp7(provider_id, group_id)
        log.write(self.parse_response(resp, level))
        if resp['type'] == 'GroupGetResponse14sp7':
            group_data = resp['data']
        else:
            log.write('ERROR: Group "{}" in Provider "{}" could not be found :-(\n'.format(group_id, provider_id))
            rval = {'log': log.getvalue()}
            log.close()
            return rval
        # Check that device exists
        log.write('{}GroupAccessDeviceGetRequest18sp1({}, {}, {}) >> '.format('    '*level, provider_id, group_id, device_name)),
        resp = self._bw.GroupAccessDeviceGetRequest18sp1(provider_id, group_id, device_name)
        log.write(self.parse_response(resp, level))
        if resp['type'] == 'GroupAccessDeviceGetResponse18sp1':
            group_data = resp['data']
        else:
            log.write('ERROR: Device "{}" in Group "{}" in Provider "{}" could not be found :-(\n'.format(device_name, group_id, provider_id))
            rval = {'log': log.getvalue()}
            log.close()
            return rval


        # Get device tags
        log.write('{}GroupAccessDeviceCustomTagGetListRequest({}, {}, {}) >> '.format('    '*level, provider_id, group_id, device_name)),
        resp1 = self._bw.GroupAccessDeviceCustomTagGetListRequest(provider_id, group_id, device_name)
        log.write(self.parse_response(resp1, level))
        if 'deviceCustomTagsTable' in resp1['data']:
            tags = {x['Tag Name']: x['Tag Value'] for x in resp1['data']['deviceCustomTagsTable']}
        else:
            tags = {}

        for name,value in tags.items():
            m = re.search(r'^%REG\d+TERMINATIONTYPE%$', name)
            if m:
                # delete tag
                log.write('{}GroupAccessDeviceCustomTagDeleteListRequest({}, {}, {}, {}) >> '.format('    '*level, provider_id, group_id, device_name, name)),
                resp = self._bw.GroupAccessDeviceCustomTagDeleteListRequest(provider_id, group_id, device_name, name)
                log.write(self.parse_response(resp, level))
                del(resp)
                continue
            m = re.search(r'^%HANDSET\d+OUTGOINGLINE%$', name)
            if m:
                # delete tag
                log.write('{}GroupAccessDeviceCustomTagDeleteListRequest({}, {}, {}, {}) >> '.format('    '*level, provider_id, group_id, device_name, name)),
                resp = self._bw.GroupAccessDeviceCustomTagDeleteListRequest(provider_id, group_id, device_name, name)
                log.write(self.parse_response(resp, level))
                del(resp)
                continue
            m = re.search(r'^%HANDSET\d+LINE\d+%$', name)
            if m:
                # delete tag
                log.write('{}GroupAccessDeviceCustomTagDeleteListRequest({}, {}, {}, {}) >> '.format('    '*level, provider_id, group_id, device_name, name)),
                resp = self._bw.GroupAccessDeviceCustomTagDeleteListRequest(provider_id, group_id, device_name, name)
                log.write(self.parse_response(resp, level))
                del(resp)
                continue
            m = re.search(r'^%HANDSET\d+LINE\d+_LINEPORT%$', name)
            if m:
                # delete tag
                log.write('{}GroupAccessDeviceCustomTagDeleteListRequest({}, {}, {}, {}) >> '.format('    '*level, provider_id, group_id, device_name, name)),
                resp = self._bw.GroupAccessDeviceCustomTagDeleteListRequest(provider_id, group_id, device_name, name)
                log.write(self.parse_response(resp, level))
                del(resp)
                continue
            m = re.search(r'^%HANDSET\d+LINE\d+_USERID%$', name)
            if m:
                # delete tag
                log.write('{}GroupAccessDeviceCustomTagDeleteListRequest({}, {}, {}, {}) >> '.format('    '*level, provider_id, group_id, device_name, name)),
                resp = self._bw.GroupAccessDeviceCustomTagDeleteListRequest(provider_id, group_id, device_name, name)
                log.write(self.parse_response(resp, level))
                del(resp)
                continue

        # Get device tags (again)
        log.write('{}GroupAccessDeviceCustomTagGetListRequest({}, {}, {}) >> '.format('    '*level, provider_id, group_id, device_name)),
        resp1 = self._bw.GroupAccessDeviceCustomTagGetListRequest(provider_id, group_id, device_name)
        log.write(self.parse_response(resp1, level))
        if 'deviceCustomTagsTable' in resp1['data']:
            tags = {x['Tag Name']: x['Tag Value'] for x in resp1['data']['deviceCustomTagsTable']}
        else:
            tags = {}

        # Add DECT ENABLED tag
        if '%DECTENABLED%' not in tags:
            log.write('{}GroupAccessDeviceCustomTagAddRequest({}, {}, {}, %DECTENABLED%, tagValue=1) >> '.format('    '*level, provider_id, group_id, device_name)),
            resp2 = self._bw.GroupAccessDeviceCustomTagAddRequest(provider_id, group_id, device_name, '%DECTENABLED%', tagValue='1')
            log.write(self.parse_response(resp2, level))
        elif tags.get('%DECTENABLED%', '0') != '1':
            log.write('{}GroupAccessDeviceCustomTagModifyRequest({}, {}, {}, %DECTENABLED%, tagValue=1) >> '.format('    '*level, provider_id, group_id, device_name)),
            resp2 = self._bw.GroupAccessDeviceCustomTagModifyRequest(provider_id, group_id, device_name, '%DECTENABLED%', tagValue='1')
            log.write(self.parse_response(resp2, level))

        # Get lineports
        lineports = self.get_lineports(provider_id, group_id, device_name)

        # Iterate all handsets...
        for item in handsets:
            if not item['lineport'] or item['lineport'] == '' or item['lineport'] not in lineports:
                # lineport doesn't exist or is empty, create a SCA!
                if item['lineport']:
                    lineport = item['lineport']
                else:
                    lineport = '{}_{}@telapexinc.com'.format(item['user_id'], Util.random_passcode(length=6, repeating_limit=6, sequential_limit=6))
                endpoint = OrderedDict()
                endpoint['accessDevice'] = OrderedDict()
                endpoint['accessDevice']['deviceLevel'] = 'Group'
                endpoint['accessDevice']['deviceName'] = device_name
                endpoint['linePort'] = lineport
                log.write('{}UserSharedCallAppearanceAddEndpointRequest14sp2({}, {{...}}, True, True, True) >> '.format('    '*level, item['user_id'])),
                resp4 = self._bw.UserSharedCallAppearanceAddEndpointRequest14sp2(item['user_id'], endpoint, True, True, True)
                log.write(self.parse_response(resp4, level))
                # update lineports
                lineports = self.get_lineports(provider_id, group_id, device_name)
                item['lineport'] = lineport

            lineport = lineports.get(item['lineport'])
            if lineport is None:
                log.write('ERROR: Could not determine Line/Port!')
                log.write('Likely a Shared Call Appearance could not be created')
                rval = {'log': log.getvalue()}
                log.close()
                return rval

            # Add handset line tags
            tag_name = '%REG{}TERMINATIONTYPE%'.format(lineport['Order'])
            if tag_name not in tags:
                # add
                log.write('{}GroupAccessDeviceCustomTagAddRequest({}, {}, {}, {}, tagValue=DECT) >> '.format('    '*level, provider_id, group_id, device_name, tag_name)),
                resp5 = self._bw.GroupAccessDeviceCustomTagAddRequest(provider_id, group_id, device_name, tag_name, tagValue='DECT')
                log.write(self.parse_response(resp5, level))
            elif tags[tag_name] != 'DECT':
                # modify
                log.write('{}GroupAccessDeviceCustomTagModifyRequest({}, {}, {}, {}, tagValue=DECT) >> '.format('    '*level, provider_id, group_id, device_name, tag_name)),
                resp5 = self._bw.GroupAccessDeviceCustomTagModifyRequest(provider_id, group_id, device_name, tag_name, tagValue='DECT')
                log.write(self.parse_response(resp5, level))
            tag_name = '%HANDSET{}OUTGOINGLINE%'.format(item['handset'])
            if tag_name not in tags:
                # add
                log.write('{}GroupAccessDeviceCustomTagAddRequest({}, {}, {}, {}, tagValue=1) >> '.format('    '*level, provider_id, group_id, device_name, tag_name)),
                resp6 = self._bw.GroupAccessDeviceCustomTagAddRequest(provider_id, group_id, device_name, tag_name, tagValue='1')
                log.write(self.parse_response(resp6, level))
            elif tags[tag_name] != '1':
                # modify
                log.write('{}GroupAccessDeviceCustomTagModifyRequest({}, {}, {}, {}, tagValue=1) >> '.format('    '*level, provider_id, group_id, device_name, tag_name)),
                resp6 = self._bw.GroupAccessDeviceCustomTagModifyRequest(provider_id, group_id, device_name, tag_name, tagValue='1')
                log.write(self.parse_response(resp6, level))
            tag_name = '%HANDSET{}LINE{}%'.format(item['handset'], item['line'])
            if tag_name not in tags:
                # add
                log.write('{}GroupAccessDeviceCustomTagAddRequest({}, {}, {}, {}, tagValue={}) >> '.format('    '*level, provider_id, group_id, device_name, tag_name, lineport['Order'])),
                resp7 = self._bw.GroupAccessDeviceCustomTagAddRequest(provider_id, group_id, device_name, tag_name, tagValue=lineport['Order'])
                log.write(self.parse_response(resp7, level))
            elif tags[tag_name] != lineport['Order']:
                # modify
                log.write('{}GroupAccessDeviceCustomTagModifyRequest({}, {}, {}, {}, tagValue={}) >> '.format('    '*level, provider_id, group_id, device_name, tag_name, lineport['Order'])),
                resp7 = self._bw.GroupAccessDeviceCustomTagModifyRequest(provider_id, group_id, device_name, tag_name, tagValue=lineport['Order'])
                log.write(self.parse_response(resp7, level))
            tag_name = '%HANDSET{}LINE{}_LINEPORT%'.format(item['handset'], item['line'])
            if tag_name not in tags:
                # add
                log.write('{}GroupAccessDeviceCustomTagAddRequest({}, {}, {}, {}, tagValue={}) >> '.format('    '*level, provider_id, group_id, device_name, tag_name, item['lineport'])),
                resp7 = self._bw.GroupAccessDeviceCustomTagAddRequest(provider_id, group_id, device_name, tag_name, tagValue=item['lineport'])
                log.write(self.parse_response(resp7, level))
            elif tags[tag_name] != item['lineport']:
                # modify
                log.write('{}GroupAccessDeviceCustomTagModifyRequest({}, {}, {}, {}, tagValue={}) >> '.format('    '*level, provider_id, group_id, device_name, tag_name, item['lineport'])),
                resp7 = self._bw.GroupAccessDeviceCustomTagModifyRequest(provider_id, group_id, device_name, tag_name, tagValue=item['lineport'])
                log.write(self.parse_response(resp7, level))
            tag_name = '%HANDSET{}LINE{}_USERID%'.format(item['handset'], item['line'])
            if tag_name not in tags:
                # add
                log.write('{}GroupAccessDeviceCustomTagAddRequest({}, {}, {}, {}, tagValue={}) >> '.format('    '*level, provider_id, group_id, device_name, tag_name, item['user_id'])),
                resp8 = self._bw.GroupAccessDeviceCustomTagAddRequest(provider_id, group_id, device_name, tag_name, tagValue=item['user_id'])
                log.write(self.parse_response(resp8, level))
            elif tags[tag_name] != item['user_id']:
                # modify
                log.write('{}GroupAccessDeviceCustomTagModifyRequest({}, {}, {}, {}, tagValue={}) >> '.format('    '*level, provider_id, group_id, device_name, tag_name, item['user_id'])),
                resp8 = self._bw.GroupAccessDeviceCustomTagModifyRequest(provider_id, group_id, device_name, tag_name, tagValue=item['user_id'])
                log.write(self.parse_response(resp8, level))

        # Rebuild device files and reboot device
        log.write('{}GroupCPEConfigRebuildDeviceConfigFileRequest({}, {}, {}) '.format('    '*(level+1), provider_id, group_id, device_name))
        resp9 = self._bw.GroupCPEConfigRebuildDeviceConfigFileRequest(serviceProviderId=provider_id, groupId=group_id, deviceName=device_name)
        log.write(self.parse_response(resp9, level))
        log.write('{}GroupAccessDeviceResetRequest({}, {}, {}) '.format('    '*(level+1), provider_id, group_id, device_name))
        resp10 = self._bw.GroupAccessDeviceResetRequest(serviceProviderId=provider_id, groupId=group_id, deviceName=device_name)
        log.write(self.parse_response(resp10, level))

        rval = {'log': log.getvalue()}
        log.close()
        return rval


def dect_configurator(process_id):
    process = Process.objects.get(id=process_id)

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
        provider_id = process.parameters.get('provider_id', None)
        group_id = process.parameters.get('group_id', None)
        device_name = process.parameters.get('device_name', None)
        handsets = process.parameters.get('data', None)
        dc = DectConfigurator(process)

        # Run!
        log_raw.write('Provider {}\n'.format(provider_id))
        data = dc.process(provider_id, group_id, device_name, handsets)
        log_raw.write(data['log'])

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
