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


class CallParkPickupConfigurator():
    _bw = None
    _process = None
    _park = False
    _retrieve = False

    def __init__(self, process, park, retrieve):
        self._process = process
        self._park = park
        self._retrieve = retrieve
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

    def configure_group(self, provider_id, group_id, level=0):
        log = io.StringIO()
        summary = io.StringIO()

        # Get list of pickup groups
        log.write('{}GroupCallPickupGetInstanceListRequest({}, {}) '.format('    '*level, provider_id, group_id))
        resp0 = self._bw.GroupCallPickupGetInstanceListRequest(provider_id, group_id)
        log.write(self.parse_response(resp0, level))
        if 'name' in resp0['data']:
            pickup_groups = resp0['data']['name']
        else:
            pickup_groups = list()

        # Get list of users who could be added to a Pickup Group
        log.write('{}GroupCallPickupGetAvailableUserListRequest({}, {}) '.format('    '*level, provider_id, group_id))
        resp1 = self._bw.GroupCallPickupGetAvailableUserListRequest(provider_id, group_id)
        log.write(self.parse_response(resp1, level))
        if 'userTable' in resp1['data']:
            available_users = [x['User Id'] for x in resp1['data']['userTable']]
        else:
            available_users = []

        if not pickup_groups:
            log.write("{}GroupCallPickupAddInstanceRequest({}, {}, 'Default', {{...}}) ".format('    '*level, provider_id, group_id))
            resp2 = self._bw.GroupCallPickupAddInstanceRequest(provider_id, group_id, 'Default', userId=available_users)
            log.write(self.parse_response(resp2, level))

        # Add tags to all user devices which can have a Pickup Group
        log.write('{}UserGetListInGroupRequest({}, {}) '.format('    '*(level+1), provider_id, group_id))
        resp3 = self._bw.UserGetListInGroupRequest(provider_id, group_id)
        log.write(self.parse_response(resp3, level))
        users = resp3['data'].get('userTable', [])
        for user in users:
            user_id = user['User Id']
            # Test if we can retrieve data about this user
            log.write('{}UserCallPickupGetRequest({}) '.format('    '*(level+1), group_id))
            resp4 = self._bw.UserCallPickupGetRequest(user_id)
            log.write('{}\n'.format(resp4['type']))
            if resp4['type'] == 'UserCallPickupGetResponse':
                # Get Line Ports
                devices = list()
                # primary device
                log.write("{}UserGetRequest19({}) ".format('    '*(level+2), user_id))
                resp2 = self._bw.UserGetRequest19(user_id)
                log.write(self.parse_response(resp2, (level+2)))
                user_info = resp2['data']
                if 'accessDeviceEndpoint' in user_info:
                    device_name = user_info['accessDeviceEndpoint']['accessDevice']['deviceName']
                    device_level = user_info['accessDeviceEndpoint']['accessDevice']['deviceLevel']
                    if device_level == 'Group':
                        resp5 = self._bw.GroupAccessDeviceGetRequest18sp1(provider_id, group_id, device_name)
                        device_type = resp5['data']['deviceType']
                    elif device_level == 'Service Provider':
                        resp5 = self._bw.ServiceProviderAccessDeviceGetRequest18sp1(provider_id, device_name)
                        device_type = resp5['data']['deviceType']
                    devices.append({'device_name': device_name, 'device_level': device_level, 'device_type': device_type})
                # shared call appearances
                log.write('{}UserSharedCallAppearanceGetRequest16sp2(userId={}) >> '.format('    '*(level+2), user_id)),
                resp3 = self._bw.UserSharedCallAppearanceGetRequest16sp2(userId=user_id)
                log.write(self.parse_response(resp3, (level+2)))
                appearances = resp3['data']['endpointTable']
                for appearance in appearances:
                    device_name = appearance['Device Name']
                    device_level = appearance['Device Level']
                    device_type = appearance['Device Type']
                    devices.append({'device_name': device_name, 'device_level': device_level, 'device_type': device_type})
                devices_unique = list()
                for device in devices:
                    if device not in devices_unique:
                        devices_unique.append(device)
                devices = devices_unique

                # add tags to devices?
                log.write("{}Park:     {}\n".format('    '*(level+3), self._park))
                log.write("{}Retrieve: {}\n".format('    '*(level+3), self._retrieve))
                tags = []
                if self._park:
                    tags += [
                        {'tag_name': '%SK5-Action%', 'tag_value': '!grppark'},
                        {'tag_name': '%SK5-Active%', 'tag_value': '1'},
                        {'tag_name': '%SK5-Enable%', 'tag_value': '1'},
                        {'tag_name': '%SK5-Label%',  'tag_value': 'Park'},
                    ]
                if self._retrieve:
                    tags += [
                        {'tag_name': '%SK6-Action%', 'tag_value': '!retrieve'},
                        {'tag_name': '%SK6-Enable%', 'tag_value': '1'},
                        {'tag_name': '%SK6-Idle%',   'tag_value': '1'},
                        {'tag_name': '%SK6-Label%',  'tag_value': 'Retrieve'},
                    ]
                for device in devices:
                    device_name = device['device_name']
                    log.write('{}Device: {}\n'.format('    '*(level+3), device_name))
                    log.write('{}GroupAccessDeviceCustomTagGetListRequest({}, {}, {}) '.format('    '*(level+4), provider_id, group_id, device_name))
                    resp4 = self._bw.GroupAccessDeviceCustomTagGetListRequest(provider_id, group_id, device_name)
                    log.write(self.parse_response(resp4, level))
                    if 'deviceCustomTagsTable' in resp4['data']:
                        device_tags = {x['Tag Name']: x['Tag Value'] for x in resp4['data']['deviceCustomTagsTable']}
                    else:
                        device_tags = dict()
                    if device['device_level'] == 'Group':
                        for tag in tags:
                            tag_name = tag['tag_name']
                            tag_value = tag['tag_value']
                            if tag_name in device_tags:
                                log.write('{}GroupAccessDeviceCustomTagModifyRequest(serviceProviderId={}, groupId={}, deviceName={}, tagName={}, tagValue={}) >> '.format('    '*(level+4), provider_id, group_id, device['device_name'], tag_name, tag_value)),
                                resp4 = self._bw.GroupAccessDeviceCustomTagModifyRequest(serviceProviderId=provider_id, groupId=group_id, deviceName=device['device_name'], tagName=tag_name, tagValue=tag_value)
                                log.write(self.parse_response(resp4, (level+4)))
                            else:
                                log.write('{}GroupAccessDeviceCustomTagAddRequest(serviceProviderId={}, groupId={}, deviceName={}, tagName={}, tagValue={}) >> '.format('    '*(level+4), provider_id, group_id, device['device_name'], tag_name, tag_value)),
                                resp4 = self._bw.GroupAccessDeviceCustomTagAddRequest(serviceProviderId=provider_id, groupId=group_id, deviceName=device['device_name'], tagName=tag_name, tagValue=tag_value)
                                log.write(self.parse_response(resp4, (level+4)))
                        log.write('{}GroupCPEConfigRebuildConfigFileRequest(serviceProviderId={}, groupId={}, deviceName={}, deviceType={}) >> '.format('    '*(level+4), provider_id, group_id, device['device_name'], device['device_type'])),
                        resp5 = self._bw.GroupCPEConfigRebuildConfigFileRequest(serviceProviderId=provider_id, groupId=group_id, deviceName=device['device_name'], deviceType=device['device_type'])
                        log.write(self.parse_response(resp5, (level+4)))
                    elif device['device_level'] == 'Provider':
                        for tag in tags:
                            tag_name = tag['tag_name']
                            tag_value = tag['tag_value']
                            if tag_name in device_tags:
                                log.write('{}ServiceProviderAccessDeviceCustomTagModifyRequest(serviceProviderId={}, deviceName={}, tagName={}, tagValue={}) >> '.format('    '*(level+4), provider_id, device['device_name'], tag_name, tag_value)),
                                resp4 = self._bw.ServiceProviderAccessDeviceCustomTagModifyRequest(serviceProviderId=provider_id, deviceName=device['device_name'], tagName=tag_name, tagValue=tag_value)
                                log.write(self.parse_response(resp4, (level+4)))
                            else:
                                log.write('{}ServiceProviderAccessDeviceCustomTagAddRequest(serviceProviderId={}, deviceName={}, tagName={}, tagValue={}) >> '.format('    '*(level+4), provider_id, device['device_name'], tag_name, tag_value)),
                                resp4 = self._bw.ServiceProviderAccessDeviceCustomTagAddRequest(serviceProviderId=provider_id, deviceName=device['device_name'], tagName=tag_name, tagValue=tag_value)
                                log.write(self.parse_response(resp4, (level+4)))
                        log.write('{}ServiceProviderCPEConfigRebuildDeviceConfigFileRequest(serviceProviderId={}, deviceName={}) >> '.format('    '*(level+4), provider_id, device['device_name'])),
                        resp5 = self._bw.ServiceProviderCPEConfigRebuildDeviceConfigFileRequest(serviceProviderId=provider_id, deviceName=device['device_name'])
                        log.write(self.parse_response(resp5, (level+4)))
                # write to summary file
                summary.write('"{}","{}","{}","{}"\n'.format(provider_id, group_id, user_id, 'Success'))

        rval = {'log': log.getvalue(), 'summary': summary.getvalue()}
        log.close()
        summary.close()
        return rval


def call_park_pickup_configurator(process_id):
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
        provider_type = process.parameters.get('provider_type', None)
        provider_id = process.parameters.get('provider_id', None)
        group_id = process.parameters.get('group_id', None)
        park = process.parameters.get('park') in ['True', 'true']
        retrieve = process.parameters.get('retrieve', 'False') in ['True', 'true']
        cpp = CallParkPickupConfigurator(process, park, retrieve)

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
            data = cpp.configure_group(provider_id=provider_id, group_id=group_id, level=1)
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
            cpp.provider_check(provider_id)
            groups = cpp.groups(provider_id)
            for group in groups:
                group_id = group['Group Id']
                log_raw.write('    Group {}::{}\n'.format(provider_id, group_id))
                data = cpp.configure_group(provider_id=provider_id, group_id=group_id, level=1)
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
