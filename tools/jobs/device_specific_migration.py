# Python
import io
import os
import csv
import sys
import time
import base64
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


class BroadWorksDeviceMigration:
    _bw = None
    _content = io.StringIO()

    def __init__(self, process):
        self._process = process
        self._bw = BroadWorks(url=self._process.platform.uri,
                              username=self._process.platform.username,
                              password=self._process.platform.password)
        self._bw.LoginRequest14sp4()

    @staticmethod
    def has_primary_line_port(device_user_table):
        for line_port in device_user_table:
            if line_port['Primary Line/Port'] == 'true':
                return True
        return False

    @staticmethod
    def get_first_primary_line_port(line_ports):
        for line_port in line_ports:
            if line_port['Endpoint Type'] == 'Primary':
                return line_port
        return None

    def logout(self):
        self._bw.LogoutRequest()

    def parse_response(self, response, level):
        content = io.StringIO()
        content.write('{}\n'.format(response['type']))
        if response['type'] == 'c:ErrorResponse':
            if 'summaryEnglish' in response['data'] and 'errorCode' in response['data']:
                content.write('        {}[{}] {}\n'.format('    '*level, response['data']['errorCode'], response['data']['summaryEnglish']))
            elif 'summaryEnglish' in response['data']:
                content.write('        {}{}\n'.format('    '*level, response['data']['summaryEnglish']))
            elif 'summary' in response['data'] and 'errorCode' in response['data']:
                content.write('        {}[{}] {}\n'.format('    '*level, response['data']['errorCode'], response['data']['summary']))
            elif 'summary' in response['data']:
                content.write('        {}{}\n'.format('    '*level, response['data']['summary']))
        rval = content.getvalue()
        content.close()
        return rval

    def provider_check(self, provider_id, enterprise=False):
        if enterprise:
            resp0 = self._bw.ServiceProviderGetRequest17sp1(provider_id)
            provider_info = resp0['data']
            if 'isEnterprise' in provider_info and provider_info['isEnterprise'] != True:
                raise Exception('Provider Id is not an Enterprise')
            elif 'isEnterprise' not in provider_info:
                raise Exception('Provider Id is not an Enterprise')

    def groups(self, provider_id):
        resp0 = self._bw.GroupGetListInServiceProviderRequest(serviceProviderId=provider_id)
        return resp0['data']['groupTable']

    def migrate_group(self, provider_id, group_id, **kwargs):
        log = io.StringIO()
        summary = io.StringIO()
        level = kwargs.get('level', 0)
        log.write("{}Migrating Group {}::{}\n".format('    '*level, provider_id, group_id))

        # get devices
        log.write('    {}Devices\n'.format('    '*level))
        log.write('    {}GroupAccessDeviceGetListRequest({}, {}) '.format('    '*(level+1), provider_id, group_id))
        resp3 = self._bw.GroupAccessDeviceGetListRequest(provider_id, group_id)
        log.write(self.parse_response(resp3, level))
        devices = resp3['data']['accessDeviceTable']
        for device in devices:
            device_name = device['Device Name']
            device_type = device['Device Type']
            if device_type == 'Polycom':
                log.write('    {}Device {}::{}::{})\n'.format('    '*(level+1), provider_id, group_id, device_name))
                log.write('    {}GroupAccessDeviceGetUserListRequest({}, {}, {}) '.format('    '*(level+2), provider_id, group_id, device_name))
                resp4 = self._bw.GroupAccessDeviceGetUserListRequest(provider_id, group_id, device_name)
                log.write(self.parse_response(resp4, level))
                line_ports = sorted(resp4['data']['deviceUserTable'], key=lambda k: k['Order'])
                if len(line_ports):
                    rdata = self.migrate_polycom_generic(provider_id=provider_id, group_id=group_id, device_name=device['Device Name'], device_type=device_type, line_ports=line_ports, level=(level+3))
                    log.write(rdata['log'])
                    summary.write(rdata['summary'])
            else:
                summary.write('"{}","{}","{}","{}","{}","{}","{}"\n'.format(provider_id, group_id, device_type, device_name, '', '', 'Pass'))
        return {'log': log.getvalue(), 'summary': summary.getvalue()}

    def migrate_polycom_generic(self, provider_id, group_id, device_name, device_type, **kwargs):
        log = io.StringIO()
        summary = io.StringIO()
        level = kwargs.get('level', 0)
        log.write('{}Migrate Polycom Generic: {}::{}::{} ({})\n'.format('    '*level, provider_id, group_id, device_name, device_type))
        # Determine Device Type & Info
        if provider_id and group_id and device_name:
            log.write('{}GroupAccessDeviceGetUserListRequest({}, {}, {}) '.format('    '*(level+1), provider_id, group_id, device_name))
            resp0 = self._bw.GroupAccessDeviceGetUserListRequest(provider_id, group_id, device_name)
            log.write(self.parse_response(resp0, level))
            users = resp0['data']['deviceUserTable']
        elif provider_id and device_name:
            log.write('{}ServiceProviderAccessDeviceGetUserListRequest({}, {}) '.format('    '*(level+1), provider_id, device_name))
            resp1 = self._bw.ServiceProviderAccessDeviceGetUserListRequest(provider_id, device_name)
            log.write(self.parse_response(resp1, level))
            users = resp1['data']['deviceUserTable']
        else:
            log.write('{}Could not get device user list for {}:{}:{}, not enough data\n'.format('    '*(level+1), provider_id, group_id, device_name))
            summary.write('"{}","{}","{}","{}","{}","{}","{}"\n'.format(provider_id, group_id, device_type, device_name, '', '', 'Could not get device user list'))
            return {'log': log.getvalue(), 'summary': summary.getvalue()}
        device_user_agent = None
        device_registered = False
        device_uri = None
        for user in users:
            user_id = user['User Id']
            log.write('{}UserGetRegistrationListRequest({}) '.format('    '*(level+1), user_id))
            resp2 = self._bw.UserGetRegistrationListRequest(user_id)
            log.write(self.parse_response(resp2, level))
            registrations = resp2['data']['registrationTable']
            for reg in registrations:
                if reg['Device Name'] == device_name:
                    device_user_agent = reg['User Agent']
                    device_registered = True
                    device_uri = reg['URI']
                    break
            else:
                continue
            break

        device_type_2 = None
        if device_user_agent is None:
            log.write('{}Could not determine device type for {}:{}:{}, no User Agent present (not registered)\n'.format('    '*(level+1), provider_id, group_id, device_name))
            summary.write('"{}","{}","{}","{}","{}","{}","{}"\n'.format(provider_id, group_id, device_type, device_name, '', '', 'Could not determine device type'))
            return {'log': log.getvalue(), 'summary': summary.getvalue()}
        elif 'PolycomVVX-VVX_300' in device_user_agent:
            device_suffix = 'VVX300'
            device_type_2 = 'Polycom_VVX300'
        elif 'PolycomVVX-VVX_310' in device_user_agent:
            device_suffix = 'VVX310'
            device_type_2 = 'Polycom_VVX300'
        elif 'PolycomVVX-VVX_400' in device_user_agent:
            device_suffix = 'VVX400'
            device_type_2 = 'Polycom_VVX400'
        elif 'PolycomVVX-VVX_410' in device_user_agent:
            device_suffix = 'VVX410'
            device_type_2 = 'Polycom_VVX400'
        elif 'PolycomVVX-VVX_500' in device_user_agent:
            device_suffix = 'VVX500'
            device_type_2 = 'Polycom_VVX500'
        elif 'PolycomVVX-VVX_600' in device_user_agent:
            device_suffix = 'VVX600'
            device_type_2 = 'Polycom_VVX600'
        elif 'PolycomSoundPointIP-SPIP_335' in device_user_agent:
            device_suffix = 'IP335'
            device_type_2 = 'Polycom_IP335'
        elif 'PolycomSoundPointIP-SPIP_450' in device_user_agent:
            device_suffix = 'IP450'
            device_type_2 = 'Polycom_IP450'
        elif 'PolycomSoundPointIP-SPIP_550' in device_user_agent:
            device_suffix = 'IP550'
            device_type_2 = 'Polycom_IP550'
        elif 'PolycomSoundPointIP-SPIP_560' in device_user_agent:
            device_suffix = 'IP560'
            device_type_2 = 'Polycom_IP550'
        elif 'PolycomSoundPointIP-SPIP_650' in device_user_agent:
            device_suffix = 'IP650'
            device_type_2 = 'Polycom_IP650'
        elif 'PolycomSountStationIP-SSIP_4000' in device_user_agent:
            device_suffix = 'SSIP_4000'
            device_type_2 = 'Polycom-conf'
        elif 'PolycomSountStationIP-SSIP_5000' in device_user_agent:
            device_suffix = 'SSIP_5000'
            device_type_2 = 'Polycom-conf'
        elif 'PolycomSountStationIP-SSIP_6000' in device_user_agent:
            device_suffix = 'SSIP_6000'
            device_type_2 = 'Polycom-conf'
        else:
            log.write('{}Could not determine device type for {}:{}:{} with UserAgent of {}\n'.format('    '*(level+1), provider_id, group_id, device_name, device_user_agent))
            summary.write('"{}","{}","{}","{}","{}","{}","{}"\n'.format(provider_id, group_id, device_type, device_name, '', '', 'Could not determine device type'))
            return {'log': log.getvalue(), 'summary': summary.getvalue()}

        # Retrieve Device Info
        if provider_id and group_id and device_name:
            log.write('{}GroupAccessDeviceGetRequest18sp1({}, {}, {}) '.format('    '*(level+1), provider_id, group_id, device_name))
            resp0 = self._bw.GroupAccessDeviceGetRequest18sp1(provider_id, group_id, device_name)
            log.write(self.parse_response(resp0, level))
            device_info = resp0['data']
        elif provider_id and device_name:
            log.write('{}ServiceProviderAccessDeviceGetRequest18sp1({}, {}) '.format('    '*(level+1), provider_id, device_name))
            resp1 = self._bw.ServiceProviderAccessDeviceGetRequest18sp1(provider_id, device_name)
            log.write(self.parse_response(resp1, level))
            device_info = resp1['data']
        else:
            log.write('{}Could not determine device type for {}:{}:{}, not enough data\n'.format('    '*(level+1), provider_id, group_id, device_name))
            summary.write('"{}","{}","{}","{}","{}","{}","{}"\n'.format(provider_id, group_id, device_type, device_name, '', '', 'Could not retrieve device details'))
            return {'log': log.getvalue(), 'summary': summary.getvalue()}

        # New device info
        device_name_2 = '{}_{}'.format(device_name, device_suffix)
        device_username_2 = device_info['userName']
        device_password_2 = '8675309'

        # Build Configuration Files
        redirect_file_contents = '<change device.set="1" device.dhcp.bootSrvUseOpt.set="1" device.dhcp.bootSrvUseOpt="Static" device.prov.user.set="1" device.prov.user="{username}" device.prov.password.set="1" device.prov.password="{password}" device.prov.serverType.set="1" device.prov.serverType="HTTP" device.prov.serverName.set="1" device.prov.serverName="bwdms.cspirefiber.com/dms/PolycomVVX" />'.format(username=device_username_2, password=device_password_2)
        custom_redirect_file_base64 = base64.b64encode(redirect_file_contents.encode('utf-8')).decode('utf-8')


        # Set existing device's primary line/port (if necessary)
        if 'line_ports' in kwargs:
            line_ports = kwargs['line_ports']
        else:
            log.write('{}GroupAccessDeviceGetUserListRequest({}, {}, {}) '.format('    '*(level+1), provider_id, group_id, device_name))
            resp0 = self._bw.GroupAccessDeviceGetUserListRequest(provider_id, group_id, device_name)
            log.write(self.parse_response(resp0, level))
            line_ports = sorted(resp0['data']['deviceUserTable'], key=lambda k: k['Order'])
        if len(line_ports) > 0 and not BroadWorksDeviceMigration.has_primary_line_port(line_ports):
            line_port = BroadWorksDeviceMigration.get_first_primary_line_port(line_ports)
            if line_port is not None:
                log.write('{}GroupAccessDeviceModifyUserRequest({}, {}, {}, {}, isPrimaryLinePort={}) '.format('    '*(level+1), provider_id, group_id, device_name, line_port['Line/Port'], True))
                resp1 = self._bw.GroupAccessDeviceModifyUserRequest(serviceProviderId=provider_id, groupId=group_id, deviceName=device_name, linePort=line_port['Line/Port'], isPrimaryLinePort=True)
                log.write(self.parse_response(resp1, level))

        # Create new device
        log.write('{}GroupAccessDeviceAddRequest14({}, {}, {}, {}, {}, {}) '.format('    '*(level+1), provider_id, group_id, device_name_2, device_type_2, device_username_2, device_password_2))
        resp1 = self._bw.GroupAccessDeviceAddRequest14(provider_id, group_id, device_name_2, device_type_2, username=device_username_2, password=device_password_2)
        log.write(self.parse_response(resp1, level))
        if resp1['type'] == 'c:ErrorResponse':
            # could not build device, ruh roh!
            summary.write('"{}","{}","{}","{}","{}","{}","{}"\n'.format(provider_id, group_id, device_type, device_name, device_type_2, device_name_2, 'ERROR: Could not add new device'))
            return {'log': log.getvalue(), 'summary': summary.getvalue()}

        # Move device tags to new device
        log.write('{}GroupAccessDeviceCustomTagGetListRequest({}, {}, {}) '.format('    '*(level+1), provider_id, group_id, device_name))
        resp2 = self._bw.GroupAccessDeviceCustomTagGetListRequest(provider_id, group_id, device_name)
        log.write(self.parse_response(resp2, level))
        device_tags = resp2['data']['deviceCustomTagsTable']
        for tag in device_tags:
            if tag['Tag Name'] not in ['%APP_VERSION%', '%APP_VERSION_VVX-400%', '%APP_VERSION_VVX-500%', '%APP_VERSION_VVX-600%']:
                log.write('{}GroupAccessDeviceCustomTagAddRequest({}, {}, {}, {}, {}) '.format('    '*(level+1), provider_id, group_id, device_name_2, tag['Tag Name'], tag['Tag Value']))
                resp3 = self._bw.GroupAccessDeviceCustomTagAddRequest(provider_id, group_id, device_name_2, tag['Tag Name'], tag['Tag Value'])
                log.write(self.parse_response(resp3, level))

        # Send existing device a new config file to redirect to the new device provisioning url + credentials
        log.write('{}GroupAccessDeviceFileModifyRequest14sp8({}, {}, {}, {}, {}, {}) '.format('    '*(level+1), provider_id, group_id, device_name, 'phone%BWDEVICEID%.cfg', 'Custom', '{...}'))
        resp4 = self._bw.GroupAccessDeviceFileModifyRequest14sp8(serviceProviderId=provider_id, groupId=group_id, deviceName=device_name, fileFormat='phone%BWDEVICEID%.cfg', fileSource='Custom', uploadFile={'fileContent': custom_redirect_file_base64})
        log.write(self.parse_response(resp4, level))
        log.write('{}GroupCPEConfigRebuildDeviceConfigFileRequest({}, {}, {}) '.format('    '*(level+1), provider_id, group_id, device_name))
        resp5 = self._bw.GroupCPEConfigRebuildDeviceConfigFileRequest(serviceProviderId=provider_id, groupId=group_id, deviceName=device_name)
        log.write(self.parse_response(resp5, level))
        log.write('{}GroupAccessDeviceResetRequest({}, {}, {}) '.format('    '*(level+1), provider_id, group_id, device_name))
        resp6 = self._bw.GroupAccessDeviceResetRequest(serviceProviderId=provider_id, groupId=group_id, deviceName=device_name)
        log.write(self.parse_response(resp6, level))

        # Move line/ports from old to new device
        for line_port in line_ports:
            if line_port['Endpoint Type'] == 'Primary':
                # Remove Primary Line/Port from previous device
                log.write('{}UserModifyRequest17sp4({}, endpoint={}) '.format('    '*(level+1), line_port['User Id'], 'Nil()'))
                resp7 = self._bw.UserModifyRequest17sp4(userId=line_port['User Id'], endpoint=Nil())
                log.write(self.parse_response(resp7, level))
                # Add Primary Line/Port to new device
                access_device_endpoint = OrderedDict()
                access_device_endpoint['accessDevice'] = OrderedDict()
                access_device_endpoint['accessDevice']['deviceLevel'] = 'Group'
                access_device_endpoint['accessDevice']['deviceName'] = device_name_2
                access_device_endpoint['linePort'] = line_port['Line/Port']
                log.write('{}UserModifyRequest17sp4({}, endpoint={}) '.format('    '*(level+1), line_port['User Id'], '{...}'))
                resp8 = self._bw.UserModifyRequest17sp4(userId=line_port['User Id'], endpoint={'accessDeviceEndpoint': access_device_endpoint})
                log.write(self.parse_response(resp8, level))
            elif line_port['Endpoint Type'] == 'Shared Call Appearance':
                # Remove SCA from previous device
                access_device_endpoint = OrderedDict()
                access_device_endpoint['accessDevice'] = OrderedDict()
                access_device_endpoint['accessDevice']['deviceLevel'] = 'Group'
                access_device_endpoint['accessDevice']['deviceName'] = device_name
                access_device_endpoint['linePort'] = line_port['Line/Port']
                log.write('{}UserSharedCallAppearanceDeleteEndpointListRequest14({}, {}) '.format('    '*(level+1), line_port['User Id'], '{...}'))
                resp9 = self._bw.UserSharedCallAppearanceDeleteEndpointListRequest14(line_port['User Id'], access_device_endpoint)
                log.write(self.parse_response(resp9, level))
                # Add SCA to new device
                access_device_endpoint = OrderedDict()
                access_device_endpoint['accessDevice'] = OrderedDict()
                access_device_endpoint['accessDevice']['deviceLevel'] = 'Group'
                access_device_endpoint['accessDevice']['deviceName'] = device_name_2
                access_device_endpoint['linePort'] = line_port['Line/Port']
                log.write('{}UserSharedCallAppearanceAddEndpointRequest14sp2({}, {}, isActive=True, allowOrigination=True, allowTermination=True) '.format('    '*(level+1), line_port['User Id'], '{...}'))
                resp10 = self._bw.UserSharedCallAppearanceAddEndpointRequest14sp2(line_port['User Id'], access_device_endpoint, isActive=True, allowOrigination=True, allowTermination=True)
                log.write(self.parse_response(resp10, level))
            else:
                log.write('unknown line_port endpoint type :-(\n')

        # Set new device's primary line/port (if necessary)
        log.write('{}GroupAccessDeviceGetUserListRequest({}, {}, {}) '.format('    '*(level+1), provider_id, group_id, device_name_2))
        resp11 = self._bw.GroupAccessDeviceGetUserListRequest(provider_id, group_id, device_name_2)
        log.write(self.parse_response(resp11, level))
        line_ports = sorted(resp11['data']['deviceUserTable'], key=lambda k: k['Order'])
        if len(line_ports) > 0 and not BroadWorksDeviceMigration.has_primary_line_port(line_ports):
            line_port = BroadWorksDeviceMigration.get_first_primary_line_port(line_ports)
            if line_port is not None:
                log.write('{}GroupAccessDeviceModifyUserRequest({}, {}, {}, {}, isPrimaryLinePort=True) '.format('    '*(level+1), provider_id, group_id, device_name_2, line_port['Line/Port']))
                resp11 = self._bw.GroupAccessDeviceModifyUserRequest(serviceProviderId=provider_id, groupId=group_id, deviceName=device_name_2, linePort=line_port['Line/Port'], isPrimaryLinePort=True)
                log.write(self.parse_response(resp11, level))

        # Success!
        log.write('{}Migrated Device {}::{}::{} with UserAgent of {}\n'.format('    '*(level+1), provider_id, group_id, device_name, device_info['version']))
        summary.write('"{}","{}","{}","{}","{}","{}","{}"\n'.format(provider_id, group_id, device_type, device_name, device_type_2, device_name_2, "Success"))
        return {'log': log.getvalue(), 'summary': summary.getvalue()}


