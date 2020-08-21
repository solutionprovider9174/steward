# Python
import io
import os
import re
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



class BroadWorksLab:
    _bw = None

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

    def rebuild(self, provider, groups, users):
        content = io.StringIO()
        content.write("Reset Existing Devices\n")
        level=1
        for user in users:
            content.write("{}GroupAccessDeviceResetRequest(serviceProviderId={}, groupId={}, deviceName={}) ".format('    '*level, provider['id'], user['group_id'], user['user_id'])),
            resp = self._bw.GroupAccessDeviceResetRequest(serviceProviderId=provider['id'], groupId=user['group_id'], deviceName=user['user_id'])
            content.write(self.parse_response(resp, level))
        content.write('\n')

        content.write("Retrieve Defaults\n")
        content.write("{}ServiceProviderServiceGetAuthorizationListRequest('LokiHelper') ".format('    '*level)),
        resp = self._bw.ServiceProviderServiceGetAuthorizationListRequest('LokiHelper')
        content.write(self.parse_response(resp, level))
        loki_service_authorization_list = resp['data']
        content.write("{}GroupServiceGetAuthorizationListRequest('LokiHelper', 'IP Voice Phone System') ".format('    '*level)),
        resp = self._bw.GroupServiceGetAuthorizationListRequest('LokiHelper', 'IP Voice Phone System')
        loki_group_service_auth = resp['data']
        content.write(self.parse_response(resp, level))
        content.write('\n')

        content.write("Delete Groups & Provider\n")
        for group in groups:
            content.write("{}GroupDeleteRequest({}, {}) ".format('    '*level, provider['id'], group['id'])),
            resp = self._bw.GroupDeleteRequest(provider['id'], group['id'])
            content.write(self.parse_response(resp, level))
        content.write("{}ServiceProviderDeleteRequest({}) ".format('    '*level, provider['id'])),
        resp = self._bw.ServiceProviderDeleteRequest(provider['id'])
        content.write(self.parse_response(resp, level))
        content.write('\n')

        content.write("Enterprise: {}\n".format(provider['id']))
        # Enterprise
        content.write("{}ServiceProviderAddRequest13mp2({}, {}, enterprise=True) ".format('    '*level, provider['id'], provider['description'])),
        resp = self._bw.ServiceProviderAddRequest13mp2(provider['id'], provider['description'], enterprise=True)
        content.write(self.parse_response(resp, level))
        # assign numbers
        content.write("{}ServiceProviderDnAddListRequest({}, phoneNumber={{...}}) ".format('    '*level, provider['id'])),
        resp = self._bw.ServiceProviderDnAddListRequest(provider['id'], phoneNumber=provider['numbers'])
        content.write(self.parse_response(resp, level))
        # authorized services
        authorization_list = {'groupServiceAuthorization': list(), 'userServiceAuthorization': list()}
        for d in loki_service_authorization_list['groupServicesAuthorizationTable']:
            if d['Authorized'] != 'true':
                continue
            data = OrderedDict()
            data['serviceName'] = d['Service Name']
            if d['Limited'] == 'Unlimited':
                data['authorizedQuantity'] = {'unlimited': True}
            else:
                data['authorizedQuantity'] = {'quantity': d['Quantity']}
            authorization_list['groupServiceAuthorization'].append(data)
        for d in loki_service_authorization_list['userServicesAuthorizationTable']:
            if d['Authorized'] != 'true':
                continue
            data = OrderedDict()
            data['serviceName'] = d['Service Name']
            if d['Limited'] == 'Unlimited':
                data['authorizedQuantity'] = {'unlimited': True}
            else:
                data['authorizedQuantity'] = {'quantity': d['Quantity']}
            authorization_list['userServiceAuthorization'].append(data)
        content.write("{}ServiceProviderServiceModifyAuthorizationListRequest({}, ...) ".format('    '*level, provider['id'])),
        resp = self._bw.ServiceProviderServiceModifyAuthorizationListRequest(provider['id'], **authorization_list)
        content.write(self.parse_response(resp, level))

        # service packs
        content.write("{}ServiceProviderServicePackGetListRequest('LokiHelper') ".format('    '*level)),
        resp = self._bw.ServiceProviderServicePackGetListRequest('LokiHelper')
        content.write(self.parse_response(resp, level))
        loki_service_pack_list = resp['data']['servicePackName']
        for service_pack_name in loki_service_pack_list:
            content.write("{}ServiceProviderServicePackGetDetailListRequest('LokiHelper', {}) ".format('    '*level, service_pack_name)),
            resp = self._bw.ServiceProviderServicePackGetDetailListRequest('LokiHelper', service_pack_name)
            content.write(self.parse_response(resp, level))
            service_pack_detail = resp['data']

            services = list()
            for service in service_pack_detail['userServiceTable']:
                # "Service", "Authorized" "Allocated" and "Available".
                services.append(service['Service'])

            content.write("{}ServiceProviderServicePackAddRequest({}, {}, ...) ".format('    '*level, provider['id'], service_pack_name)),
            resp = self._bw.ServiceProviderServicePackAddRequest(provider['id'],
                                                                 service_pack_detail['servicePackName'],
                                                                 service_pack_detail['isAvailableForUse'],
                                                                 service_pack_detail['servicePackQuantity'],
                                                                 serviceName=services)
            content.write(self.parse_response(resp, level))
        content.write('\n')

        for group in groups:
            content.write("Group: {}::{}\n".format(provider['id'], group['id']))
            content.write("{}GroupAddRequest({}, {}, userLimit='999999', groupName={}) ".format('    '*level, provider['id'], group['id'], group['name'])),
            resp = self._bw.GroupAddRequest(provider['id'], group['id'], userLimit='999999', groupName=group['name'])
            content.write(self.parse_response(resp, level))
            content.write("{}GroupDnAssignListRequest({}, {}, phoneNumber={{...}}) ".format('    '*level, provider['id'], group['id'])),
            resp = self._bw.GroupDnAssignListRequest(provider['id'], group['id'], phoneNumber=group['numbers'])
            content.write(self.parse_response(resp, level))
            content.write("{}GroupModifyRequest({}, {}, callingLineIdPhoneNumber={}) ".format('    '*level, provider['id'], group['id'], group['number'])),
            resp = self._bw.GroupModifyRequest(provider['id'], group['id'], callingLineIdPhoneNumber=group['number'])
            content.write(self.parse_response(resp, level))
            service_auth = {'servicePackAuthorization': list(), 'groupServiceAuthorization': list(), 'userServiceAuthorization': list()}
            for d in loki_group_service_auth['servicePacksAuthorizationTable']:
                if d['Authorized'] != 'true':
                    continue
                data = OrderedDict()
                data['servicePackName'] = d['Service Pack Name']
                if d['Allowed'] == 'Unlimited':
                    data['authorizedQuantity'] = {'unlimited': True}
                else:
                    data['authorizedQuantity'] = {'quantity': d['Quantity']}
                service_auth['servicePackAuthorization'].append(data)
            for d in loki_group_service_auth['groupServicesAuthorizationTable']:
                if d['Authorized'] != 'true':
                    continue
                data = OrderedDict()
                data['serviceName'] = d['Service Name']
                if d['Allowed'] == 'Unlimited':
                    data['authorizedQuantity'] = {'unlimited': True}
                else:
                    data['authorizedQuantity'] = {'quantity': d['Quantity']}
                service_auth['groupServiceAuthorization'].append(data)
            for d in loki_group_service_auth['userServicesAuthorizationTable']:
                if d['Authorized'] != 'true':
                    continue
                data = OrderedDict()
                data['serviceName'] = d['Service Name']
                if d['Allowed'] == 'Unlimited':
                    data['authorizedQuantity'] = {'unlimited': True}
                else:
                    data['authorizedQuantity'] = {'quantity': d['Quantity']}
                service_auth['userServiceAuthorization'].append(data)

            content.write("{}GroupServiceModifyAuthorizationListRequest({}, {}, ...) ".format('    '*level, provider['id'], group['id'])),
            resp = self._bw.GroupServiceModifyAuthorizationListRequest(provider['id'], group['id'], **service_auth)
            content.write(self.parse_response(resp, level))
            for service_name in group['assigned_services']:
                content.write("{}GroupServiceAssignListRequest({}, {}, {}) ".format('    '*level, provider['id'], group['id'], service_name)),
                resp = self._bw.GroupServiceAssignListRequest(provider['id'], group['id'], service_name)
                content.write(self.parse_response(resp, level))
            orig_permissions = OrderedDict()
            orig_permissions['group'] = 'Allow'
            orig_permissions['local'] = 'Allow'
            orig_permissions['tollFree'] = 'Allow'
            orig_permissions['toll'] = 'Allow'
            orig_permissions['international'] = 'Disallow'
            orig_permissions['operatorAssisted'] = 'Allow'
            orig_permissions['chargeableDirectoryAssisted'] = 'Allow'
            orig_permissions['specialServicesI'] = 'Allow'
            orig_permissions['specialServicesII'] = 'Allow'
            orig_permissions['premiumServicesI'] = 'Allow'
            orig_permissions['premiumServicesII'] = 'Allow'
            orig_permissions['casual'] = 'Disallow'
            orig_permissions['urlDialing'] = 'Disallow'
            orig_permissions['unknown'] = 'Disallow'
            content.write("{}GroupOutgoingCallingPlanOriginatingModifyListRequest({}, {}, groupPermissions={{...}}) ".format('    '*level, provider['id'], group['id'])),
            resp = self._bw.GroupOutgoingCallingPlanOriginatingModifyListRequest(provider['id'], group['id'], groupPermissions=orig_permissions)
            content.write(self.parse_response(resp, level))
            redirect_permissions = OrderedDict()
            redirect_permissions['group'] = True
            redirect_permissions['local'] = True
            redirect_permissions['tollFree'] = True
            redirect_permissions['toll'] = True
            redirect_permissions['international'] = False
            redirect_permissions['operatorAssisted'] = False
            redirect_permissions['chargeableDirectoryAssisted'] = False
            redirect_permissions['specialServicesI'] = False
            redirect_permissions['specialServicesII'] = False
            redirect_permissions['premiumServicesI'] = False
            redirect_permissions['premiumServicesII'] = False
            redirect_permissions['casual'] = False
            redirect_permissions['urlDialing'] = False
            redirect_permissions['unknown'] = False
            content.write("{}GroupOutgoingCallingPlanRedirectingModifyListRequest({}, {}, groupPermissions={{...}}) ".format('    '*level, provider['id'], group['id'])),
            resp = self._bw.GroupOutgoingCallingPlanRedirectingModifyListRequest(provider['id'], group['id'], groupPermissions=redirect_permissions)
            content.write(self.parse_response(resp, level))
            content.write('\n')

        for user in users:
            content.write("    {}::{}: {}\n".format(user['group_id'], user['user_id'], user['device_type']))
            content.write("{}GroupAccessDeviceAddRequest14({}, {}, {}, {}, username={}, password='8675309') ".format('    '*(level+1), provider['id'], user['group_id'], user['user_id'], user['device_type'], user['device_username'])),
            resp = self._bw.GroupAccessDeviceAddRequest14(provider['id'], user['group_id'], user['user_id'], user['device_type'], username=user['device_username'], password='8675309')
            content.write(self.parse_response(resp, (level+1)))
            access_device_endpoint = OrderedDict()
            access_device_endpoint['accessDevice'] = OrderedDict()
            access_device_endpoint['accessDevice']['deviceLevel'] = 'Group'
            access_device_endpoint['accessDevice']['deviceName'] = user['user_id']
            access_device_endpoint['linePort'] = user['line_port']
            content.write("{}UserAddRequest17sp4({}, {}, {}, {}, {}, {}, {}, extension={}, password='1234aB!', accessDeviceEndpoint={{...}}) ".format('    '*(level+1), provider['id'], user['group_id'], user['user_id'], user['last_name'], user['first_name'], user['last_name'], user['first_name'], user['extension'])),
            resp = self._bw.UserAddRequest17sp4(provider['id'], user['group_id'], user['user_id'], user['last_name'], user['first_name'], user['last_name'], user['first_name'], extension=user['extension'], password='1234aB!', accessDeviceEndpoint=access_device_endpoint)
            content.write(self.parse_response(resp, (level+1)))
            content.write("{}GroupAccessDeviceModifyUserRequest({}, {}, {}, {}, True) ".format('    '*(level+1), provider['id'], user['group_id'], user['user_id'], user['line_port'])),
            resp = self._bw.GroupAccessDeviceModifyUserRequest(provider['id'], user['group_id'], user['user_id'], user['line_port'], True)
            content.write(self.parse_response(resp, (level+1)))
            content.write("{}UserServiceAssignListRequest({}, servicePackName={}) ".format('    '*(level+1), user['user_id'], user['service_pack'])),
            resp = self._bw.UserServiceAssignListRequest(user['user_id'], servicePackName=user['service_pack'])
            content.write(self.parse_response(resp, (level+1)))
            content.write('\n')

        # Shared Call and BLF
        content.write("    Shared Call Appearances and Busy Lamp Field\n")
        for user in users:
            # SCA
            for appearance in user['appearances']:
                access_device_endpoint = OrderedDict()
                access_device_endpoint['accessDevice'] = OrderedDict()
                access_device_endpoint['accessDevice']['deviceLevel'] = 'Group'
                access_device_endpoint['accessDevice']['deviceName'] = user['user_id']
                access_device_endpoint['linePort'] = appearance['line_port']
                content.write("{}UserSharedCallAppearanceAddEndpointRequest14sp2({}, {{...}}, isActive=True, allowOrigination=True, allowTermination=True) ".format('    '*(level+1), appearance['user_id'])),
                resp = self._bw.UserSharedCallAppearanceAddEndpointRequest14sp2(appearance['user_id'], access_device_endpoint, isActive=True, allowOrigination=True, allowTermination=True)
                content.write(self.parse_response(resp, (level+1)))

            # BLF
            if len(user['busy_lamp_field_users']):
                content.write("{}UserBusyLampFieldModifyRequest({}, listURI={}, monitoredUserIdList={{...}}) ".format('    '*(level+1), user['user_id'], '{}@telapexinc.com'.format(user['user_id']))),
                resp = self._bw.UserBusyLampFieldModifyRequest(user['user_id'], listURI='{}@telapexinc.com'.format(user['user_id']), monitoredUserIdList=user['busy_lamp_field_users'])
                content.write(self.parse_response(resp, (level+1)))
        content.write('\n')

        # Group Services
        content.write("Group Services\n")
        for group in groups:
            for service in group['service_instances']:
                if service['type'] == 'Hunt Group':
                    service_instance_profile = OrderedDict()
                    service_instance_profile['name'] = service['name']
                    service_instance_profile['callingLineIdLastName'] = service['clid_last_name']
                    service_instance_profile['callingLineIdFirstName'] = service['clid_first_name']
                    service_instance_profile['phoneNumber'] = service['number']
                    service_instance_profile['extension'] = service['extension']
                    service_instance_profile['password'] = '1234aB!'
                    service_instance_profile['callingLineIdPhoneNumber'] = service['clid_number']
                    content.write("{}GroupHuntGroupAddInstanceRequest19({}, {}, {}, ...) ".format('    '*level, provider['id'], group['id'], service['user_id'])),
                    resp = self._bw.GroupHuntGroupAddInstanceRequest19(provider['id'], group['id'], service['user_id'], service_instance_profile,
                                                                       policy='Simultaneous', huntAfterNoAnswer=False, noAnswerNumberOfRings=10, forwardAfterTimeout=False,
                                                                       forwardTimeoutSeconds=0, allowCallWaitingForAgents=False, useSystemHuntGroupCLIDSetting=True,
                                                                       includeHuntGroupNameInCLID=False, enableNotReachableForwarding=False, makeBusyWhenNotReachable=True,
                                                                       allowMembersToControlGroupBusy=False, enableGroupBusy=False, agentUserId=service['members'])
                    content.write(self.parse_response(resp, level))
        content.write('\n')

        rval = content.getvalue()
        content.close()
        return rval