def device_specific_migration(process_id):
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

        dm = BroadWorksDeviceMigration(process=process)
        content = dict()

        # Retrieve Data
        provider_type = process.parameters.get('provider_type', None)
        provider_id = process.parameters.get('provider_id', None)
        group_id = process.parameters.get('group_id', None)

        # Initial content
        summary_html.write('<table class="table table-striped table-bordered table-hover">\n')
        summary_html.write('<tr>\n')
        summary_html.write('\t<th>Provider Id</th><th>Group Id</th><th>Device A Type</th><th>Device A Id</th><th>Device B Type</th><th>Device B Id</th><th>Status</th>\n')
        summary_html.write('</tr>\n')
        summary_html.write('<tbody>\n')
        summary_raw.write('"Provider Id","Group Id","Device A Type","Device A Id","Device B Type","Device B Id","Status"\n')

        if provider_id and group_id:
            log_raw.write('Group {}::{}\n'.format(provider_id, group_id))
            data = dm.migrate_group(provider_id=provider_id, group_id=group_id)
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
            dm.provider_check(provider_id, True if provider_type == 'Enterprise' else False)
            groups = dm.groups(provider_id)
            for group in groups:
                group_id = group['Group Id']
                log_raw.write('    Group {}::{}\n'.format(provider_id, group_id))
                data = dm.migrate_group(provider_id=provider_id, group_id=group_id, level=2)
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
        dm.logout()
    except Exception:
        process.status = process.STATUS_ERROR
        process.end_timestamp = timezone.now()
        process.exception = traceback.format_exc()
        process.save(update_fields=['status', 'exception', 'end_timestamp'])

    # Cleanup
    log_raw.close()
    summary_html.close()
    summary_raw.close()