#
# Local variables
#

provider = {
    'id': 'IP_Voice_Engineering_Lab',
    'description': 'IP Voice Engineering Lab',
    'numbers': ['+1-251-555-1100', '+1-251-555-2100',],
}
groups = [
    {
        'id': 'IPVE_LAB1',
        'name': 'IP Voice Engineering Lab 1',
        'number': '+1-251-555-1100',
        'numbers': ['+1-251-555-1100',],
        'assigned_services': ['Outgoing Calling Plan', 'Hunt Group'],
        'service_instances': [
            {
                'type': 'Hunt Group',
                'user_id': '12515551100@telapexinc.com',
                'number': '+1-251-555-1100',
                'extension': '1100',
                'name': 'Lab 1 Main Huntgroup',
                'clid_number': '+1-251-555-1100',
                'clid_last_name': 'Lab 1',
                'clid_first_name': 'Main Huntgroup',
                'members': [
                    'IPVE_LAB1_1001', 'IPVE_LAB1_1002', 'IPVE_LAB1_1003',
                    'IPVE_LAB1_1004', 'IPVE_LAB1_1005', 'IPVE_LAB1_1006',
                    'IPVE_LAB1_1007', 'IPVE_LAB1_1008', 'IPVE_LAB1_1009',
                    'IPVE_LAB1_1010', 'IPVE_LAB1_1011',
                    'IPVE_LAB1_1101', 'IPVE_LAB1_1102', 'IPVE_LAB1_1103',
                    'IPVE_LAB1_1104', 'IPVE_LAB1_1105', 'IPVE_LAB1_1106',
                    'IPVE_LAB1_1107', 'IPVE_LAB1_1108',
                ],
            }
        ]
    },
    {
        'id': 'IPVE_LAB2',
        'name': 'IP Voice Engineering Lab 2',
        'number': '+1-251-555-2100',
        'numbers': ['+1-251-555-2100',],
        'assigned_services': ['Outgoing Calling Plan', 'Hunt Group'],
        'service_instances': [
            {
                'type': 'Hunt Group',
                'user_id': '12515552100@telapexinc.com',
                'number': '+1-251-555-2100',
                'extension': '2100',
                'name': 'Lab 2 Main Huntgroup',
                'clid_number': '+1-251-555-2100',
                'clid_last_name': 'Lab 2',
                'clid_first_name': 'Main Huntgroup',
                'members': [
                    'IPVE_LAB2_2001', 'IPVE_LAB2_2002', 'IPVE_LAB2_2003',
                    'IPVE_LAB2_2004', 'IPVE_LAB2_2005', 'IPVE_LAB2_2006',
                    'IPVE_LAB2_2007', 'IPVE_LAB2_2008', 'IPVE_LAB2_2009',
                    'IPVE_LAB2_2010', 'IPVE_LAB2_2011',
                    'IPVE_LAB2_2101', 'IPVE_LAB2_2102', 'IPVE_LAB2_2103',
                    'IPVE_LAB2_2104', 'IPVE_LAB2_2105', 'IPVE_LAB2_2106',
                    'IPVE_LAB2_2107', 'IPVE_LAB2_2108',
                ],
            }
        ]
    }
]
users = [
    # Group 1
    {
        'group_id': 'IPVE_LAB1',
        'user_id': 'IPVE_LAB1_1001',
        'device_type': 'Polycom_VVX300',
        'device_username': 'IPVE-1001',
        'first_name': 'IPVE Lab',
        'last_name': '1001',
        'extension': '1001',
        'line_port': 'IPVE_LAB1_1001@telapexinc.com',
        'service_pack': 'IPVComplete',
        'appearances': [
            { 'user_id': 'IPVE_LAB1_1002', 'line_port': 'IPVE_LAB1_1001_1@telapexinc.com' },
            { 'user_id': 'IPVE_LAB1_1003', 'line_port': 'IPVE_LAB1_1001_2@telapexinc.com' }],
        'busy_lamp_field_users': ['IPVE_LAB1_1004', 'IPVE_LAB1_1005', 'IPVE_LAB1_1006',
                                  'IPVE_LAB1_1007', 'IPVE_LAB1_1008', 'IPVE_LAB1_1009',
                                  'IPVE_LAB1_1010'],
    },
    {
        'group_id': 'IPVE_LAB1',
        'user_id': 'IPVE_LAB1_1002',
        'device_type': 'Polycom_VVX300',
        'device_username': 'IPVE-1002',
        'first_name': 'IPVE Lab',
        'last_name': '1002',
        'extension': '1002',
        'line_port': 'IPVE_LAB1_1002@telapexinc.com',
        'service_pack': 'IPVComplete',
        'appearances': [
            { 'user_id': 'IPVE_LAB1_1003', 'line_port': 'IPVE_LAB1_1002_1@telapexinc.com' },
            { 'user_id': 'IPVE_LAB1_1004', 'line_port': 'IPVE_LAB1_1002_2@telapexinc.com' }],
        'busy_lamp_field_users': ['IPVE_LAB1_1001', 'IPVE_LAB1_1005', 'IPVE_LAB1_1006',
                                  'IPVE_LAB1_1007', 'IPVE_LAB1_1008', 'IPVE_LAB1_1009',
                                  'IPVE_LAB1_1010'],
    },
    {
        'group_id': 'IPVE_LAB1',
        'user_id': 'IPVE_LAB1_1003',
        'device_type': 'Polycom_VVX400',
        'device_username': 'IPVE-1003',
        'first_name': 'IPVE Lab',
        'last_name': '1003',
        'extension': '1003',
        'line_port': 'IPVE_LAB1_1003@telapexinc.com',
        'service_pack': 'IPVComplete',
        'appearances': [
            { 'user_id': 'IPVE_LAB1_1004', 'line_port': 'IPVE_LAB1_1003_1@telapexinc.com' },
            { 'user_id': 'IPVE_LAB1_1005', 'line_port': 'IPVE_LAB1_1003_2@telapexinc.com' }],
        'busy_lamp_field_users': ['IPVE_LAB1_1001', 'IPVE_LAB1_1002', 'IPVE_LAB1_1006',
                                  'IPVE_LAB1_1007', 'IPVE_LAB1_1008', 'IPVE_LAB1_1009',
                                  'IPVE_LAB1_1010'],
    },
    {
        'group_id': 'IPVE_LAB1',
        'user_id': 'IPVE_LAB1_1004',
        'device_type': 'Polycom_VVX400',
        'device_username': 'IPVE-1004',
        'first_name': 'IPVE Lab',
        'last_name': '1004',
        'extension': '1004',
        'line_port': 'IPVE_LAB1_1004@telapexinc.com',
        'service_pack': 'IPVComplete',
        'appearances': [
            { 'user_id': 'IPVE_LAB1_1005', 'line_port': 'IPVE_LAB1_1004_1@telapexinc.com' },
            { 'user_id': 'IPVE_LAB1_1006', 'line_port': 'IPVE_LAB1_1004_2@telapexinc.com' }],
        'busy_lamp_field_users': ['IPVE_LAB1_1001', 'IPVE_LAB1_1002', 'IPVE_LAB1_1003',
                                  'IPVE_LAB1_1007', 'IPVE_LAB1_1008', 'IPVE_LAB1_1009',
                                  'IPVE_LAB1_1010'],
    },
    {
        'group_id': 'IPVE_LAB1',
        'user_id': 'IPVE_LAB1_1005',
        'device_type': 'Polycom_VVX500',
        'device_username': 'IPVE-1005',
        'first_name': 'IPVE Lab',
        'last_name': '1005',
        'extension': '1005',
        'line_port': 'IPVE_LAB1_1005@telapexinc.com',
        'service_pack': 'IPVComplete',
        'appearances': [
            { 'user_id': 'IPVE_LAB1_1006', 'line_port': 'IPVE_LAB1_1005_1@telapexinc.com' },
            { 'user_id': 'IPVE_LAB1_1007', 'line_port': 'IPVE_LAB1_1005_2@telapexinc.com' }],
        'busy_lamp_field_users': ['IPVE_LAB1_1001', 'IPVE_LAB1_1002', 'IPVE_LAB1_1003',
                                  'IPVE_LAB1_1004', 'IPVE_LAB1_1008', 'IPVE_LAB1_1009',
                                  'IPVE_LAB1_1010'],
    },
    {
        'group_id': 'IPVE_LAB1',
        'user_id': 'IPVE_LAB1_1006',
        'device_type': 'Polycom_VVX600',
        'device_username': 'IPVE-1006',
        'first_name': 'IPVE Lab',
        'last_name': '1006',
        'extension': '1006',
        'line_port': 'IPVE_LAB1_1006@telapexinc.com',
        'service_pack': 'IPVComplete',
        'appearances': [
            { 'user_id': 'IPVE_LAB1_1007', 'line_port': 'IPVE_LAB1_1006_1@telapexinc.com' },
            { 'user_id': 'IPVE_LAB1_1008', 'line_port': 'IPVE_LAB1_1006_2@telapexinc.com' }],
        'busy_lamp_field_users': ['IPVE_LAB1_1001', 'IPVE_LAB1_1002', 'IPVE_LAB1_1003',
                                  'IPVE_LAB1_1004', 'IPVE_LAB1_1005', 'IPVE_LAB1_1009',
                                  'IPVE_LAB1_1010'],
    },
    {
        'group_id': 'IPVE_LAB1',
        'user_id': 'IPVE_LAB1_1007',
        'device_type': 'Polycom_IP335',
        'device_username': 'IPVE-1007',
        'first_name': 'IPVE Lab',
        'last_name': '1007',
        'extension': '1007',
        'line_port': 'IPVE_LAB1_1007@telapexinc.com',
        'service_pack': 'IPVComplete',
        'appearances': [
            { 'user_id': 'IPVE_LAB1_1008', 'line_port': 'IPVE_LAB1_1007_1@telapexinc.com' }],
        'busy_lamp_field_users': ['IPVE_LAB1_1001', 'IPVE_LAB1_1002', 'IPVE_LAB1_1003',
                                  'IPVE_LAB1_1004', 'IPVE_LAB1_1005', 'IPVE_LAB1_1006',
                                  'IPVE_LAB1_1009', 'IPVE_LAB1_1010'],
    },
    {
        'group_id': 'IPVE_LAB1',
        'user_id': 'IPVE_LAB1_1008',
        'device_type': 'Polycom_IP450',
        'device_username': 'IPVE-1008',
        'first_name': 'IPVE Lab',
        'last_name': '1008',
        'extension': '1008',
        'line_port': 'IPVE_LAB1_1008@telapexinc.com',
        'service_pack': 'IPVComplete',
        'appearances': [
            { 'user_id': 'IPVE_LAB1_1009', 'line_port': 'IPVE_LAB1_1008_1@telapexinc.com' },
            { 'user_id': 'IPVE_LAB1_1010', 'line_port': 'IPVE_LAB1_1008_2@telapexinc.com' }],
        'busy_lamp_field_users': ['IPVE_LAB1_1001', 'IPVE_LAB1_1002', 'IPVE_LAB1_1003',
                                  'IPVE_LAB1_1004', 'IPVE_LAB1_1005', 'IPVE_LAB1_1006',
                                  'IPVE_LAB1_1007'],
    },
    {
        'group_id': 'IPVE_LAB1',
        'user_id': 'IPVE_LAB1_1009',
        'device_type': 'Polycom_IP550',
        'device_username': 'IPVE-1009',
        'first_name': 'IPVE Lab',
        'last_name': '1009',
        'extension': '1009',
        'line_port': 'IPVE_LAB1_1009@telapexinc.com',
        'service_pack': 'IPVComplete',
        'appearances': [
            { 'user_id': 'IPVE_LAB1_1010', 'line_port': 'IPVE_LAB1_1009_1@telapexinc.com' },
            { 'user_id': 'IPVE_LAB1_1001', 'line_port': 'IPVE_LAB1_1009_2@telapexinc.com' }],
        'busy_lamp_field_users': ['IPVE_LAB1_1002', 'IPVE_LAB1_1003', 'IPVE_LAB1_1004',
                                  'IPVE_LAB1_1005', 'IPVE_LAB1_1006', 'IPVE_LAB1_1007',
                                  'IPVE_LAB1_1008'],
    },
    {
        'group_id': 'IPVE_LAB1',
        'user_id': 'IPVE_LAB1_1010',
        'device_type': 'Polycom_IP650',
        'device_username': 'IPVE-1010',
        'first_name': 'IPVE Lab',
        'last_name': '1010',
        'extension': '1010',
        'line_port': 'IPVE_LAB1_1010@telapexinc.com',
        'service_pack': 'IPVComplete',
        'appearances': [
            { 'user_id': 'IPVE_LAB1_1001', 'line_port': 'IPVE_LAB1_1010_1@telapexinc.com' },
            { 'user_id': 'IPVE_LAB1_1002', 'line_port': 'IPVE_LAB1_1010_2@telapexinc.com' }],
        'busy_lamp_field_users': ['IPVE_LAB1_1003', 'IPVE_LAB1_1004', 'IPVE_LAB1_1005',
                                  'IPVE_LAB1_1006', 'IPVE_LAB1_1007', 'IPVE_LAB1_1008',
                                  'IPVE_LAB1_1009'],
    },
    {
        'group_id': 'IPVE_LAB1',
        'user_id': 'IPVE_LAB1_1011',
        'device_type': 'Polycom-conf',
        'device_username': 'IPVE-1011',
        'first_name': 'IPVE Lab',
        'last_name': '1011',
        'extension': '1011',
        'line_port': 'IPVE_LAB1_1011@telapexinc.com',
        'service_pack': 'IPVComplete',
        'appearances': [],
        'busy_lamp_field_users': [],
    },
    {
        'group_id': 'IPVE_LAB1',
        'user_id': 'IPVE_LAB1_1101',
        'device_type': 'Polycom_VVX101',
        'device_username': 'IPVE-1101',
        'first_name': 'IPVE Lab',
        'last_name': '1101',
        'extension': '1101',
        'line_port': 'IPVE_LAB1_1101@telapexinc.com',
        'service_pack': 'IPVComplete',
        'appearances': [
                { 'user_id': 'IPVE_LAB1_1102', 'line_port': 'IPVE_LAB1_1101_1@telapexinc.com' },
                { 'user_id': 'IPVE_LAB1_1103', 'line_port': 'IPVE_LAB1_1101_2@telapexinc.com' }],
        'busy_lamp_field_users': ['IPVE_LAB1_1104', 'IPVE_LAB1_1105', 'IPVE_LAB1_1106',
                                  'IPVE_LAB1_1107', 'IPVE_LAB1_1108'],
    },
    {
        'group_id': 'IPVE_LAB1',
        'user_id': 'IPVE_LAB1_1102',
        'device_type': 'Polycom_VVX201',
        'device_username': 'IPVE-1102',
        'first_name': 'IPVE Lab',
        'last_name': '1102',
        'extension': '1102',
        'line_port': 'IPVE_LAB1_1102@telapexinc.com',
        'service_pack': 'IPVComplete',
        'appearances': [
                { 'user_id': 'IPVE_LAB1_1103', 'line_port': 'IPVE_LAB1_1102_1@telapexinc.com' },
                { 'user_id': 'IPVE_LAB1_1104', 'line_port': 'IPVE_LAB1_1102_2@telapexinc.com' }],
        'busy_lamp_field_users': ['IPVE_LAB1_1101', 'IPVE_LAB1_1105', 'IPVE_LAB1_1106',
                                  'IPVE_LAB1_1107', 'IPVE_LAB1_1108'],
    },
    {
        'group_id': 'IPVE_LAB1',
        'user_id': 'IPVE_LAB1_1103',
        'device_type': 'Polycom_VVX300',
        'device_username': 'IPVE-1103',
        'first_name': 'IPVE Lab',
        'last_name': '1103',
        'extension': '1103',
        'line_port': 'IPVE_LAB1_1103@telapexinc.com',
        'service_pack': 'IPVComplete',
        'appearances': [
                { 'user_id': 'IPVE_LAB1_1104', 'line_port': 'IPVE_LAB1_1103_1@telapexinc.com' },
                { 'user_id': 'IPVE_LAB1_1105', 'line_port': 'IPVE_LAB1_1103_2@telapexinc.com' }],
        'busy_lamp_field_users': ['IPVE_LAB1_1101', 'IPVE_LAB1_1102', 'IPVE_LAB1_1106',
                                  'IPVE_LAB1_1107', 'IPVE_LAB1_1108'],
    },
    {
        'group_id': 'IPVE_LAB1',
        'user_id': 'IPVE_LAB1_1104',
        'device_type': 'Polycom_VVX300',
        'device_username': 'IPVE-1104',
        'first_name': 'IPVE Lab',
        'last_name': '1104',
        'extension': '1104',
        'line_port': 'IPVE_LAB1_1104@telapexinc.com',
        'service_pack': 'IPVComplete',
        'appearances': [
                { 'user_id': 'IPVE_LAB1_1105', 'line_port': 'IPVE_LAB1_1104_1@telapexinc.com' },
                { 'user_id': 'IPVE_LAB1_1106', 'line_port': 'IPVE_LAB1_1104_2@telapexinc.com' }],
        'busy_lamp_field_users': ['IPVE_LAB1_1101', 'IPVE_LAB1_1102', 'IPVE_LAB1_1103',
                                  'IPVE_LAB1_1107', 'IPVE_LAB1_1108'],
    },
    {
        'group_id': 'IPVE_LAB1',
        'user_id': 'IPVE_LAB1_1105',
        'device_type': 'Polycom_VVX400',
        'device_username': 'IPVE-1105',
        'first_name': 'IPVE Lab',
        'last_name': '1105',
        'extension': '1105',
        'line_port': 'IPVE_LAB1_1105@telapexinc.com',
        'service_pack': 'IPVComplete',
        'appearances': [
                { 'user_id': 'IPVE_LAB1_1106', 'line_port': 'IPVE_LAB1_1105_1@telapexinc.com' },
                { 'user_id': 'IPVE_LAB1_1107', 'line_port': 'IPVE_LAB1_1105_2@telapexinc.com' }],
        'busy_lamp_field_users': ['IPVE_LAB1_1101', 'IPVE_LAB1_1102', 'IPVE_LAB1_1103',
                                  'IPVE_LAB1_1104', 'IPVE_LAB1_1108'],
    },
    {
        'group_id': 'IPVE_LAB1',
        'user_id': 'IPVE_LAB1_1106',
        'device_type': 'Polycom_VVX400',
        'device_username': 'IPVE-1106',
        'first_name': 'IPVE Lab',
        'last_name': '1106',
        'extension': '1106',
        'line_port': 'IPVE_LAB1_1106@telapexinc.com',
        'service_pack': 'IPVComplete',
        'appearances': [
                { 'user_id': 'IPVE_LAB1_1107', 'line_port': 'IPVE_LAB1_1106_1@telapexinc.com' },
                { 'user_id': 'IPVE_LAB1_1108', 'line_port': 'IPVE_LAB1_1106_2@telapexinc.com' }],
        'busy_lamp_field_users': ['IPVE_LAB1_1101', 'IPVE_LAB1_1102', 'IPVE_LAB1_1103',
                                  'IPVE_LAB1_1104', 'IPVE_LAB1_1105'],
    },
    {
        'group_id': 'IPVE_LAB1',
        'user_id': 'IPVE_LAB1_1107',
        'device_type': 'Polycom_VVX500',
        'device_username': 'IPVE-1107',
        'first_name': 'IPVE Lab',
        'last_name': '1107',
        'extension': '1107',
        'line_port': 'IPVE_LAB1_1107@telapexinc.com',
        'service_pack': 'IPVComplete',
        'appearances': [
                { 'user_id': 'IPVE_LAB1_1108', 'line_port': 'IPVE_LAB1_1107_1@telapexinc.com' },
                { 'user_id': 'IPVE_LAB1_1101', 'line_port': 'IPVE_LAB1_1107_2@telapexinc.com' }],
        'busy_lamp_field_users': ['IPVE_LAB1_1102', 'IPVE_LAB1_1103', 'IPVE_LAB1_1104',
                                  'IPVE_LAB1_1105', 'IPVE_LAB1_1106'],
    },
    {
        'group_id': 'IPVE_LAB1',
        'user_id': 'IPVE_LAB1_1108',
        'device_type': 'Polycom_VVX600',
        'device_username': 'IPVE-1108',
        'first_name': 'IPVE Lab',
        'last_name': '1108',
        'extension': '1108',
        'line_port': 'IPVE_LAB1_1108@telapexinc.com',
        'service_pack': 'IPVComplete',
        'appearances': [
                { 'user_id': 'IPVE_LAB1_1101', 'line_port': 'IPVE_LAB1_1108_1@telapexinc.com' },
                { 'user_id': 'IPVE_LAB1_1102', 'line_port': 'IPVE_LAB1_1108_2@telapexinc.com' }],
        'busy_lamp_field_users': ['IPVE_LAB1_1103', 'IPVE_LAB1_1104', 'IPVE_LAB1_1105',
                                  'IPVE_LAB1_1106', 'IPVE_LAB1_1107'],
    },
    # Group 2
    {
        'group_id': 'IPVE_LAB2',
        'user_id': 'IPVE_LAB2_2001',
        #'device_type': 'Polycom_VVX300',
        'device_type': 'Polycom',
        'device_username': 'IPVE-2001',
        'first_name': 'IPVE Lab',
        'last_name': '2001',
        'extension': '2001',
        'line_port': 'IPVE_LAB2_2001@telapexinc.com',
        'service_pack': 'IPVComplete',
        'appearances': [
            { 'user_id': 'IPVE_LAB2_2002', 'line_port': 'IPVE_LAB2_2001_1@telapexinc.com' },
            { 'user_id': 'IPVE_LAB2_2003', 'line_port': 'IPVE_LAB2_2001_2@telapexinc.com' }],
        'busy_lamp_field_users': ['IPVE_LAB2_2004', 'IPVE_LAB2_2005', 'IPVE_LAB2_2006',
                                  'IPVE_LAB2_2007', 'IPVE_LAB2_2008', 'IPVE_LAB2_2009',
                                  'IPVE_LAB2_2010'],
    },
    {
        'group_id': 'IPVE_LAB2',
        'user_id': 'IPVE_LAB2_2002',
        # 'device_type': 'Polycom_VVX300',
        'device_type': 'Polycom',
        'device_username': 'IPVE-2002',
        'first_name': 'IPVE Lab',
        'last_name': '2002',
        'extension': '2002',
        'line_port': 'IPVE_LAB2_2002@telapexinc.com',
        'service_pack': 'IPVComplete',
        'appearances': [
            { 'user_id': 'IPVE_LAB2_2003', 'line_port': 'IPVE_LAB2_2002_1@telapexinc.com' },
            { 'user_id': 'IPVE_LAB2_2004', 'line_port': 'IPVE_LAB2_2002_2@telapexinc.com' }],
        'busy_lamp_field_users': ['IPVE_LAB2_2001', 'IPVE_LAB2_2005', 'IPVE_LAB2_2006',
                                  'IPVE_LAB2_2007', 'IPVE_LAB2_2008', 'IPVE_LAB2_2009',
                                  'IPVE_LAB2_2010'],
    },
    {
        'group_id': 'IPVE_LAB2',
        'user_id': 'IPVE_LAB2_2003',
        # 'device_type': 'Polycom_VVX400',
        'device_type': 'Polycom',
        'device_username': 'IPVE-2003',
        'first_name': 'IPVE Lab',
        'last_name': '2003',
        'extension': '2003',
        'line_port': 'IPVE_LAB2_2003@telapexinc.com',
        'service_pack': 'IPVComplete',
        'appearances': [
            { 'user_id': 'IPVE_LAB2_2004', 'line_port': 'IPVE_LAB2_2003_1@telapexinc.com' },
            { 'user_id': 'IPVE_LAB2_2005', 'line_port': 'IPVE_LAB2_2003_2@telapexinc.com' }],
        'busy_lamp_field_users': ['IPVE_LAB2_2001', 'IPVE_LAB2_2002', 'IPVE_LAB2_2006',
                                  'IPVE_LAB2_2007', 'IPVE_LAB2_2008', 'IPVE_LAB2_2009',
                                  'IPVE_LAB2_2010'],
    },
    {
        'group_id': 'IPVE_LAB2',
        'user_id': 'IPVE_LAB2_2004',
        # 'device_type': 'Polycom_VVX400',
        'device_type': 'Polycom',
        'device_username': 'IPVE-2004',
        'first_name': 'IPVE Lab',
        'last_name': '2004',
        'extension': '2004',
        'line_port': 'IPVE_LAB2_2004@telapexinc.com',
        'service_pack': 'IPVComplete',
        'appearances': [
            { 'user_id': 'IPVE_LAB2_2005', 'line_port': 'IPVE_LAB2_2004_1@telapexinc.com' },
            { 'user_id': 'IPVE_LAB2_2006', 'line_port': 'IPVE_LAB2_2004_2@telapexinc.com' }],
        'busy_lamp_field_users': ['IPVE_LAB2_2001', 'IPVE_LAB2_2002', 'IPVE_LAB2_2003',
                                  'IPVE_LAB2_2007', 'IPVE_LAB2_2008', 'IPVE_LAB2_2009',
                                  'IPVE_LAB2_2010'],
    },
    {
        'group_id': 'IPVE_LAB2',
        'user_id': 'IPVE_LAB2_2005',
        # 'device_type': 'Polycom_VVX500',
        'device_type': 'Polycom',
        'device_username': 'IPVE-2005',
        'first_name': 'IPVE Lab',
        'last_name': '2005',
        'extension': '2005',
        'line_port': 'IPVE_LAB2_2005@telapexinc.com',
        'service_pack': 'IPVComplete',
        'appearances': [
            { 'user_id': 'IPVE_LAB2_2006', 'line_port': 'IPVE_LAB2_2005_1@telapexinc.com' },
            { 'user_id': 'IPVE_LAB2_2007', 'line_port': 'IPVE_LAB2_2005_2@telapexinc.com' }],
        'busy_lamp_field_users': ['IPVE_LAB2_2001', 'IPVE_LAB2_2002', 'IPVE_LAB2_2003',
                                  'IPVE_LAB2_2004', 'IPVE_LAB2_2008', 'IPVE_LAB2_2009',
                                  'IPVE_LAB2_2010'],
    },
    {
        'group_id': 'IPVE_LAB2',
        'user_id': 'IPVE_LAB2_2006',
        # 'device_type': 'Polycom_VVX600',
        'device_type': 'Polycom',
        'device_username': 'IPVE-2006',
        'first_name': 'IPVE Lab',
        'last_name': '2006',
        'extension': '2006',
        'line_port': 'IPVE_LAB2_2006@telapexinc.com',
        'service_pack': 'IPVComplete',
        'appearances': [
            { 'user_id': 'IPVE_LAB2_2007', 'line_port': 'IPVE_LAB2_2006_1@telapexinc.com' },
            { 'user_id': 'IPVE_LAB2_2008', 'line_port': 'IPVE_LAB2_2006_2@telapexinc.com' }],
        'busy_lamp_field_users': ['IPVE_LAB2_2001', 'IPVE_LAB2_2002', 'IPVE_LAB2_2003',
                                  'IPVE_LAB2_2004', 'IPVE_LAB2_2005', 'IPVE_LAB2_2009',
                                  'IPVE_LAB2_2010'],
    },
    {
        'group_id': 'IPVE_LAB2',
        'user_id': 'IPVE_LAB2_2007',
        # 'device_type': 'Polycom_IP335',
        'device_type': 'Polycom',
        'device_username': 'IPVE-2007',
        'first_name': 'IPVE Lab',
        'last_name': '2007',
        'extension': '2007',
        'line_port': 'IPVE_LAB2_2007@telapexinc.com',
        'service_pack': 'IPVComplete',
        'appearances': [
            { 'user_id': 'IPVE_LAB2_2008', 'line_port': 'IPVE_LAB2_2007_1@telapexinc.com' }],
        'busy_lamp_field_users': ['IPVE_LAB2_2001', 'IPVE_LAB2_2002', 'IPVE_LAB2_2003',
                                  'IPVE_LAB2_2004', 'IPVE_LAB2_2005', 'IPVE_LAB2_2006',
                                  'IPVE_LAB2_2009', 'IPVE_LAB2_2010'],
    },
    {
        'group_id': 'IPVE_LAB2',
        'user_id': 'IPVE_LAB2_2008',
        # 'device_type': 'Polycom_IP450',
        'device_type': 'Polycom',
        'device_username': 'IPVE-2008',
        'first_name': 'IPVE Lab',
        'last_name': '2008',
        'extension': '2008',
        'line_port': 'IPVE_LAB2_2008@telapexinc.com',
        'service_pack': 'IPVComplete',
        'appearances': [
            { 'user_id': 'IPVE_LAB2_2009', 'line_port': 'IPVE_LAB2_2008_1@telapexinc.com' },
            { 'user_id': 'IPVE_LAB2_2010', 'line_port': 'IPVE_LAB2_2008_2@telapexinc.com' }],
        'busy_lamp_field_users': ['IPVE_LAB2_2001', 'IPVE_LAB2_2002', 'IPVE_LAB2_2003',
                                  'IPVE_LAB2_2004', 'IPVE_LAB2_2005', 'IPVE_LAB2_2006',
                                  'IPVE_LAB2_2007'],
    },
    {
        'group_id': 'IPVE_LAB2',
        'user_id': 'IPVE_LAB2_2009',
        # 'device_type': 'Polycom_IP550',
        'device_type': 'Polycom',
        'device_username': 'IPVE-2009',
        'first_name': 'IPVE Lab',
        'last_name': '2009',
        'extension': '2009',
        'line_port': 'IPVE_LAB2_2009@telapexinc.com',
        'service_pack': 'IPVComplete',
        'appearances': [
            { 'user_id': 'IPVE_LAB2_2010', 'line_port': 'IPVE_LAB2_2009_1@telapexinc.com' },
            { 'user_id': 'IPVE_LAB2_2001', 'line_port': 'IPVE_LAB2_2009_2@telapexinc.com' }],
        'busy_lamp_field_users': ['IPVE_LAB2_2002', 'IPVE_LAB2_2003', 'IPVE_LAB2_2004',
                                  'IPVE_LAB2_2005', 'IPVE_LAB2_2006', 'IPVE_LAB2_2007',
                                  'IPVE_LAB2_2008'],
    },
    {
        'group_id': 'IPVE_LAB2',
        'user_id': 'IPVE_LAB2_2010',
        # 'device_type': 'Polycom_IP650',
        'device_type': 'Polycom',
        'device_username': 'IPVE-2010',
        'first_name': 'IPVE Lab',
        'last_name': '2010',
        'extension': '2010',
        'line_port': 'IPVE_LAB2_2010@telapexinc.com',
        'service_pack': 'IPVComplete',
        'appearances': [
            { 'user_id': 'IPVE_LAB2_2001', 'line_port': 'IPVE_LAB2_2010_1@telapexinc.com' },
            { 'user_id': 'IPVE_LAB2_2002', 'line_port': 'IPVE_LAB2_2010_2@telapexinc.com' }],
        'busy_lamp_field_users': ['IPVE_LAB2_2003', 'IPVE_LAB2_2004', 'IPVE_LAB2_2005',
                                  'IPVE_LAB2_2006', 'IPVE_LAB2_2007', 'IPVE_LAB2_2008',
                                  'IPVE_LAB2_2009'],
    },
    {
        'group_id': 'IPVE_LAB2',
        'user_id': 'IPVE_LAB2_2011',
        'device_type': 'Polycom-conf',
        'device_username': 'IPVE-2011',
        'first_name': 'IPVE Lab',
        'last_name': '2011',
        'extension': '2011',
        'line_port': 'IPVE_LAB2_2011@telapexinc.com',
        'service_pack': 'IPVComplete',
        'appearances': [],
        'busy_lamp_field_users': [],
    },
    {
        'group_id': 'IPVE_LAB2',
        'user_id': 'IPVE_LAB2_2101',
        'device_type': 'Polycom_VVX101',
        'device_username': 'IPVE-2101',
        'first_name': 'IPVE Lab',
        'last_name': '2101',
        'extension': '2101',
        'line_port': 'IPVE_LAB2_2101@telapexinc.com',
        'service_pack': 'IPVComplete',
        'appearances': [
                { 'user_id': 'IPVE_LAB2_2102', 'line_port': 'IPVE_LAB2_2101_1@telapexinc.com' },
                { 'user_id': 'IPVE_LAB2_2103', 'line_port': 'IPVE_LAB2_2101_2@telapexinc.com' }],
        'busy_lamp_field_users': ['IPVE_LAB2_2104', 'IPVE_LAB2_2105', 'IPVE_LAB2_2106',
                                  'IPVE_LAB2_2107', 'IPVE_LAB2_2108'],
    },
    {
        'group_id': 'IPVE_LAB2',
        'user_id': 'IPVE_LAB2_2102',
        'device_type': 'Polycom_VVX201',
        'device_username': 'IPVE-2102',
        'first_name': 'IPVE Lab',
        'last_name': '2102',
        'extension': '2102',
        'line_port': 'IPVE_LAB2_2102@telapexinc.com',
        'service_pack': 'IPVComplete',
        'appearances': [
                { 'user_id': 'IPVE_LAB2_2103', 'line_port': 'IPVE_LAB2_2102_1@telapexinc.com' },
                { 'user_id': 'IPVE_LAB2_2104', 'line_port': 'IPVE_LAB2_2102_2@telapexinc.com' }],
        'busy_lamp_field_users': ['IPVE_LAB2_2101', 'IPVE_LAB2_2105', 'IPVE_LAB2_2106',
                                  'IPVE_LAB2_2107', 'IPVE_LAB2_2108'],
    },
    {
        'group_id': 'IPVE_LAB2',
        'user_id': 'IPVE_LAB2_2103',
        'device_type': 'Polycom_VVX300',
        'device_username': 'IPVE-2103',
        'first_name': 'IPVE Lab',
        'last_name': '2103',
        'extension': '2103',
        'line_port': 'IPVE_LAB2_2103@telapexinc.com',
        'service_pack': 'IPVComplete',
        'appearances': [
                { 'user_id': 'IPVE_LAB2_2104', 'line_port': 'IPVE_LAB2_2103_1@telapexinc.com' },
                { 'user_id': 'IPVE_LAB2_2105', 'line_port': 'IPVE_LAB2_2103_2@telapexinc.com' }],
        'busy_lamp_field_users': ['IPVE_LAB2_2101', 'IPVE_LAB2_2102', 'IPVE_LAB2_2106',
                                  'IPVE_LAB2_2107', 'IPVE_LAB2_2108'],
    },
    {
        'group_id': 'IPVE_LAB2',
        'user_id': 'IPVE_LAB2_2104',
        'device_type': 'Polycom_VVX300',
        'device_username': 'IPVE-2104',
        'first_name': 'IPVE Lab',
        'last_name': '2104',
        'extension': '2104',
        'line_port': 'IPVE_LAB2_2104@telapexinc.com',
        'service_pack': 'IPVComplete',
        'appearances': [
                { 'user_id': 'IPVE_LAB2_2105', 'line_port': 'IPVE_LAB2_2104_1@telapexinc.com' },
                { 'user_id': 'IPVE_LAB2_2106', 'line_port': 'IPVE_LAB2_2104_2@telapexinc.com' }],
        'busy_lamp_field_users': ['IPVE_LAB2_2101', 'IPVE_LAB2_2102', 'IPVE_LAB2_2103',
                                  'IPVE_LAB2_2107', 'IPVE_LAB2_2108'],
    },
    {
        'group_id': 'IPVE_LAB2',
        'user_id': 'IPVE_LAB2_2105',
        'device_type': 'Polycom_VVX400',
        'device_username': 'IPVE-2105',
        'first_name': 'IPVE Lab',
        'last_name': '2105',
        'extension': '2105',
        'line_port': 'IPVE_LAB2_2105@telapexinc.com',
        'service_pack': 'IPVComplete',
        'appearances': [
                { 'user_id': 'IPVE_LAB2_2106', 'line_port': 'IPVE_LAB2_2105_1@telapexinc.com' },
                { 'user_id': 'IPVE_LAB2_2107', 'line_port': 'IPVE_LAB2_2105_2@telapexinc.com' }],
        'busy_lamp_field_users': ['IPVE_LAB2_2101', 'IPVE_LAB2_2102', 'IPVE_LAB2_2103',
                                  'IPVE_LAB2_2104', 'IPVE_LAB2_2108'],
    },
    {
        'group_id': 'IPVE_LAB2',
        'user_id': 'IPVE_LAB2_2106',
        'device_type': 'Polycom_VVX400',
        'device_username': 'IPVE-2106',
        'first_name': 'IPVE Lab',
        'last_name': '2106',
        'extension': '2106',
        'line_port': 'IPVE_LAB2_2106@telapexinc.com',
        'service_pack': 'IPVComplete',
        'appearances': [
                { 'user_id': 'IPVE_LAB2_2107', 'line_port': 'IPVE_LAB2_2106_1@telapexinc.com' },
                { 'user_id': 'IPVE_LAB2_2108', 'line_port': 'IPVE_LAB2_2106_2@telapexinc.com' }],
        'busy_lamp_field_users': ['IPVE_LAB2_2101', 'IPVE_LAB2_2102', 'IPVE_LAB2_2103',
                                  'IPVE_LAB2_2104', 'IPVE_LAB2_2105'],
    },
    {
        'group_id': 'IPVE_LAB2',
        'user_id': 'IPVE_LAB2_2107',
        'device_type': 'Polycom_VVX500',
        'device_username': 'IPVE-2107',
        'first_name': 'IPVE Lab',
        'last_name': '2107',
        'extension': '2107',
        'line_port': 'IPVE_LAB2_2107@telapexinc.com',
        'service_pack': 'IPVComplete',
        'appearances': [
                { 'user_id': 'IPVE_LAB2_2108', 'line_port': 'IPVE_LAB2_2107_1@telapexinc.com' },
                { 'user_id': 'IPVE_LAB2_2101', 'line_port': 'IPVE_LAB2_2107_2@telapexinc.com' }],
        'busy_lamp_field_users': ['IPVE_LAB2_2102', 'IPVE_LAB2_2103', 'IPVE_LAB2_2104',
                                  'IPVE_LAB2_2105', 'IPVE_LAB2_2106'],
    },
    {
        'group_id': 'IPVE_LAB2',
        'user_id': 'IPVE_LAB2_2108',
        'device_type': 'Polycom_VVX600',
        'device_username': 'IPVE-2108',
        'first_name': 'IPVE Lab',
        'last_name': '2108',
        'extension': '2108',
        'line_port': 'IPVE_LAB1_2108@telapexinc.com',
        'service_pack': 'IPVComplete',
        'appearances': [
                { 'user_id': 'IPVE_LAB2_2101', 'line_port': 'IPVE_LAB2_2108_1@telapexinc.com' },
                { 'user_id': 'IPVE_LAB2_2102', 'line_port': 'IPVE_LAB2_2108_2@telapexinc.com' }],
        'busy_lamp_field_users': ['IPVE_LAB2_2103', 'IPVE_LAB2_2104', 'IPVE_LAB2_2105',
                                  'IPVE_LAB2_2106', 'IPVE_LAB2_2107'],
    },
]


def lab_rebuild(process_id):
    process = Process.objects.get(id=process_id)
    # Log Tab
    log_content = ProcessContent.objects.create(process=process, tab='Log', priority=1)
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
        bwl = BroadWorksLab(process)
        data = bwl.rebuild(provider, groups, users)
        log_raw.write(data)
        process.end_timestamp = timezone.now()
        process.status = process.STATUS_COMPLETED
        process.save(update_fields=['status', 'end_timestamp'])
    except Exception:
        process.status = process.STATUS_ERROR
        process.end_timestamp = timezone.now()
        process.exception = traceback.format_exc()
        process.save(update_fields=['status', 'exception', 'end_timestamp'])

    # Cleanup
    log_raw.close()
