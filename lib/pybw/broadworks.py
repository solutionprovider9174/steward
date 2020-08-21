# Stdlib imports
import re
import uuid
import logging
import hashlib
import warnings
from io import BytesIO
from xml.sax.saxutils import escape
from collections import OrderedDict

# Third-party app imports
from lxml import etree
from suds.client import Client

# Application imports


class Nil:
    pass


class BroadWorks:
    name = 'BroadWorks'

    _sessionId = None
    _userDomain = None
    _locale = None
    _encoding = None
    _loginType = None
    _passwordExpiresDays = None


    group_services = [
        'Call Pickup', 'Group Paging', 'Trunk Group', 'Preferred Carrier Group', 'Voice Messaging Group',
        'Auto Attendant - Standard', 'Incoming Calling Plan', 'Hunt Group', 'Custom Ringback Group - Video',
        'Music On Hold', 'Auto Attendant - Video', 'Call Park', 'Inventory Report', 'Outgoing Calling Plan',
        'Enhanced Outgoing Calling Plan', 'Meet-Me Conferencing', 'Music On Hold - Video', 'Auto Attendant',
        'Emergency Zones', 'Custom Ringback Group', 'Service Scripts Group', 'Call Capacity Management',
        'Instant Group Call', 'LDAP Integration', 'Series Completion', 'Account/Authorization Codes', 'Intercept Group',
    ]

    user_services = [
        'Voice Portal Calling', 'Enhanced Call Logs', 'Diversion Inhibitor', 'Do Not Disturb', 'Client License 4',
        'Client License 3', 'In-Call Service Activation', 'Calling Line ID Delivery Blocking', 'Client License 19',
        'Client License 18', 'Client License 17', 'Internal Calling Line ID Delivery', 'Call Recording',
        'Selective Call Acceptance', 'Two-Stage Dialing', 'Video Add-On', 'Sequential Ring', 'Call Waiting',
        'Virtual On-Net Enterprise Extensions', 'Shared Call Appearance 35', 'Shared Call Appearance 30',
        'Automatic Callback', 'Shared Call Appearance 25', 'Selective Call Rejection', 'Calling Name Delivery',
        'Last Number Redial', 'Zone Calling Restrictions', 'Shared Call Appearance 20', 'Call Me Now',
        'Shared Call Appearance 15', 'Shared Call Appearance 10', 'Charge Number', 'Speed Dial 100',
        'Multiple Call Arrangement', 'Automatic Hold/Retrieve', 'Malicious Call Trace', 'Client Call Control',
        'External Calling Line ID Delivery', 'Hoteling Guest', 'Directed Call Pickup with Barge-in',
        'SMDI Message Desk', 'Anonymous Call Rejection', 'Third-Party Voice Mail Support', 'Calling Party Category',
        'Basic Call Logs', 'Alternate Numbers', 'Speed Dial 8', 'Connected Line Identification Restriction',
        'Integrated IMP', 'Busy Lamp Field', 'Remote Office', 'Shared Call Appearance 5',
        'Communication Barring User-Control', 'Music On Hold User', 'Directory Number Hunting', 'Flash Call Hold',
        'Call Forwarding No Answer', 'Call Forwarding Not Reachable', 'BroadTouch Business Communicator Mobile',
        'BroadTouch Business Communicator Desktop - Audio', 'Connected Line Identification Presentation',
        'Custom Ringback User - Video', 'Calling Line ID Blocking Override', 'Video On Hold User', 'Authentication',
        'BroadWorks Agent', 'Classmark', 'Hoteling Host', 'Calling Number Delivery', 'External Custom Ringback',
        'Preferred Carrier User', 'Third-Party MWI Control', 'BroadWorks Supervisor', 'Barge-in Exempt', 'Call Notify',
        'BroadTouch Business Communicator Desktop', 'Call Return', 'Priority Alert', 'Simultaneous Ring Personal',
        'Service Scripts User', 'Three-Way Call', 'Directed Call Pickup', 'N-Way Call', 'Calling Name Retrieval',
        'BroadWorks Receptionist - Small Business', 'Call Center - Premium', 'Outlook Integration', 'Attendant Console',
        'BroadWorks Receptionist - Office', 'CommPilot Call Manager', 'Custom Ringback User', 'Shared Call Appearance',
        'Group Night Forwarding', 'Custom Ringback User - Call Waiting', 'Location-Based Calling Restrictions',
        'Call Transfer', 'Voice Messaging User - Video', 'Prepaid', 'Intercept User', 'Call Center - Basic',
        'Call Forwarding Always', 'Customer Originated Trace', 'Push to Talk', 'CommPilot Express', 'Fax Messaging',
        'Call Center - Standard', 'Pre-alerting Announcement', 'Call Center Monitoring',
        'MWI Delivery to Mobile Endpoint', 'BroadWorks Anywhere', 'Privacy', 'Call Forwarding Busy',
        'Polycom Phone Services', 'Voice Messaging User', 'Call Forwarding Selective',
        'BroadTouch Business Communicator Mobile - Audio', 'Physical Location', 'BroadWorks Mobility',
    ]

    def __init__(self, url, username, password):
        self._url = url
        self._username = str(username)
        self._password = str(password)

        self._sessionId = uuid.uuid1()
        self._conn = Client(self._url, faults=True)
        #logging.basicConfig(level=logging.INFO)
        #logging.getLogger('suds.client').setLevel(logging.DEBUG)
        #print(self._conn)

    def _decodeResponseObject(self, obj):
        try:
            r = {}
            for item in list(obj):
                if len(item) == 0:
                    if item.tag in r:
                        t = r[item.tag]
                        if type(t) != list:
                            r[item.tag] = [t]
                        r[item.tag].append(item.text)
                        del t
                    else:
                        if item.text == 'true':
                            r[item.tag] = True
                        elif item.text == 'false':
                            r[item.tag] = False
                        else:
                            r[item.tag] = item.text
                else:
                    if item.tag in r:
                        t = r[item.tag]
                        if type(t) != list:
                            r[item.tag] = [t]
                        r[item.tag].append(self._decodeResponseObject(item))
                        del t
                    else:
                        r[item.tag] = self._decodeResponseObject(item)
                del item
            del obj
            return r
        except Exception as e:
            raise Exception("%s" % (e))

    def _cleanResponseTables(self, data, tables):
        try:
            for table in tables:
                if table in data:
                    colHeading = data[table]['colHeading']
                    rows = []
                    if 'row' in data[table]:
                        ''' if there is only one row we need to convert result to list so it can be processed '''
                        if type(data[table]['row']) == dict:
                            data[table]['row'] = [data[table]['row']]
                        for r in data[table]['row']:
                            row = {}
                            for i in range(0,len(colHeading)):
                                row[colHeading[i]] = r['col'][i]
                            rows.append(row)
                            del row, i
                    data[table] = rows
                    del rows, colHeading
                del table
            return data
        except Exception as e:
            raise Exception("%s" % (e))

    def _sendRequest(self, schema):
        r = {'error': False, 'type': None, 'data': None, 'request': None, 'response': None}

        request = OCIBuilder.build(schema, self._sessionId)
        if __debug__:
            print(request)
            reqTree = etree.parse(BytesIO(bytes(request, 'utf-8')))
            r['request'] = etree.tostring(reqTree, pretty_print=True)
            del reqTree
        response = self._conn.service.processOCIMessage(escape(request))
        if response is None:
            return r
        tree = etree.parse(BytesIO(bytes(response, 'utf-8')))
        if __debug__:
            r['response'] = etree.tostring(tree, pretty_print=True)
            print(r['response'].decode("utf-8"))
        command = tree.find('command')
        del request
        del response
        del tree

        r['type'] = command.get('{https://www.w3.org/2001/XMLSchema-instance}type')
        if r['type'] == 'c:ErrorResponse':
            r['error'] = True
        r['data'] = self._cleanResponseTables(self._decodeResponseObject(command), schema['tables'])
        del command

        if r['error']:
            r['exception'] = list()
            for field in ['detail', 'summaryEnglish', 'summary']:
                if field in r['data'] and r['data'][field] is not None:
                    r['exception'].append(r['data'][field])

            if len(r['exception']) == 0:
                r['exception'].append('Unknown error in the response')

        del r['error']

        return r

    def NormalizeUserId(self, user_id):
        if not self._userDomain:
            raise Exception('User Domain not set, must be logged in to normalize')
        if not '@' in user_id:
            return "{}@{}".format(user_id, self._userDomain)
        else:
            return user_id

    def GroupAccessDeviceAddRequest14(self, serviceProviderId, groupId, deviceName, deviceType, **kwargs):
        return self._sendRequest(OCISchema.GroupAccessDeviceAddRequest14(serviceProviderId=serviceProviderId,
                                                                         groupId=groupId, deviceName=deviceName,
                                                                         deviceType=deviceType, **kwargs))

    def GroupAccessDeviceCustomTagAddRequest(self, serviceProviderId, groupId, deviceName, tagName, tagValue=None):
        return self._sendRequest(OCISchema.GroupAccessDeviceCustomTagAddRequest(serviceProviderId=serviceProviderId,
                                                                                groupId=groupId, deviceName=deviceName,
                                                                                tagName=tagName, tagValue=tagValue))

    def GroupAccessDeviceCustomTagDeleteListRequest(self, serviceProviderId, groupId, deviceName, tagNames):
        return self._sendRequest(
            OCISchema.GroupAccessDeviceCustomTagDeleteListRequest(serviceProviderId=serviceProviderId, groupId=groupId,
                                                                  deviceName=deviceName, tagNames=tagNames))

    def GroupAccessDeviceCustomTagGetListRequest(self, serviceProviderId, groupId, deviceName):
        return self._sendRequest(OCISchema.GroupAccessDeviceCustomTagGetListRequest(serviceProviderId=serviceProviderId,
                                                                                    groupId=groupId, deviceName=deviceName))

    def GroupAccessDeviceCustomTagModifyRequest(self, serviceProviderId, groupId, deviceName, tagName, tagValue):
        return self._sendRequest(OCISchema.GroupAccessDeviceCustomTagModifyRequest(serviceProviderId=serviceProviderId,
                                                                                   groupId=groupId,
                                                                                   deviceName=deviceName,
                                                                                   tagName=tagName, tagValue=tagValue))

    def GroupAccessDeviceDeleteRequest(self, serviceProviderId, groupId, deviceName):
        return self._sendRequest(OCISchema.GroupAccessDeviceDeleteRequest(serviceProviderId=serviceProviderId,
                                                                          groupId=groupId, deviceName=deviceName))

    def GroupAccessDeviceFileModifyRequest14sp8(self, serviceProviderId, groupId, deviceName, fileFormat, **kwargs):
        return self._sendRequest(OCISchema.GroupAccessDeviceFileModifyRequest14sp8(serviceProviderId=serviceProviderId,
                                                                                   groupId=groupId,
                                                                                   deviceName=deviceName,
                                                                                   fileFormat=fileFormat,
                                                                                   **kwargs))

    def GroupAccessDeviceGetListRequest(self, serviceProviderId, groupId, **kwargs):
        return self._sendRequest(OCISchema.GroupAccessDeviceGetListRequest(serviceProviderId=serviceProviderId,
                                                                           groupId=groupId, **kwargs))

    def GroupAccessDeviceGetRequest18sp1(self, serviceProviderId, groupId, deviceName):
        return self._sendRequest(OCISchema.GroupAccessDeviceGetRequest18sp1(serviceProviderId=serviceProviderId,
                                                                            groupId=groupId, deviceName=deviceName))

    def GroupAccessDeviceGetUserListRequest(self, serviceProviderId, groupId, deviceName, **kwargs):
        return self._sendRequest(OCISchema.GroupAccessDeviceGetUserListRequest(serviceProviderId=serviceProviderId,
                                                                               groupId=groupId, deviceName=deviceName,
                                                                               **kwargs))

    def GroupAccessDeviceModifyRequest14(self, serviceProviderId, groupId, deviceName, **kwargs):
        return self._sendRequest(OCISchema.GroupAccessDeviceModifyRequest14(serviceProviderId=serviceProviderId,
                                                                            groupId=groupId, deviceName=deviceName,
                                                                            **kwargs))

    def GroupAccessDeviceModifyUserRequest(self, serviceProviderId, groupId, deviceName, linePort, isPrimaryLinePort):
        return self._sendRequest(OCISchema.GroupAccessDeviceModifyUserRequest(serviceProviderId=serviceProviderId,
                                                                              groupId=groupId, deviceName=deviceName,
                                                                              linePort=linePort,
                                                                              isPrimaryLinePort=isPrimaryLinePort))

    def GroupAccessDeviceResetRequest(self, serviceProviderId, groupId, deviceName):
        return self._sendRequest(OCISchema.GroupAccessDeviceResetRequest(serviceProviderId=serviceProviderId,
                                                                         groupId=groupId, deviceName=deviceName))

    def GroupAddRequest(self, serviceProviderId, groupId, userLimit, groupName, defaultDomain=None, **kwargs):
        if defaultDomain is None:
            defaultDomain = self._userDomain

        return self._sendRequest(OCISchema.GroupAddRequest(serviceProviderId=serviceProviderId, groupId=groupId,
                                                           userLimit=userLimit, groupName=groupName,
                                                           defaultDomain=defaultDomain, **kwargs))

    def GroupAdminAddRequest(self, serviceProviderId, groupId, userId, **kwargs):
        return self._sendRequest(OCISchema.GroupAdminAddRequest(serviceProviderId=serviceProviderId, groupId=groupId,
                                                                userId=userId, **kwargs))

    def GroupAdminDeleteRequest(self, userId):
        return self._sendRequest(OCISchema.GroupAdminDeleteRequest(userId=userId))

    def GroupAdminModifyRequest(self, userId, **kwargs):
        return self._sendRequest(OCISchema.GroupAdminModifyRequest(userId=userId, **kwargs))

    def GroupCallPickupAddInstanceRequest(self, serviceProviderId, groupId, name, **kwargs):
        return self._sendRequest(OCISchema.GroupCallPickupAddInstanceRequest(serviceProviderId=serviceProviderId,
                                                                             groupId=groupId, name=name, **kwargs))

    def GroupCallPickupDeleteInstanceRequest(self, serviceProviderId, groupId, name):
        return self._sendRequest(OCISchema.GroupCallPickupDeleteInstanceRequest(serviceProviderId=serviceProviderId,
                                                                                groupId=groupId, name=name))

    def GroupCallPickupGetAvailableUserListRequest(self, serviceProviderId, groupId, **kwargs):
        return self._sendRequest(OCISchema.GroupCallPickupGetAvailableUserListRequest(serviceProviderId=serviceProviderId,
                                                                                      groupId=groupId, **kwargs))

    def GroupCallPickupGetInstanceListRequest(self, serviceProviderId, groupId):
        return self._sendRequest(OCISchema.GroupCallPickupGetInstanceListRequest(serviceProviderId=serviceProviderId,
                                                                                 groupId=groupId))

    def GroupCallPickupGetInstanceRequest(self, serviceProviderId, groupId, name):
        return self._sendRequest(OCISchema.GroupCallPickupGetInstanceRequest(serviceProviderId=serviceProviderId,
                                                                             groupId=groupId, name=name))

    def GroupCallPickupModifyInstanceRequest(self, serviceProviderId, groupId, name, **kwargs):
        return self._sendRequest(OCISchema.GroupCallPickupModifyInstanceRequest(serviceProviderId=serviceProviderId,
                                                                                groupId=groupId, name=name, **kwargs))

    def GroupCallProcessingModifyPolicyRequest15sp2(self, serviceProviderId, groupId, **kwargs):
        return self._sendRequest(
            OCISchema.GroupCallProcessingModifyPolicyRequest15sp2(serviceProviderId=serviceProviderId, groupId=groupId,
                                                                  **kwargs))

    def GroupCPEConfigRebuildConfigFileRequest(self, serviceProviderId, groupId, deviceType, **kwargs):
        return self._sendRequest(OCISchema.GroupCPEConfigRebuildConfigFileRequest(serviceProviderId=serviceProviderId,
                                                                                  groupId=groupId, deviceType=deviceType,
                                                                                  **kwargs))

    def GroupCPEConfigRebuildDeviceConfigFileRequest(self, serviceProviderId, groupId, deviceName):
        return self._sendRequest(OCISchema.GroupCPEConfigRebuildDeviceConfigFileRequest(serviceProviderId=serviceProviderId,
                                                                                        groupId=groupId, deviceName=deviceName))

    def GroupCPEConfigReorderDeviceLinePortsRequest(self, serviceProviderId, groupId, deviceName, linePortList):
        return self._sendRequest(OCISchema.GroupCPEConfigReorderDeviceLinePortsRequest(
            serviceProviderId=serviceProviderId, groupId=groupId, deviceName=deviceName, linePortList=linePortList))

    def GroupCustomContactDirectoryAddRequest17(self, serviceProviderId, groupId, directory_name, entry=None):
        return self._sendRequest(OCISchema.GroupCustomContactDirectoryAddRequest17(serviceProviderId=serviceProviderId,
                                                                                   groupId=groupId,
                                                                                   directory_name=directory_name,
                                                                                   entry=entry))

    def GroupCustomContactDirectoryModifyRequest17(self, serviceProviderId, groupId, directory_name, **kwargs):
        return self._sendRequest(OCISchema.GroupCustomContactDirectoryModifyRequest17(serviceProviderId=serviceProviderId,
                                                                                      groupId=groupId,
                                                                                      directory_name=directory_name,
                                                                                      **kwargs))

    def GroupDeleteRequest(self, serviceProviderId, groupId):
        return self._sendRequest(OCISchema.GroupDeleteRequest(serviceProviderId=serviceProviderId, groupId=groupId))

    def GroupDeviceTypeCustomTagAddRequest(self, serviceProviderId, groupId, deviceType, tagName, **kwargs):
        return self._sendRequest(OCISchema.GroupDeviceTypeCustomTagAddRequest(serviceProviderId=serviceProviderId,
                                                                              groupId=groupId, deviceType=deviceType,
                                                                              tagName=tagName, **kwargs))

    def GroupDeviceTypeCustomTagDeleteListRequest(self, serviceProviderId, groupId, deviceType, tagName):
        return self._sendRequest(OCISchema.GroupDeviceTypeCustomTagDeleteListRequest(serviceProviderId=serviceProviderId,
                                                                                     groupId=groupId, deviceType=deviceType,
                                                                                     tagName=tagName))

    def GroupDeviceTypeCustomTagGetListRequest(self, serviceProviderId, groupId, deviceType):
        return self._sendRequest(OCISchema.GroupDeviceTypeCustomTagGetListRequest(serviceProviderId=serviceProviderId,
                                                                                  groupId=groupId, deviceType=deviceType))

    def GroupDeviceTypeCustomTagModifyRequest(self, serviceProviderId, groupId, deviceType, tagName, **kwargs):
        return self._sendRequest(OCISchema.GroupDeviceTypeCustomTagModifyRequest(serviceProviderId=serviceProviderId,
                                                                                 groupId=groupId, deviceType=deviceType,
                                                                                 tagName=tagName, **kwargs))

    def GroupDeviceTypeFileModifyRequest14sp8(self, serviceProviderId, groupId, deviceType, **kwargs):
        return self._sendRequest(OCISchema.GroupDeviceTypeFileModifyRequest14sp8(serviceProviderId=serviceProviderId,
                                                                                 groupId=groupId, deviceType=deviceType,
                                                                                 fileFormat=fileFormat, **kwargs))

    def GroupDnActivateListRequest(self, serviceProviderId, groupId, **kwargs):
        return self._sendRequest(OCISchema.GroupDnActivateListRequest(serviceProviderId=serviceProviderId,
                                                                      groupId=groupId, **kwargs))

    def GroupDnAssignListRequest(self, serviceProviderId, groupId, **kwargs):
        return self._sendRequest(OCISchema.GroupDnAssignListRequest(serviceProviderId=serviceProviderId,
                                                                    groupId=groupId, **kwargs))

    def GroupDnGetSummaryListRequest(self, serviceProviderId, groupId):
        return self._sendRequest(OCISchema.GroupDnGetSummaryListRequest(serviceProviderId=serviceProviderId, groupId=groupId))

    def GroupDnUnassignListRequest(self, serviceProviderId, groupId, **kwargs):
        return self._sendRequest(OCISchema.GroupDnUnassignListRequest(serviceProviderId=serviceProviderId,
                                                                      groupId=groupId, **kwargs))

    def GroupExtensionLengthModifyRequest17(self, serviceProviderId, groupId, **kwargs):
        return self._sendRequest(OCISchema.GroupExtensionLengthModifyRequest17(serviceProviderId=serviceProviderId,
                                                                               groupId=groupId, **kwargs))

    def GroupGetListInServiceProviderRequest(self, serviceProviderId, **kwargs):
        return self._sendRequest(OCISchema.GroupGetListInServiceProviderRequest(serviceProviderId=serviceProviderId,
                                                                                **kwargs))

    def GroupGetListInSystemRequest(self, **kwargs):
        return self._sendRequest(OCISchema.GroupGetListInSystemRequest(**kwargs))

    def GroupGetRequest14sp7(self, serviceProviderId, groupId):
        return self._sendRequest(OCISchema.GroupGetRequest14sp7(serviceProviderId=serviceProviderId, groupId=groupId))

    def GroupGroupPagingAddInstanceRequest(self, serviceProviderId, groupId, serviceUserId, serviceInstanceProfile,
                                           confirmationToneTimeoutSeconds, deliverOriginatorCLIDInstead, **kwargs):
        return self._sendRequest(OCISchema.GroupGroupPagingAddInstanceRequest(serviceProviderId=serviceProviderId,
                                                                              groupId=groupId,
                                                                              serviceUserId=serviceUserId,
                                                                              serviceInstanceProfile=serviceInstanceProfile,
                                                                              confirmationToneTimeoutSeconds=confirmationToneTimeoutSeconds,
                                                                              deliverOriginatorCLIDInstead=deliverOriginatorCLIDInstead,
                                                                              **kwargs))

    def GroupGroupPagingAddOriginatorListRequest(self, serviceUserId, originatorUserId):
        return self._sendRequest(OCISchema.GroupGroupPagingAddOriginatorListRequest(serviceUserId=serviceUserId,
                                                                                    originatorUserId=originatorUserId))

    def GroupGroupPagingAddTargetListRequest(self, serviceUserId, targetUserId):
        return self._sendRequest(OCISchema.GroupGroupPagingAddTargetListRequest(serviceUserId=serviceUserId,
                                                                                targetUserId=targetUserId))

    def GroupGroupPagingDeleteInstanceRequest(self, serviceUserId):
        return self._sendRequest(OCISchema.GroupGroupPagingDeleteInstanceRequest(serviceUserId=serviceUserId))

    def GroupGroupPagingModifyInstanceRequest(self, serviceUserId, **kwargs):
        return self._sendRequest(OCISchema.GroupGroupPagingModifyInstanceRequest(serviceUserId=serviceUserId, **kwargs))

    def GroupGroupPagingModifyOriginatorListRequest(self, serviceUserId, **kwargs):
        return self._sendRequest(OCISchema.GroupGroupPagingModifyOriginatorListRequest(serviceUserId=serviceUserId,
                                                                                       **kwargs))

    def GroupGroupPagingModifyTargetListRequest(self, serviceUserId, **kwargs):
        return self._sendRequest(OCISchema.GroupGroupPagingModifyTargetListRequest(serviceUserId=serviceUserId,
                                                                                   **kwargs))

    def GroupHuntGroupAddInstanceRequest19(self, serviceProviderId, groupId, serviceUserId, serviceInstanceProfile,
                                           policy, huntAfterNoAnswer, noAnswerNumberOfRings, forwardAfterTimeout,
                                           forwardTimeoutSeconds, allowCallWaitingForAgents,
                                           useSystemHuntGroupCLIDSetting, includeHuntGroupNameInCLID,
                                           enableNotReachableForwarding, makeBusyWhenNotReachable,
                                           allowMembersToControlGroupBusy, enableGroupBusy, **kwargs):
        return self._sendRequest(OCISchema.GroupHuntGroupAddInstanceRequest19(serviceProviderId=serviceProviderId,
                                                                              groupId=groupId,
                                                                              serviceUserId=serviceUserId,
                                                                              serviceInstanceProfile=serviceInstanceProfile,
                                                                              policy=policy,
                                                                              huntAfterNoAnswer=huntAfterNoAnswer,
                                                                              noAnswerNumberOfRings=noAnswerNumberOfRings,
                                                                              forwardAfterTimeout=forwardAfterTimeout,
                                                                              forwardTimeoutSeconds=forwardTimeoutSeconds,
                                                                              allowCallWaitingForAgents=allowCallWaitingForAgents,
                                                                              useSystemHuntGroupCLIDSetting=useSystemHuntGroupCLIDSetting,
                                                                              includeHuntGroupNameInCLID=includeHuntGroupNameInCLID,
                                                                              enableNotReachableForwarding=enableNotReachableForwarding,
                                                                              makeBusyWhenNotReachable=makeBusyWhenNotReachable,
                                                                              allowMembersToControlGroupBusy=allowMembersToControlGroupBusy,
                                                                              enableGroupBusy=enableGroupBusy,
                                                                              **kwargs))

    def GroupHuntGroupDeleteInstanceRequest(self, serviceUserId):
        return self._sendRequest(OCISchema.GroupHuntGroupDeleteInstanceRequest(serviceUserId=serviceUserId))

    def GroupHuntGroupModifyInstanceRequest(self, serviceUserId, **kwargs):
        return self._sendRequest(OCISchema.GroupHuntGroupModifyInstanceRequest(serviceUserId=serviceUserId, **kwargs))

    def GroupInterceptGroupGetRequest16sp1(self, serviceProviderId, groupId):
        return self._sendRequest(OCISchema.GroupInterceptGroupGetRequest16sp1(serviceProviderId=serviceProviderId, groupId=groupId))

    def GroupInterceptGroupModifyRequest16(self, serviceProviderId, groupId, **kwargs):
        return self._sendRequest(OCISchema.GroupInterceptGroupModifyRequest16(serviceProviderId=serviceProviderId,
                                                                              groupId=groupId, **kwargs))

    def GroupMeetMeConferencingModifyInstanceRequest(self, serviceUserId, **kwargs):
        return self._sendRequest(OCISchema.GroupMeetMeConferencingModifyInstanceRequest(serviceUserId=serviceUserId,
                                                                                        **kwargs))

    def GroupModifyRequest(self, serviceProviderId, groupId, **kwargs):
        return self._sendRequest(OCISchema.GroupModifyRequest(serviceProviderId=serviceProviderId, groupId=groupId,
                                                              **kwargs))

    def GroupOutgoingCallingPlanOriginatingGetListRequest(self, serviceProviderId, groupId):
        return self._sendRequest(OCISchema.GroupOutgoingCallingPlanOriginatingGetListRequest(serviceProviderId=serviceProviderId,
                                                                                             groupId=groupId))

    def GroupOutgoingCallingPlanOriginatingModifyListRequest(self, serviceProviderId, groupId, **kwargs):
        return self._sendRequest(OCISchema.GroupOutgoingCallingPlanOriginatingModifyListRequest(serviceProviderId=serviceProviderId,
                                                                                                groupId=groupId, **kwargs))

    def GroupOutgoingCallingPlanRedirectingGetListRequest(self, serviceProviderId, groupId):
        return self._sendRequest(OCISchema.GroupOutgoingCallingPlanRedirectingGetListRequest(serviceProviderId=serviceProviderId,
                                                                                             groupId=groupId))

    def GroupOutgoingCallingPlanRedirectingModifyListRequest(self, serviceProviderId, groupId, **kwargs):
        return self._sendRequest(OCISchema.GroupOutgoingCallingPlanRedirectingModifyListRequest(serviceProviderId=serviceProviderId,
                                                                                               groupId=groupId, **kwargs))

    def GroupServiceGetAuthorizationListRequest(self, serviceProviderId, groupId):
        return self._sendRequest(OCISchema.GroupServiceGetAuthorizationListRequest(
            serviceProviderId=serviceProviderId, groupId=groupId))

    def GroupServiceModifyAuthorizationListRequest(self, serviceProviderId, groupId, **kwargs):
        return self._sendRequest(OCISchema.GroupServiceModifyAuthorizationListRequest(
            serviceProviderId=serviceProviderId, groupId=groupId, **kwargs))

    def GroupServiceAssignListRequest(self, serviceProviderId, groupId, serviceName):
        return self._sendRequest(OCISchema.GroupServiceAssignListRequest(serviceProviderId=serviceProviderId,
                                                                         groupId=groupId, serviceName=serviceName))

    def GroupVoiceMessagingGroupGetRequest(self, serviceProviderId, groupId):
        return self._sendRequest(OCISchema.GroupVoiceMessagingGroupGetRequest(serviceProviderId=serviceProviderId,
                                                                              groupId=groupId))


    def GroupVoiceMessagingGroupModifyVoicePortalRequest(self, serviceProviderId, groupId, **kwargs):
        return self._sendRequest(OCISchema.GroupVoiceMessagingGroupModifyVoicePortalRequest(serviceProviderId=serviceProviderId,
                                                                                            groupId=groupId, **kwargs))

    def UserVoiceMessagingUserGetVoiceManagementRequest17(self, userId):
        return self._sendRequest(OCISchema.UserVoiceMessagingUserGetVoiceManagementRequest17(userId=userId))

    def LoginRequest14sp4(self):
        auth = self._sendRequest(OCISchema.AuthenticationRequest(userId=self._username))
        if auth:
            secretHash = hashlib.sha1()
            secretHash.update(bytes(self._password, 'utf-8'))
            secret = secretHash.hexdigest()
            signedPasswordHash = hashlib.md5()
            signedPasswordHash.update(bytes("{}:{}".format(auth['data']['nonce'], secret), 'utf-8'))
            signedPassword = signedPasswordHash.hexdigest()
            resp = self._sendRequest(OCISchema.LoginRequest14sp4(self._username, signedPassword))

            self._userDomain = resp['data']['userDomain']
            self._locale = resp['data']['locale']
            self._encoding = resp['data']['encoding']
            self._loginType = resp['data']['loginType']
            self._passwordExpiresDays = resp['data']['passwordExpiresDays']

            if int(self._passwordExpiresDays) < 30:
                warnings.warn('Password expires in less than 30 days', UserWarning)

            return auth
        else:
            raise Exception('AuthenticationRequest failed')

    def LogoutRequest(self):
        resp = self._sendRequest(OCISchema.LogoutRequest(userId=self._username))
        if resp is None:
            # success!
            self._sessionId = None
        return resp

    def ServiceProviderAccessDeviceAddRequest14(self, serviceProviderId, deviceName, deviceType, **kwargs):
        return self._sendRequest(OCISchema.ServiceProviderAccessDeviceAddRequest14(serviceProviderId=serviceProviderId,
                                                                                   deviceName=deviceName, deviceType=deviceType,
                                                                                   **kwargs))

    def ServiceProviderAccessDeviceDeleteRequest(self, serviceProviderId, deviceName):
        return self._sendRequest(OCISchema.ServiceProviderAccessDeviceDeleteRequest(serviceProviderId=serviceProviderId,
                                                                                    deviceName=deviceName))

    def ServiceProviderAccessDeviceGetRequest18sp1(self, serviceProviderId, deviceName):
        return self._sendRequest(OCISchema.ServiceProviderAccessDeviceGetRequest18sp1(serviceProviderId=serviceProviderId, deviceName=deviceName))

    def ServiceProviderAccessDeviceGetUserListRequest(self, serviceProviderId, deviceName, **kwargs):
        return self._sendRequest(OCISchema.ServiceProviderAccessDeviceGetUserListRequest(serviceProviderId=serviceProviderId, deviceName=deviceName, **kwargs))

    def ServiceProviderAccessDeviceCustomTagAddRequest(self, serviceProviderId, deviceName, tagName, **kwargs):
        return self._sendRequest(OCISchema.ServiceProviderAccessDeviceCustomTagAddRequest(serviceProviderId=serviceProviderId, deviceName=deviceName, tagName=tagName, **kwargs))

    def ServiceProviderAccessDeviceCustomTagDeleteListRequest(self, serviceProviderId, deviceName, tagName):
        return self._sendRequest(OCISchema.ServiceProviderAccessDeviceCustomTagDeleteListRequest(serviceProviderId=serviceProviderId, deviceName=deviceName, tagName=tagName))

    def ServiceProviderAccessDeviceCustomTagGetListRequest(self, serviceProviderId, deviceName):
        return self._sendRequest(OCISchema.ServiceProviderAccessDeviceCustomTagGetListRequest(serviceProviderId=serviceProviderId, deviceName=deviceName))

    def ServiceProviderAccessDeviceCustomTagModifyRequest(self, serviceProviderId, deviceName, tagName, **kwargs):
        return self._sendRequest(OCISchema.ServiceProviderAccessDeviceCustomTagModifyRequest(serviceProviderId=serviceProviderId, deviceName=deviceName, tagName=tagName, **kwargs))

    def ServiceProviderAccessDeviceModifyUserRequest(self, serviceProviderId, deviceName, linePort, isPrimaryLinePort):
        return self._sendRequest(OCISchema.ServiceProviderAccessDeviceModifyUserRequest(serviceProviderId=serviceProviderId, deviceName=deviceName, linePort=linePort, isPrimaryLinePort=isPrimaryLinePort))

    def ServiceProviderAccessDeviceResetRequest(self, serviceProviderId, deviceName):
        return self._sendRequest(OCISchema.ServiceProviderAccessDeviceResetRequest(serviceProviderId=serviceProviderId, deviceName=deviceName))

    def ServiceProviderAddRequest13mp2(self, serviceProviderId, serviceProviderName, defaultDomain=None, **kwargs):
        if defaultDomain is None:
            defaultDomain = self._userDomain

        return self._sendRequest(
            OCISchema.ServiceProviderAddRequest13mp2(serviceProviderId=serviceProviderId,
                                                     serviceProviderName=serviceProviderName,
                                                     defaultDomain=defaultDomain, **kwargs))

    def ServiceProviderCallProcessingModifyPolicyRequest15(self, serviceProviderId, **kwargs):
        return self._sendRequest(OCISchema.ServiceProviderCallProcessingModifyPolicyRequest15(serviceProviderId=serviceProviderId, **kwargs))

    def ServiceProviderCPEConfigRebuildDeviceConfigFileRequest(self, serviceProviderId, deviceName):
        return self._sendRequest(OCISchema.ServiceProviderCPEConfigRebuildDeviceConfigFileRequest(serviceProviderId=serviceProviderId, deviceName=deviceName))

    def ServiceProviderDeleteRequest(self, serviceProviderId):
        return self._sendRequest(OCISchema.ServiceProviderDeleteRequest(serviceProviderId=serviceProviderId))

    def ServiceProviderDnAddListRequest(self, serviceProviderId, **kwargs):
        return self._sendRequest(OCISchema.ServiceProviderDnAddListRequest(serviceProviderId=serviceProviderId,
                                                                           **kwargs))

    def ServiceProviderDnDeleteListRequest(self, serviceProviderId, **kwargs):
        return self._sendRequest(OCISchema.ServiceProviderDnDeleteListRequest(serviceProviderId=serviceProviderId,
                                                                              **kwargs))

    def ServiceProviderDnGetSummaryListRequest(self, serviceProviderId):
        return self._sendRequest(OCISchema.ServiceProviderDnGetSummaryListRequest(serviceProviderId=serviceProviderId))

    def ServiceProviderGetListRequest(self, **kwargs):
        return self._sendRequest(OCISchema.ServiceProviderGetListRequest(**kwargs))

    def ServiceProviderGetRequest17sp1(self, serviceProviderId):
        return self._sendRequest(OCISchema.ServiceProviderGetRequest17sp1(serviceProviderId=serviceProviderId))

    def ServiceProviderServiceGetAuthorizationListRequest(self, serviceProviderId):
        return self._sendRequest(OCISchema.ServiceProviderServiceGetAuthorizationListRequest(
            serviceProviderId=serviceProviderId))

    def ServiceProviderServiceModifyAuthorizationListRequest(self, serviceProviderId, **kwargs):
        return self._sendRequest(OCISchema.ServiceProviderServiceModifyAuthorizationListRequest(
            serviceProviderId=serviceProviderId, **kwargs))

    def ServiceProviderServicePackAddRequest(self, serviceProviderId, servicePackName, isAvailableForUse,
                                             servicePackQuantity, *args, **kwargs):
        return self._sendRequest(OCISchema.ServiceProviderServicePackAddRequest(serviceProviderId=serviceProviderId,
                                                                                servicePackName=servicePackName,
                                                                                isAvailableForUse=isAvailableForUse,
                                                                                servicePackQuantity=servicePackQuantity,
                                                                                **kwargs))

    def ServiceProviderServicePackGetDetailListRequest(self, serviceProviderId, servicePackName):
        return self._sendRequest(OCISchema.ServiceProviderServicePackGetDetailListRequest(serviceProviderId=serviceProviderId,
                                                                                          servicePackName=servicePackName))

    def ServiceProviderServicePackGetListRequest(self, serviceProviderId):
        return self._sendRequest(OCISchema.ServiceProviderServicePackGetListRequest(serviceProviderId))

    def SystemAccessDeviceGetAllRequest(self, **kwargs):
        return self._sendRequest(OCISchema.SystemAccessDeviceGetAllRequest(**kwargs))

    def SystemAccessDeviceTypeGetListRequest(self):
        return self._sendRequest(OCISchema.SystemAccessDeviceTypeGetListRequest())

    def SystemDeviceTypeGetRequest19(self, device_type):
        return self._sendRequest(OCISchema.SystemDeviceTypeGetRequest19(device_type=device_type))

    def SystemSIPDeviceTypeFileAddRequest20(self, device_type, file_format, remote_file_format, file_category, file_customization, file_source, use_http_digest_authentication, mac_based_file_authentication, user_name_password_file_authentication, mac_in_non_request_uri, allow_http, allow_https, allow_tftp, enable_caching, allow_upload_from_device, **kwargs):
        return self._sendRequest(OCISchema.SystemSIPDeviceTypeFileAddRequest20(device_type, file_format, remote_file_format, file_category, file_customization, file_source, use_http_digest_authentication, mac_based_file_authentication, user_name_password_file_authentication, mac_in_non_request_uri, allow_http, allow_https, allow_tftp, enable_caching, allow_upload_from_device, **kwargs))

    def SystemSIPDeviceTypeFileGetListRequest14sp8(self, device_type):
        return self._sendRequest(OCISchema.SystemSIPDeviceTypeFileGetListRequest14sp8(device_type))

    def SystemSIPDeviceTypeFileGetRequest20(self, device_type, file_format):
        return self._sendRequest(OCISchema.SystemSIPDeviceTypeFileGetRequest20(device_type, file_format))

    def SystemSIPDeviceTypeFileModifyRequest16sp1(self, device_type, file_format, **kwargs):
        return self._sendRequest(OCISchema.SystemSIPDeviceTypeFileModifyRequest16sp1(device_type, file_format, **kwargs))

    def SystemSoftwareVersionGetRequest(self):
        return self._sendRequest(OCISchema.SystemSoftwareVersionGetRequest())

    def UserAccessDeviceResetRequest(self, userId, accessDevice):
        return self._sendRequest(OCISchema.UserAccessDeviceResetRequest(userId=userId, accessDevice=accessDevice))

    def UserAddRequest17sp4(self, serviceProviderId, groupId, userId, lastName, firstName, callingLineIdLastName,
                            callingLineIdFirstName, **kwargs):
        if not '@' in userId:
            userId = "{}@{}".format(userId, self._userDomain)
        return self._sendRequest(OCISchema.UserAddRequest17sp4(serviceProviderId=serviceProviderId, groupId=groupId,
                                                               userId=userId, lastName=lastName, firstName=firstName,
                                                               callingLineIdLastName=callingLineIdLastName,
                                                               callingLineIdFirstName=callingLineIdFirstName, **kwargs))

    def UserAssignedServicesGetListRequest(self, userId):
        return self._sendRequest(OCISchema.UserAssignedServicesGetListRequest(userId=userId))

    def UserAuthenticationModifyRequest(self, userId, **kwargs):
        if userId is not None and not '@' in userId:
            userId = "{}@{}".format(userId, self._userDomain)
        return self._sendRequest(OCISchema.UserAuthenticationModifyRequest(userId=userId, **kwargs))

    def UserBusyLampFieldGetRequest16sp2(self, userId):
        return self._sendRequest(OCISchema.UserBusyLampFieldGetRequest16sp2(userId=userId))

    def UserBusyLampFieldModifyRequest(self, userId, **kwargs):
        return self._sendRequest(OCISchema.UserBusyLampFieldModifyRequest(userId=userId, **kwargs))

    def UserCallForwardingAlwaysModifyRequest(self, userId, **kwargs):
        return self._sendRequest(OCISchema.UserCallForwardingAlwaysModifyRequest(userId=userId, **kwargs))

    def UserCallPickupGetRequest(self, userId):
        return self._sendRequest(OCISchema.UserCallPickupGetRequest(userId=userId))

    def UserCallProcessingModifyPolicyRequest14sp7(self, userId, **kwargs):
        return self._sendRequest(OCISchema.UserCallProcessingModifyPolicyRequest14sp7(userId=userId, **kwargs))

    def UserCombinedGetRequest22(self, userId, **kwargs):
        return self._sendRequest(OCISchema.UserCombinedGetRequest22(userId=userId, **kwargs))

    def UserCombinedModifyRequest(self, userId, **kwargs):
        return self._sendRequest(OCISchema.UserCombinedModifyRequest(userId=userId, **kwargs))

    def UserDeleteRequest(self, userId):
        if not '@' in userId:
            userId = "{}@{}".format(userId, self._userDomain)
        return self._sendRequest(OCISchema.UserDeleteRequest(userId=userId))

    def UserGetListInGroupRequest(self, serviceProviderId, groupId, **kwargs):
        return self._sendRequest(OCISchema.UserGetListInGroupRequest(serviceProviderId=serviceProviderId,
                                                                     groupId=groupId, **kwargs))

    def UserGetListInServiceProviderRequest(self, serviceProviderId, **kwargs):
        return self._sendRequest(OCISchema.UserGetListInServiceProviderRequest(serviceProviderId=serviceProviderId,
                                                                               **kwargs))

    def UserGetListInSystemRequest(self, **kwargs):
        return self._sendRequest(OCISchema.UserGetListInSystemRequest(**kwargs))

    def UserGetRegistrationListRequest(self, userId):
        if not '@' in userId:
            userId = "{}@{}".format(userId, self._userDomain)
        return self._sendRequest(OCISchema.UserGetRegistrationListRequest(userId=userId))

    def UserGetRequest19(self, userId):
        if not '@' in userId:
            userId = "{}@{}".format(userId, self._userDomain)
        return self._sendRequest(OCISchema.UserGetRequest19(userId=userId))

    def UserGetServiceInstanceListInSystemRequest(self, **kwargs):
        return self._sendRequest(OCISchema.UserGetServiceInstanceListInSystemRequest(**kwargs))

    def UserIntegratedIMPModifyRequest(self, userId, isActive):
        return self._sendRequest(OCISchema.UserIntegratedIMPModifyRequest(userId=userId, isActive=isActive))

    def UserInterceptUserGetRequest16sp1(self, userId):
        return self._sendRequest(OCISchema.UserInterceptUserGetRequest16sp1(userId=userId))

    def UserInterceptUserModifyRequest16(self, userId, **kwargs):
        return self._sendRequest(OCISchema.UserInterceptUserModifyRequest16(userId=userId, **kwargs))

    def UserLinePortGetListRequest(self, userId):
        return self._sendRequest(OCISchema.UserLinePortGetListRequest(userId=userId))

    def UserModifyRequest17sp4(self, userId, **kwargs):
        if userId is not None and not '@' in userId:
            userId = "{}@{}".format(userId, self._userDomain)
        return self._sendRequest(OCISchema.UserModifyRequest17sp4(userId=userId, **kwargs))

    def UserModifyUserIdRequest(self, userId, newUserId):
        if not '@' in userId:
            userId = "{}@{}".format(userId, self._userDomain)
        if not '@' in newUserId:
            newUserId = "{}@{}".format(newUserId, self._userDomain)
        return self._sendRequest(OCISchema.UserModifyUserIdRequest(userId=userId, newUserId=newUserId))

    def UserOutgoingCallingPlanOriginatingGetRequest(self, userId):
        return self._sendRequest(OCISchema.UserOutgoingCallingPlanOriginatingGetRequest(userId=userId))

    def UserOutgoingCallingPlanOriginatingModifyRequest(self, userId, **kwargs):
        return self._sendRequest(OCISchema.UserOutgoingCallingPlanOriginatingModifyRequest(userId=userId, **kwargs))

    def UserOutgoingCallingPlanRedirectingGetRequest(self, userId):
        return self._sendRequest(OCISchema.UserOutgoingCallingPlanRedirectingGetRequest(userId=userId))

    def UserOutgoingCallingPlanRedirectingModifyRequest(self, userId, **kwargs):
        return self._sendRequest(OCISchema.UserOutgoingCallingPlanRedirectingModifyRequest(userId=userId, **kwargs))

    def UserPolycomPhoneServicesModifyRequest(self, userId, accessDevice, **kwargs):
        return self._sendRequest(OCISchema.UserPolycomPhoneServicesModifyRequest(userId=userId,
                                                                                 accessDevice=accessDevice, **kwargs))

    def UserPortalPasscodeModifyRequest(self, userId, newPasscode, **kwargs):
        return self._sendRequest(OCISchema.UserPortalPasscodeModifyRequest(userId=userId, newPasscode=newPasscode,
                                                                           **kwargs))

    def UserPushToTalkModifyRequest(self, userId, **kwargs):
        return self._sendRequest(OCISchema.UserPushToTalkModifyRequest(userId=userId, **kwargs))

    def UserSharedCallAppearanceAddEndpointRequest14sp2(self, userId, accessDeviceEndpoint, isActive, allowOrigination,
                                                        allowTermination):
        return self._sendRequest(OCISchema.UserSharedCallAppearanceAddEndpointRequest14sp2(userId=userId,
                                                                                           accessDeviceEndpoint=accessDeviceEndpoint,
                                                                                           isActive=isActive,
                                                                                           allowOrigination=allowOrigination,
                                                                                           allowTermination=allowTermination))

    def UserSharedCallAppearanceDeleteEndpointListRequest14(self, userId, accessDeviceEndpoint):
        return self._sendRequest(OCISchema.UserSharedCallAppearanceDeleteEndpointListRequest14(userId=userId,
                                                                                               accessDeviceEndpoint=accessDeviceEndpoint))

    def UserSharedCallAppearanceGetRequest16sp2(self, userId):
        return self._sendRequest(OCISchema.UserSharedCallAppearanceGetRequest16sp2(userId=userId))

    def UserSharedCallAppearanceModifyRequest(self, userId, **kwargs):
        return self._sendRequest(OCISchema.UserSharedCallAppearanceModifyRequest(userId=userId, **kwargs))

    def UserServiceAssignListRequest(self, userId, **kwargs):
        return self._sendRequest(OCISchema.UserServiceAssignListRequest(userId=userId, **kwargs))

    def UserServiceGetAssignmentListRequest(self, userId):
        return self._sendRequest(OCISchema.UserServiceGetAssignmentListRequest(userId=userId))

    def UserServiceUnassignListRequest(self, userId, **kwargs):
        return self._sendRequest(OCISchema.UserServiceUnassignListRequest(userId=userId, **kwargs))

    def UserSpeedDial100AddListRequest(self, userId, **kwargs):
        return self._sendRequest(OCISchema.UserSpeedDial100AddListRequest(userId=userId, **kwargs))

    def UserSpeedDial100GetListRequest17sp1(self, userId):
        return self._sendRequest(OCISchema.UserSpeedDial100GetListRequest17sp1(userId=userId))

    def UserSpeedDial100ModifyListRequest(self, userId, **kwargs):
        return self._sendRequest(OCISchema.UserSpeedDial100ModifyListRequest(userId=userId, **kwargs))

    def UserThirdPartyVoiceMailSupportModifyRequest(self, userId, **kwargs):
        return self._sendRequest(OCISchema.UserThirdPartyVoiceMailSupportModifyRequest(userId=userId, **kwargs))

    def UserVoiceMessagingUserModifyAdvancedVoiceManagementRequest(self, userId, **kwargs):
        return self._sendRequest(OCISchema.UserVoiceMessagingUserModifyAdvancedVoiceManagementRequest(userId=userId,
                                                                                                      **kwargs))

    def UserVoiceMessagingUserModifyVoiceManagementRequest(self, userId, **kwargs):
        return self._sendRequest(OCISchema.UserVoiceMessagingUserModifyVoiceManagementRequest(userId=userId, **kwargs))


class OCISchema:

    @staticmethod
    def AuthenticationRequest(userId):
        name = 'AuthenticationRequest'
        elements = {
            'userId': userId
        }
        tables = []
        return locals()

    @staticmethod
    def GroupAccessDeviceAddRequest14(serviceProviderId, groupId, deviceName, deviceType, **kwargs):
        name = 'GroupAccessDeviceAddRequest14'
        elements = OrderedDict()
        elements['serviceProviderId'] = serviceProviderId
        elements['groupId'] = groupId
        elements['deviceName'] = deviceName
        elements['deviceType'] = deviceType
        if kwargs.get('macAddress') is not None:
            elements['macAddress'] = kwargs['macAddress']
        if kwargs.get('username') is not None and kwargs.get('password') is not None:
            creds = OrderedDict()
            creds['userName'] = kwargs['username']
            creds['password'] = kwargs['password']
            elements['useCustomUserNamePassword'] = True
            elements['accessDeviceCredentials'] = creds
        tables = []
        return locals()

    @staticmethod
    def GroupAccessDeviceCustomTagAddRequest(serviceProviderId, groupId, deviceName, tagName, tagValue=None):
        name = 'GroupAccessDeviceCustomTagAddRequest'
        elements = OrderedDict()
        elements['serviceProviderId'] = serviceProviderId
        elements['groupId'] = groupId
        elements['deviceName'] = deviceName
        elements['tagName'] = tagName
        if tagValue is not None:
            elements['tagValue'] = tagValue
        tables = []
        return locals()

    @staticmethod
    def GroupAccessDeviceCustomTagDeleteListRequest(serviceProviderId, groupId, deviceName, tagNames):
        if tagNames is None:
            raise Exception('tagNames must be defined')
        name = 'GroupAccessDeviceCustomTagDeleteListRequest'
        elements = OrderedDict()
        elements['serviceProviderId'] = serviceProviderId
        elements['groupId'] = groupId
        elements['deviceName'] = deviceName
        elements['tagName'] = tagNames
        tables = []
        return locals()

    @staticmethod
    def GroupAccessDeviceCustomTagGetListRequest(serviceProviderId, groupId, deviceName):
        name = 'GroupAccessDeviceCustomTagGetListRequest'
        elements = OrderedDict()
        elements['serviceProviderId'] = serviceProviderId
        elements['groupId'] = groupId
        elements['deviceName'] = deviceName
        tables = ['deviceCustomTagsTable']
        return locals()

    @staticmethod
    def GroupAccessDeviceCustomTagModifyRequest(serviceProviderId, groupId, deviceName, tagName, tagValue):
        name = 'GroupAccessDeviceCustomTagModifyRequest'
        elements = OrderedDict()
        elements['serviceProviderId'] = serviceProviderId
        elements['groupId'] = groupId
        elements['deviceName'] = deviceName
        elements['tagName'] = tagName
        elements['tagValue'] = tagValue
        tables = []
        return locals()

    @staticmethod
    def GroupAccessDeviceDeleteRequest(serviceProviderId, groupId, deviceName):
        name = 'GroupAccessDeviceDeleteRequest'
        elements = OrderedDict()
        elements['serviceProviderId'] = serviceProviderId
        elements['groupId'] = groupId
        elements['deviceName'] = deviceName
        tables = []
        return locals()

    @staticmethod
    def GroupAccessDeviceFileModifyRequest14sp8(serviceProviderId, groupId, deviceName, fileFormat, **kwargs):
        name = 'GroupAccessDeviceFileModifyRequest14sp8'
        elements = OrderedDict()
        elements['serviceProviderId'] = serviceProviderId
        elements['groupId'] = groupId
        elements['deviceName'] = deviceName
        elements['fileFormat'] = fileFormat
        if kwargs.get('fileSource') is not None:
            elements['fileSource'] = kwargs['fileSource']
        if kwargs.get('uploadFile') is not None:
            elements['uploadFile'] = kwargs['uploadFile']
        if kwargs.get('extendedCaptureEnabled') is not None:
            elements['extendedCaptureEnabled'] = kwargs['extendedCaptureEnabled']
        tables = []
        return locals()

    @staticmethod
    def GroupAccessDeviceGetListRequest(serviceProviderId, groupId, **kwargs):
        name = 'GroupAccessDeviceGetListRequest'
        elements = OrderedDict()
        elements['serviceProviderId'] = serviceProviderId
        elements['groupId'] = groupId
        if kwargs.get('responseSizeLimit') is not None:
            elements['responseSizeLimit'] = kwargs['responseSizeLimit']
        if kwargs.get('searchCriteriaDeviceName') is not None:
            elements['searchCriteriaDeviceName'] = kwargs['searchCriteriaDeviceName']
        if kwargs.get('searchCriteriaDeviceMACAddress') is not None:
            elements['searchCriteriaDeviceMACAddress'] = kwargs['searchCriteriaDeviceMACAddress']
        if kwargs.get('searchCriteriaDeviceNetAddress') is not None:
            elements['searchCriteriaDeviceNetAddress'] = kwargs['searchCriteriaDeviceNetAddress']
        if kwargs.get('searchCriteriaExactDeviceType') is not None:
            elements['searchCriteriaExactDeviceType'] = kwargs['searchCriteriaExactDeviceType']
        if kwargs.get('searchCriteriaAccessDeviceVersion') is not None:
            elements['searchCriteriaAccessDeviceVersion'] = kwargs['searchCriteriaAccessDeviceVersion']
        tables = ['accessDeviceTable']
        return locals()

    @staticmethod
    def GroupAccessDeviceGetRequest18sp1(serviceProviderId, groupId, deviceName):
        name = 'GroupAccessDeviceGetRequest18sp1'
        elements = OrderedDict()
        elements['serviceProviderId'] = serviceProviderId
        elements['groupId'] = groupId
        elements['deviceName'] = deviceName
        tables = []
        return locals()

    @staticmethod
    def GroupAccessDeviceGetUserListRequest(serviceProviderId, groupId, deviceName, **kwargs):
        name = 'GroupAccessDeviceGetUserListRequest'
        elements = OrderedDict()
        elements['serviceProviderId'] = serviceProviderId
        elements['groupId'] = groupId
        elements['deviceName'] = deviceName
        if kwargs.get('responseSizeLimit') is not None:
            elements['responseSizeLimit'] = kwargs['responseSizeLimit']
        if kwargs.get('searchCriteriaLinePortUserPart') is not None:
            elements['searchCriteriaLinePortUserPart'] = kwargs['searchCriteriaLinePortUserPart']
        if kwargs.get('searchCriteriaLinePortDomain') is not None:
            elements['searchCriteriaLinePortDomain'] = kwargs['searchCriteriaLinePortDomain']
        if kwargs.get('searchCriteriaUserLastName') is not None:
            elements['searchCriteriaUserLastName'] = kwargs['searchCriteriaUserLastName']
        if kwargs.get('searchCriteriaUserFirstName') is not None:
            elements['searchCriteriaUserFirstName'] = kwargs['searchCriteriaUserFirstName']
        if kwargs.get('searchCriteriaDn') is not None:
            elements['searchCriteriaDn'] = kwargs['searchCriteriaDn']
        if kwargs.get('searchCriteriaUserId') is not None:
            elements['searchCriteriaUserId'] = kwargs['searchCriteriaUserId']
        if kwargs.get('searchCriteriaExactEndpointType') is not None:
            elements['searchCriteriaExactEndpointType'] = kwargs['searchCriteriaExactEndpointType']
        if kwargs.get('searchCriteriaExactUserType') is not None:
            elements['searchCriteriaExactUserType'] = kwargs['searchCriteriaExactUserType']
        if kwargs.get('searchCriteriaExtension') is not None:
            elements['searchCriteriaExtension'] = kwargs['searchCriteriaExtension']
        if kwargs.get('searchCriteriaExactUserDepartment') is not None:
            elements['searchCriteriaExactUserDepartment'] = kwargs['searchCriteriaExactUserDepartment']
        if kwargs.get('searchCriteriaExactPortNumber') is not None:
            elements['searchCriteriaExactPortNumber'] = kwargs['searchCriteriaExactPortNumber']
        tables = ['deviceUserTable']
        return locals()

    @staticmethod
    def GroupAccessDeviceModifyRequest14(serviceProviderId, groupId, deviceName, **kwargs):
        name = 'GroupAccessDeviceModifyRequest14'
        elements = OrderedDict()
        elements['serviceProviderId'] = serviceProviderId
        elements['groupId'] = groupId
        elements['deviceName'] = deviceName
        if kwargs.get('deviceType') is not None:
            elements['deviceType'] = kwargs['deviceType']
        if kwargs.get('macAddress') is not None:
            elements['macAddress'] = kwargs['macAddress']
        if kwargs.get('username') is not None and kwargs.get('password') is not None:
            creds = OrderedDict()
            creds['userName'] = kwargs['username']
            creds['password'] = kwargs['password']
            elements['useCustomUserNamePassword'] = True
            elements['accessDeviceCredentials'] = creds
        tables = []
        return locals()

    @staticmethod
    def GroupAccessDeviceModifyUserRequest(serviceProviderId, groupId, deviceName, linePort, isPrimaryLinePort):
        name = 'GroupAccessDeviceModifyUserRequest'
        elements = OrderedDict()
        elements['serviceProviderId'] = serviceProviderId
        elements['groupId'] = groupId
        elements['deviceName'] = deviceName
        elements['linePort'] = linePort
        elements['isPrimaryLinePort'] = isPrimaryLinePort
        tables = []
        return locals()

    @staticmethod
    def GroupAccessDeviceResetRequest(serviceProviderId, groupId, deviceName):
        name = 'GroupAccessDeviceResetRequest'
        elements = OrderedDict()
        elements['serviceProviderId'] = serviceProviderId
        elements['groupId'] = groupId
        elements['deviceName'] = deviceName
        tables = []
        return locals()

    @staticmethod
    def GroupAddRequest(serviceProviderId, groupId, defaultDomain, userLimit, groupName, **kwargs):
        name = 'GroupAddRequest'
        elements = OrderedDict()
        elements['serviceProviderId'] = serviceProviderId
        elements['groupId'] = groupId
        elements['defaultDomain'] = defaultDomain
        elements['userLimit'] = userLimit
        if groupName is not None:
            elements['groupName'] = groupName
        if kwargs.get('callingLineIdName') is not None:
            elements['callingLineIdName'] = kwargs['callingLineIdName']
        if kwargs.get('timeZone') is not None:
            elements['timeZone'] = kwargs['timeZone']
        if kwargs.get('locationDialingCode') is not None:
            elements['locationDialingCode'] = kwargs['locationDialingCode']
        tables = []
        return locals()

    @staticmethod
    def GroupAdminAddRequest(serviceProviderId, groupId, userId, **kwargs):
        name = 'GroupAdminAddRequest'
        elements = OrderedDict()
        elements['serviceProviderId'] = serviceProviderId
        elements['groupId'] = groupId
        elements['userId'] = userId
        if kwargs.get('firstName') is not None:
            elements['firstName'] = kwargs['firstName']
        if kwargs.get('lastName') is not None:
            elements['lastName'] = kwargs['lastName']
        if kwargs.get('password') is not None:
            elements['password'] = kwargs['password']
        if kwargs.get('language') is not None:
            elements['language'] = kwargs['language']
        tables = []
        return locals()

    @staticmethod
    def GroupAdminDeleteRequest(userId):
        name = 'GroupAdminDeleteRequest'
        elements = OrderedDict()
        elements['userId'] = userId
        tables = []
        return locals()

    @staticmethod
    def GroupAdminModifyRequest(userId, **kwargs):
        name = 'GroupAdminModifyRequest'
        elements = OrderedDict()
        elements['userId'] = userId
        if kwargs.get('firstName') is not None:
            elements['firstName'] = kwargs['firstName']
        if kwargs.get('lastName') is not None:
            elements['lastName'] = kwargs['lastName']
        if kwargs.get('password') is not None:
            elements['password'] = kwargs['password']
        if kwargs.get('language') is not None:
            elements['language'] = kwargs['language']
        tables = []
        return locals()

    @staticmethod
    def GroupCallPickupAddInstanceRequest(serviceProviderId, groupId, name, **kwargs):
        _name = name
        name = 'GroupCallPickupAddInstanceRequest'
        elements = OrderedDict()
        elements['serviceProviderId'] = serviceProviderId
        elements['groupId'] = groupId
        elements['name'] = _name
        del(_name)
        if 'userId' in kwargs:
            elements['userId'] = kwargs['userId']
        tables = []
        return locals()

    @staticmethod
    def GroupCallPickupDeleteInstanceRequest(serviceProviderId, groupId, name):
        name = 'GroupCallPickupDeleteInstanceRequest'
        elements = OrderedDict()
        elements['serviceProviderId'] = serviceProviderId
        elements['groupId'] = groupId
        elements['name'] = name
        tables = []
        return locals()

    @staticmethod
    def GroupCallPickupGetAvailableUserListRequest(serviceProviderId, groupId, **kwargs):
        name = 'GroupCallPickupGetAvailableUserListRequest'
        elements = OrderedDict()
        elements['serviceProviderId'] = serviceProviderId
        elements['groupId'] = groupId
        if 'name' in kwargs:
            elements['name'] = kwargs['name']
        if 'responseSizeLimit' in kwargs:
            elements['responseSizeLimit'] = kwargs['responseSizeLimit']
        if 'searchCriteriaUserLastName' in kwargs:
            elements['searchCriteriaUserLastName'] = kwargs['searchCriteriaUserLastName']
        if 'searchCriteriaUserFirstName' in kwargs:
            elements['searchCriteriaUserFirstName'] = kwargs['searchCriteriaUserFirstName']
        if 'searchCriteriaExactUserDepartment' in kwargs:
            elements['searchCriteriaExactUserDepartment'] = kwargs['searchCriteriaExactUserDepartment']
        if 'searchCriteriaUserId' in kwargs:
            elements['searchCriteriaUserId'] = kwargs['searchCriteriaUserId']
        if 'searchCriteriaDn' in kwargs:
            elements['searchCriteriaDn'] = kwargs['searchCriteriaDn']
        if 'searchCriteriaExtension' in kwargs:
            elements['searchCriteriaExtension'] = kwargs['searchCriteriaExtension']
        tables = ['userTable']
        return locals()

    @staticmethod
    def GroupCallPickupGetInstanceListRequest(serviceProviderId, groupId):
        name = 'GroupCallPickupGetInstanceListRequest'
        elements = OrderedDict()
        elements['serviceProviderId'] = serviceProviderId
        elements['groupId'] = groupId
        tables = []
        return locals()

    @staticmethod
    def GroupCallPickupGetInstanceRequest(serviceProviderId, groupId, name):
        name = 'GroupCallPickupGetInstanceRequest'
        elements = OrderedDict()
        elements['serviceProviderId'] = serviceProviderId
        elements['groupId'] = groupId
        elements['name'] = name
        tables = ['userTable']
        return locals()

    @staticmethod
    def GroupCallPickupModifyInstanceRequest(serviceProviderId, groupId, name, **kwargs):
        name = 'GroupCallPickupAddInstanceRequest'
        elements = OrderedDict()
        elements['serviceProviderId'] = serviceProviderId
        elements['groupId'] = groupId
        elements['name'] = name
        if 'newName' in kwargs:
            elements['newName'] = kwargs['newName']
        if 'userIdList' in kwargs:
            elements['userIdList'] = kwargs['userIdList']
        tables = []
        return locals()

    @staticmethod
    def GroupCallProcessingModifyPolicyRequest15sp2(serviceProviderId, groupId, **kwargs):
        name = 'GroupCallProcessingModifyPolicyRequest15sp2'
        elements = OrderedDict()
        elements['serviceProviderId'] = serviceProviderId
        elements['groupId'] = groupId
        if kwargs.get('useGroupCLIDSetting') is not None:
            elements['useGroupCLIDSetting'] = kwargs['useGroupCLIDSetting']
        if kwargs.get('useGroupMediaSetting') is not None:
            elements['useGroupMediaSetting'] = kwargs['useGroupMediaSetting']
        if kwargs.get('useGroupCallLimitsSetting') is not None:
            elements['useGroupCallLimitsSetting'] = kwargs['useGroupCallLimitsSetting']
        if kwargs.get('useGroupTranslationRoutingSetting') is not None:
            elements['useGroupTranslationRoutingSetting'] = kwargs['useGroupTranslationRoutingSetting']
        if kwargs.get('useMaxSimultaneousCalls') is not None:
            elements['useMaxSimultaneousCalls'] = kwargs['useMaxSimultaneousCalls']
        if kwargs.get('maxSimultaneousCalls') is not None:
            elements['maxSimultaneousCalls'] = kwargs['maxSimultaneousCalls']
        if kwargs.get('useMaxSimultaneousVideoCalls') is not None:
            elements['useMaxSimultaneousVideoCalls'] = kwargs['useMaxSimultaneousVideoCalls']
        if kwargs.get('maxSimultaneousVideoCalls') is not None:
            elements['maxSimultaneousVideoCalls'] = kwargs['maxSimultaneousVideoCalls']
        if kwargs.get('useMaxCallTimeForAnsweredCalls') is not None:
            elements['useMaxCallTimeForAnsweredCalls'] = kwargs['useMaxCallTimeForAnsweredCalls']
        if kwargs.get('maxCallTimeForAnsweredCallsMinutes') is not None:
            elements['maxCallTimeForAnsweredCallsMinutes'] = kwargs['maxCallTimeForAnsweredCallsMinutes']
        if kwargs.get('useMaxCallTimeForUnansweredCalls') is not None:
            elements['useMaxCallTimeForUnansweredCalls'] = kwargs['useMaxCallTimeForUnansweredCalls']
        if kwargs.get('maxCallTimeForUnansweredCallsMinutes') is not None:
            elements['maxCallTimeForUnansweredCallsMinutes'] = kwargs['maxCallTimeForUnansweredCallsMinutes']
        if kwargs.get('mediaPolicySelection') is not None:
            elements['mediaPolicySelection'] = kwargs['mediaPolicySelection']
        if kwargs.get('supportedMediaSetName') is not None:
            elements['supportedMediaSetName'] = kwargs['supportedMediaSetName']
        if kwargs.get('networkUsageSelection') is not None:
            elements['networkUsageSelection'] = kwargs['networkUsageSelection']
        if kwargs.get('enforceGroupCallingLineIdentityRestriction') is not None:
            elements['enforceGroupCallingLineIdentityRestriction'] = \
                kwargs['enforceGroupCallingLineIdentityRestriction']
        if kwargs.get('allowEnterpriseGroupCallTypingForPrivateDialingPlan') is not None:
            elements['allowEnterpriseGroupCallTypingForPrivateDialingPlan'] = \
                kwargs['allowEnterpriseGroupCallTypingForPrivateDialingPlan']
        if kwargs.get('allowEnterpriseGroupCallTypingForPublicDialingPlan') is not None:
            elements['allowEnterpriseGroupCallTypingForPublicDialingPlan'] = \
                kwargs['allowEnterpriseGroupCallTypingForPublicDialingPlan']
        if kwargs.get('overrideCLIDRestrictionForPrivateCallCategory') is not None:
            elements['overrideCLIDRestrictionForPrivateCallCategory'] = \
                kwargs['overrideCLIDRestrictionForPrivateCallCategory']
        if kwargs.get('useEnterpriseCLIDForPrivateCallCategory') is not None:
            elements['useEnterpriseCLIDForPrivateCallCategory'] = kwargs['useEnterpriseCLIDForPrivateCallCategory']
        if kwargs.get('enableEnterpriseExtensionDialing') is not None:
            elements['enableEnterpriseExtensionDialing'] = kwargs['enableEnterpriseExtensionDialing']
        if kwargs.get('useMaxConcurrentRedirectedCalls') is not None:
            elements['useMaxConcurrentRedirectedCalls'] = kwargs['useMaxConcurrentRedirectedCalls']
        if kwargs.get('maxConcurrentRedirectedCalls') is not None:
            elements['maxConcurrentRedirectedCalls'] = kwargs['maxConcurrentRedirectedCalls']
        if kwargs.get('useMaxFindMeFollowMeDepth') is not None:
            elements['useMaxFindMeFollowMeDepth'] = kwargs['useMaxFindMeFollowMeDepth']
        if kwargs.get('maxFindMeFollowMeDepth') is not None:
            elements['maxFindMeFollowMeDepth'] = kwargs['maxFindMeFollowMeDepth']
        if kwargs.get('maxRedirectionDepth') is not None:
            elements['maxRedirectionDepth'] = kwargs['maxRedirectionDepth']
        if kwargs.get('useMaxConcurrentFindMeFollowMeInvocations') is not None:
            elements['useMaxConcurrentFindMeFollowMeInvocations'] = kwargs['useMaxConcurrentFindMeFollowMeInvocations']
        if kwargs.get('maxConcurrentFindMeFollowMeInvocations') is not None:
            elements['maxConcurrentFindMeFollowMeInvocations'] = kwargs['maxConcurrentFindMeFollowMeInvocations']
        if kwargs.get('clidPolicy') is not None:
            elements['clidPolicy'] = kwargs['clidPolicy']
        if kwargs.get('emergencyClidPolicy') is not None:
            elements['emergencyClidPolicy'] = kwargs['emergencyClidPolicy']
        if kwargs.get('allowAlternateNumbersForRedirectingIdentity') is not None:
            elements['allowAlternateNumbersForRedirectingIdentity'] = \
                kwargs['allowAlternateNumbersForRedirectingIdentity']
        if kwargs.get('useGroupName') is not None:
            elements['useGroupName'] = kwargs['useGroupName']
        if kwargs.get('blockCallingNameForExternalCalls') is not None:
            elements['blockCallingNameForExternalCalls'] = kwargs['blockCallingNameForExternalCalls']
        if kwargs.get('enableDialableCallerID') is not None:
            elements['enableDialableCallerID'] = kwargs['enableDialableCallerID']
        if kwargs.get('allowConfigurableCLIDForRedirectingIdentity') is not None:
            elements['allowConfigurableCLIDForRedirectingIdentity'] = \
                kwargs['allowConfigurableCLIDForRedirectingIdentity']
        if kwargs.get('allowDepartmentCLIDNameOverride') is not None:
            elements['allowDepartmentCLIDNameOverride'] = kwargs['allowDepartmentCLIDNameOverride']
        tables = []
        return locals()

    @staticmethod
    def GroupCPEConfigRebuildConfigFileRequest(serviceProviderId, groupId, deviceType, **kwargs):
        name = 'GroupCPEConfigRebuildConfigFileRequest'
        elements = OrderedDict()
        elements['serviceProviderId'] = serviceProviderId
        elements['groupId'] = groupId
        elements['deviceType'] = deviceType
        if kwargs.get('force') is not None:
            elements['force'] = kwargs['force']
        tables = []
        return locals()

    @staticmethod
    def GroupCPEConfigRebuildDeviceConfigFileRequest(serviceProviderId, groupId, deviceName):
        name = 'GroupCPEConfigRebuildDeviceConfigFileRequest'
        elements = OrderedDict()
        elements['serviceProviderId'] = serviceProviderId
        elements['groupId'] = groupId
        elements['deviceName'] = deviceName
        tables = []
        return locals()

    @staticmethod
    def GroupCPEConfigReorderDeviceLinePortsRequest(serviceProviderId, groupId, deviceName, linePortList):
        if not type(linePortList) == 'list':
            raise Exception('linePortList must be a list')

        name = 'GroupCPEConfigReorderDeviceLinePortsRequest'
        elements = OrderedDict()
        elements['serviceProviderId'] = serviceProviderId
        elements['groupId'] = groupId
        elements['deviceName'] = deviceName
        elements['orderedLinePortList'] = linePortList
        tables = []
        return locals()

    @staticmethod
    def GroupCustomContactDirectoryAddRequest17(serviceProviderId, groupId, directory_name, entry=None):
        name = 'GroupCustomContactDirectoryAddRequest17'
        elements = OrderedDict()
        elements['serviceProviderId'] = serviceProviderId
        elements['groupId'] = groupId
        elements['name'] = directory_name
        if entry is not None:
            elements['entry'] = entry
        tables = []
        return locals()

    @staticmethod
    def GroupCustomContactDirectoryModifyRequest17(serviceProviderId, groupId, directory_name, **kwargs):
        name = 'GroupCustomContactDirectoryModifyRequest17'
        elements = OrderedDict()
        elements['serviceProviderId'] = serviceProviderId
        elements['groupId'] = groupId
        elements['name'] = directory_name
        if kwargs.get('newName') is not None:
            elements['newName'] = kwargs['newName']
        if kwargs.get('entryList') is not None:
            elements['entryList'] = OrderedDict()
            entries = list()
            for e in kwargs['entryList']:
                entries.append(e)
            elements['entryList']['entry'] = entries
        tables = []
        return locals()

    @staticmethod
    def GroupDeleteRequest(serviceProviderId, groupId):
        name = 'GroupDeleteRequest'
        elements = OrderedDict()
        elements['serviceProviderId'] = serviceProviderId
        elements['groupId'] = groupId
        tables = []
        return locals()

    @staticmethod
    def GroupDeviceTypeCustomTagAddRequest(serviceProviderId, groupId, deviceType, tagName, **kwargs):
        name = 'GroupDeviceTypeCustomTagAddRequest'
        elements = OrderedDict()
        elements['serviceProviderId'] = serviceProviderId
        elements['groupId'] = groupId
        elements['deviceType'] = deviceType
        elements['tagName'] = tagName
        if 'tagValue' in kwargs:
            elements['tagValue'] = kwargs['tagValue']
        tables = []
        return locals()

    @staticmethod
    def GroupDeviceTypeCustomTagDeleteListRequest(serviceProviderId, groupId, deviceType, tagName):
        name = 'GroupDeviceTypeCustomTagDeleteListRequest'
        elements = OrderedDict()
        elements['serviceProviderId'] = serviceProviderId
        elements['groupId'] = groupId
        elements['deviceType'] = deviceType
        elements['tagName'] = tagName
        tables = []
        return locals()


    @staticmethod
    def GroupDeviceTypeCustomTagGetListRequest(serviceProviderId, groupId, deviceType):
        name = 'GroupDeviceTypeCustomTagGetListRequest'
        elements = OrderedDict()
        elements['serviceProviderId'] = serviceProviderId
        elements['groupId'] = groupId
        elements['deviceType'] = deviceType
        tables = ['groupDeviceTypeCustomTagsTable']
        return locals()

    @staticmethod
    def GroupDeviceTypeCustomTagModifyRequest(serviceProviderId, groupId, deviceType, tagName, **kwargs):
        name = 'GroupDeviceTypeCustomTagModifyRequest'
        elements = OrderedDict()
        elements['serviceProviderId'] = serviceProviderId
        elements['groupId'] = groupId
        elements['deviceType'] = deviceType
        elements['tagName'] = tagName
        if 'tagValue' in kwargs:
            elements['tagValue'] = kwargs['tagValue']
        tables = []
        return locals()

    @staticmethod
    def GroupDeviceTypeFileModifyRequest14sp8(serviceProviderId, groupId, deviceType, fileFormat, **kwargs):
        name = 'GroupDeviceTypeFileModifyRequest14sp8'
        elements = OrderedDict()
        elements['serviceProviderId'] = serviceProviderId
        elements['groupId'] = groupId
        elements['deviceType'] = deviceType
        elements['fileFormat'] = fileFormat
        if kwargs.get('fileSource') is not None:
            elements['fileSource'] = kwargs['fileSource']
        if kwargs.get('uploadFile') is not None:
            elements['uploadFile'] = kwargs['uploadFile']
        tables = []
        return locals()

    @staticmethod
    def GroupDnActivateListRequest(serviceProviderId, groupId, **kwargs):
        name = 'GroupDnActivateListRequest'
        elements = OrderedDict()
        elements['serviceProviderId'] = serviceProviderId
        elements['groupId'] = groupId
        if kwargs.get('phoneNumber') is not None:
            elements['phoneNumber'] = kwargs['phoneNumber']
        if kwargs.get('dnRange') is not None:
            elements['dnRange'] = kwargs['dnRange']
        tables = []
        return locals()

    @staticmethod
    def GroupDnAssignListRequest(serviceProviderId, groupId, **kwargs):
        name = 'GroupDnAssignListRequest'
        elements = OrderedDict()
        elements['serviceProviderId'] = serviceProviderId
        elements['groupId'] = groupId
        if kwargs.get('phoneNumber') is not None:
            elements['phoneNumber'] = kwargs['phoneNumber']
        if kwargs.get('dnRange') is not None:
            elements['dnRange'] = kwargs['dnRange']
        tables = []
        return locals()

    @staticmethod
    def GroupDnGetSummaryListRequest(serviceProviderId, groupId):
        name = 'GroupDnGetSummaryListRequest'
        elements = OrderedDict()
        elements['serviceProviderId'] = serviceProviderId
        elements['groupId'] = groupId
        tables = ['dnTable']
        return locals()

    @staticmethod
    def GroupDnUnassignListRequest(serviceProviderId, groupId, **kwargs):
        name = 'GroupDnUnassignListRequest'
        elements = OrderedDict()
        elements['serviceProviderId'] = serviceProviderId
        elements['groupId'] = groupId
        if kwargs.get('phoneNumber') is not None:
            elements['phoneNumber'] = kwargs['phoneNumber']
        if kwargs.get('dnRange') is not None:
            elements['dnRange'] = kwargs['dnRange']
        tables = []
        return locals()

    @staticmethod
    def GroupExtensionLengthModifyRequest17(serviceProviderId, groupId=None, **kwargs):
        name = 'GroupExtensionLengthModifyRequest17'
        elements = OrderedDict()
        elements['serviceProviderId'] = serviceProviderId
        elements['groupId'] = groupId
        if kwargs.get('minExtensionLength') is not None:
            elements['minExtensionLength'] = kwargs['minExtensionLength']
        if kwargs.get('maxExtensionLength') is not None:
            elements['maxExtensionLength'] = kwargs['maxExtensionLength']
        tables = []
        return locals()

    @staticmethod
    def GroupGetListInServiceProviderRequest(serviceProviderId, **kwargs):
        name = 'GroupGetListInServiceProviderRequest'
        elements = OrderedDict()
        elements['serviceProviderId'] = serviceProviderId
        if 'responseSizeLimit' in kwargs:
            elements['responseSizeLimit'] = kwargs['responseSizeLimit']
        if 'searchCriteriaGroupId' in kwargs:
            elements['searchCriteriaGroupId'] = kwargs['searchCriteriaGroupId']
        if 'searchCriteriaGroupName' in kwargs:
            elements['searchCriteriaGroupName'] = kwargs['searchCriteriaGroupName']
        tables = ['groupTable']
        return locals()

    @staticmethod
    def GroupGetListInSystemRequest(**kwargs):
        name = 'GroupGetListInSystemRequest'
        elements = OrderedDict()
        if 'responseSizeLimit' in kwargs:
            elements['responseSizeLimit'] = kwargs['responseSizeLimit']
        if 'searchCriteriaGroupId' in kwargs:
            elements['searchCriteriaGroupId'] = kwargs['searchCriteriaGroupId']
        if 'searchCriteriaGroupName' in kwargs:
            elements['searchCriteriaGroupName'] = kwargs['searchCriteriaGroupName']
        if 'searchCriteriaExactServiceProvider' in kwargs:
            elements['searchCriteriaExactServiceProvider'] = kwargs['searchCriteriaExactServiceProvider']
        tables = ['groupTable']
        return locals()

    @staticmethod
    def GroupGetRequest14sp7(serviceProviderId, groupId):
        name = 'GroupGetRequest14sp7'
        elements = OrderedDict()
        elements['serviceProviderId'] = serviceProviderId
        elements['groupId'] = groupId
        tables = []
        return locals()

    @staticmethod
    def GroupGroupPagingAddInstanceRequest(serviceProviderId, groupId, serviceUserId, serviceInstanceProfile,
                                           confirmationToneTimeoutSeconds, deliverOriginatorCLIDInstead,
                                           originatorCLIDPrefix=None):
        name = 'GroupGroupPagingAddInstanceRequest'
        elements = OrderedDict()
        elements['serviceProviderId'] = serviceProviderId
        elements['groupId'] = groupId
        elements['serviceUserId'] = serviceUserId
        elements['serviceInstanceProfile'] = serviceInstanceProfile
        elements['confirmationToneTimeoutSeconds'] = confirmationToneTimeoutSeconds
        elements['deliverOriginatorCLIDInstead'] = deliverOriginatorCLIDInstead
        if originatorCLIDPrefix is not None:
            elements['originatorCLIDPrefix'] = originatorCLIDPrefix
        tables = []
        return locals()

    @staticmethod
    def GroupGroupPagingAddOriginatorListRequest(serviceUserId, originatorUserId):
        name = 'GroupGroupPagingAddOriginatorListRequest'
        elements = OrderedDict()
        elements['serviceUserId'] = serviceUserId
        elements['originatorUserId'] = originatorUserId
        tables = []
        return locals()

    @staticmethod
    def GroupGroupPagingAddTargetListRequest(serviceUserId, targetUserId):
        name = 'GroupGroupPagingAddTargetListRequest'
        elements = OrderedDict()
        elements['serviceUserId'] = serviceUserId
        elements['targetUserId'] = targetUserId
        tables = []
        return locals()

    @staticmethod
    def GroupGroupPagingDeleteInstanceRequest(serviceUserId):
        name = 'GroupGroupPagingDeleteInstanceRequest'
        elements = OrderedDict()
        elements['serviceUserId'] = serviceUserId
        tables = []
        return locals()

    @staticmethod
    def GroupGroupPagingModifyInstanceRequest(serviceUserId, **kwargs):
        name = 'GroupGroupPagingModifyInstanceRequest'
        elements = OrderedDict()
        elements['serviceUserId'] = serviceUserId
        if kwargs.get('serviceInstanceProfile') is not None:
            elements['serviceInstanceProfile'] = kwargs['serviceInstanceProfile']
        if kwargs.get('confirmationToneTimeoutSeconds') is not None:
            elements['confirmationToneTimeoutSeconds'] = kwargs['confirmationToneTimeoutSeconds']
        if kwargs.get('deliverOriginatorCLIDInstead') is not None:
            elements['deliverOriginatorCLIDInstead'] = kwargs['deliverOriginatorCLIDInstead']
        if kwargs.get('originatorCLIDPrefix') is not None:
            elements['originatorCLIDPrefix'] = kwargs['originatorCLIDPrefix']
        tables = []
        return locals()

    @staticmethod
    def GroupGroupPagingModifyOriginatorListRequest(serviceUserId, originatorUserIdList=None):
        name = 'GroupGroupPagingModifyOriginatorListRequest'
        elements = OrderedDict()
        elements['serviceUserId'] = serviceUserId
        if originatorUserIdList is not None:
            if len(originatorUserIdList) == 0:
                elements['originatorUserIdList'] = Nil()
            else:
                elements['originatorUserIdList'] = {'userId': originatorUserIdList}
        tables = []
        return locals()

    @staticmethod
    def GroupGroupPagingModifyTargetListRequest(serviceUserId, targetUserIdList=None):
        name = 'GroupGroupPagingModifyTargetListRequest'
        elements = OrderedDict()
        elements['serviceUserId'] = serviceUserId
        if targetUserIdList is not None:
            if len(targetUserIdList) == 0:
                elements['targetUserIdList'] = Nil()
            else:
                elements['targetUserIdList'] = {'userId': targetUserIdList}
        tables = []
        return locals()

    @staticmethod
    def GroupHuntGroupAddInstanceRequest19(serviceProviderId, groupId, serviceUserId, serviceInstanceProfile, policy,
                                           huntAfterNoAnswer, noAnswerNumberOfRings, forwardAfterTimeout,
                                           forwardTimeoutSeconds, allowCallWaitingForAgents,
                                           useSystemHuntGroupCLIDSetting, includeHuntGroupNameInCLID,
                                           enableNotReachableForwarding, makeBusyWhenNotReachable,
                                           allowMembersToControlGroupBusy, enableGroupBusy, **kwargs):
        name = 'GroupHuntGroupAddInstanceRequest19'
        elements = OrderedDict()
        elements['serviceProviderId'] = serviceProviderId
        elements['groupId'] = groupId
        elements['serviceUserId'] = serviceUserId
        elements['serviceInstanceProfile'] = serviceInstanceProfile
        elements['policy'] = policy
        elements['huntAfterNoAnswer'] = huntAfterNoAnswer
        elements['noAnswerNumberOfRings'] = noAnswerNumberOfRings
        elements['forwardAfterTimeout'] = forwardAfterTimeout
        elements['forwardTimeoutSeconds'] = forwardTimeoutSeconds
        if kwargs.get('forwardToPhoneNumber') is not None:
            elements['forwardToPhoneNumber'] = kwargs['forwardToPhoneNumber']
        if kwargs.get('agentUserId') is not None:
            elements['agentUserId'] = kwargs['agentUserId']
        elements['allowCallWaitingForAgents'] = allowCallWaitingForAgents
        elements['useSystemHuntGroupCLIDSetting'] = useSystemHuntGroupCLIDSetting
        elements['includeHuntGroupNameInCLID'] = includeHuntGroupNameInCLID
        elements['enableNotReachableForwarding'] = enableNotReachableForwarding
        if kwargs.get('notReachableForwardToPhoneNumber') is not None:
            elements['notReachableForwardToPhoneNumber'] = kwargs['notReachableForwardToPhoneNumber']
        elements['makeBusyWhenNotReachable'] = makeBusyWhenNotReachable
        elements['allowMembersToControlGroupBusy'] = allowMembersToControlGroupBusy
        elements['enableGroupBusy'] = enableGroupBusy
        tables = []
        return locals()

    @staticmethod
    def GroupHuntGroupDeleteInstanceRequest(serviceUserId):
        name = 'GroupHuntGroupDeleteInstanceRequest'
        elements = OrderedDict()
        elements['serviceUserId'] = serviceUserId
        tables = []
        return locals()

    @staticmethod
    def GroupHuntGroupModifyInstanceRequest(serviceUserId, **kwargs):
        name = 'GroupHuntGroupModifyInstanceRequest'
        elements = OrderedDict()
        elements['serviceUserId'] = serviceUserId
        if kwargs.get('serviceInstanceProfile') is not None:
            elements['serviceInstanceProfile'] = kwargs['serviceInstanceProfile']
        if kwargs.get('policy') is not None:
            elements['policy'] = kwargs['policy']
        if kwargs.get('huntAfterNoAnswer') is not None:
            elements['huntAfterNoAnswer'] = kwargs['huntAfterNoAnswer']
        if kwargs.get('noAnswerNumberOfRings') is not None:
            elements['noAnswerNumberOfRings'] = kwargs['noAnswerNumberOfRings']
        if kwargs.get('forwardAfterTimeout') is not None:
            elements['forwardAfterTimeout'] = kwargs['forwardAfterTimeout']
        if kwargs.get('forwardTimeoutSeconds') is not None:
            elements['forwardTimeoutSeconds'] = kwargs['forwardTimeoutSeconds']
        if kwargs.get('forwardToPhoneNumber') is not None:
            elements['forwardToPhoneNumber'] = kwargs['forwardToPhoneNumber']
        if kwargs.get('agentUserIdList') is not None:
            if len(kwargs['agentUserIdList']) == 0:
                elements['agentUserIdList'] = Nil()
            else:
                elements['agentUserIdList'] = {'userId': kwargs['agentUserIdList']}
        if kwargs.get('allowCallWaitingForAgents') is not None:
            elements['allowCallWaitingForAgents'] = kwargs['allowCallWaitingForAgents']
        if kwargs.get('useSystemHuntGroupCLIDSetting') is not None:
            elements['useSystemHuntGroupCLIDSetting'] = kwargs['useSystemHuntGroupCLIDSetting']
        if kwargs.get('includeHuntGroupNameInCLID') is not None:
            elements['includeHuntGroupNameInCLID'] = kwargs['includeHuntGroupNameInCLID']
        if kwargs.get('enableNotReachableForwarding') is not None:
            elements['enableNotReachableForwarding'] = kwargs['enableNotReachableForwarding']
        if kwargs.get('notReachableForwardToPhoneNumber') is not None:
            elements['notReachableForwardToPhoneNumber'] = kwargs['notReachableForwardToPhoneNumber']
        if kwargs.get('makeBusyWhenNotReachable') is not None:
            elements['makeBusyWhenNotReachable'] = kwargs['makeBusyWhenNotReachable']
        if kwargs.get('allowMembersToControlGroupBusy') is not None:
            elements['allowMembersToControlGroupBusy'] = kwargs['allowMembersToControlGroupBusy']
        if kwargs.get('enableGroupBusy') is not None:
            elements['enableGroupBusy'] = kwargs['enableGroupBusy']
        tables = []
        return locals()

    @staticmethod
    def GroupInterceptGroupGetRequest16sp1(serviceProviderId, groupId):
        name = 'GroupInterceptGroupGetRequest16sp1'
        elements = OrderedDict()
        elements['serviceProviderId'] = serviceProviderId
        elements['groupId'] = groupId
        tables = []
        return locals()

    @staticmethod
    def GroupInterceptGroupModifyRequest16(serviceProviderId, groupId, **kwargs):
        name = 'GroupInterceptGroupModifyRequest16'
        elements = OrderedDict()
        elements['serviceProviderId'] = serviceProviderId
        elements['groupId'] = groupId
        if kwargs.get('isActive') is not None:
            elements['isActive'] = kwargs['isActive']
        if kwargs.get('announcementSelection') is not None:
            elements['announcementSelection'] = kwargs['announcementSelection']
        if kwargs.get('audioFile') is not None:
            elements['audioFile'] = kwargs['audioFile']
        if kwargs.get('videoFile') is not None:
            elements['videoFile'] = kwargs['videoFile']
        if kwargs.get('playNewPhoneNumber') is not None:
            elements['playNewPhoneNumber'] = kwargs['playNewPhoneNumber']
        if kwargs.get('newPhoneNumber') is not None:
            elements['newPhoneNumber'] = kwargs['newPhoneNumber']
        if kwargs.get('transferOnZeroToPhoneNumber') is not None:
            elements['transferOnZeroToPhoneNumber'] = kwargs['transferOnZeroToPhoneNumber']
        if kwargs.get('transferPhoneNumber') is not None:
            elements['transferPhoneNumber'] = kwargs['transferPhoneNumber']
        if kwargs.get('rerouteOutboundCalls') is not None:
            elements['rerouteOutboundCalls'] = kwargs['rerouteOutboundCalls']
        if kwargs.get('outboundReroutePhoneNumber') is not None:
            elements['outboundReroutePhoneNumber'] = kwargs['outboundReroutePhoneNumber']
        if kwargs.get('allowOutboundLocalCalls') is not None:
            elements['allowOutboundLocalCalls'] = kwargs['allowOutboundLocalCalls']
        if kwargs.get('inboundCallMode') is not None:
            elements['inboundCallMode'] = kwargs['inboundCallMode']
        if kwargs.get('alternateBlockingAnnouncement') is not None:
            elements['alternateBlockingAnnouncement'] = kwargs['alternateBlockingAnnouncement']
        if kwargs.get('routeToVoiceMail') is not None:
            elements['routeToVoiceMail'] = kwargs['routeToVoiceMail']
        tables = []
        return locals()

    @staticmethod
    def GroupMeetMeConferencingModifyInstanceRequest(serviceUserId, **kwargs):
        name = 'GroupMeetMeConferencingModifyInstanceRequest'
        elements = OrderedDict()
        elements['serviceUserId'] = serviceUserId
        if 'serviceInstanceProfile' in kwargs:
            elements['serviceInstanceProfile'] = kwargs['serviceInstanceProfile']
        if 'allocatedPorts' in kwargs:
            elements['allocatedPorts'] = kwargs['allocatedPorts']
        if 'networkClassOfService' in kwargs:
            elements['networkClassOfService'] = kwargs['networkClassOfService']
        if 'securityPinLength' in kwargs:
            elements['securityPinLength'] = kwargs['securityPinLength']
        if 'allowIndividualOutDial' in kwargs:
            elements['allowIndividualOutDial'] = kwargs['allowIndividualOutDial']
        if 'operatorNumber' in kwargs:
            elements['operatorNumber'] = kwargs['operatorNumber']
        if 'conferenceHostUserIdList' in kwargs:
            elements['conferenceHostUserIdList'] = kwargs['conferenceHostUserIdList']
        if 'playWarningPrompt' in kwargs:
            elements['playWarningPrompt'] = kwargs['playWarningPrompt']
        if 'conferenceEndWarningPromptMinutes' in kwargs:
            elements['conferenceEndWarningPromptMinutes'] = kwargs['conferenceEndWarningPromptMinutes']
        if 'enableMaxConferenceDuration' in kwargs:
            elements['enableMaxConferenceDuration'] = kwargs['enableMaxConferenceDuration']
        if 'maxConferenceDurationMinutes' in kwargs:
            elements['maxConferenceDurationMinutes'] = kwargs['maxConferenceDurationMinutes']
        if 'maxScheduledConferenceDurationMinutes' in kwargs:
            elements['maxScheduledConferenceDurationMinutes'] = kwargs['maxScheduledConferenceDurationMinutes']
        tables = []
        return locals()

    @staticmethod
    def GroupModifyRequest(serviceProviderId, groupId, **kwargs):
        name = 'GroupModifyRequest'
        elements = OrderedDict()
        elements['serviceProviderId'] = serviceProviderId
        elements['groupId'] = groupId
        if kwargs.get('defaultDomain') is not None:
            elements['defaultDomain'] = kwargs['defaultDomain']
        if kwargs.get('userLimit') is not None:
            elements['userLimit'] = kwargs['userLimit']
        if kwargs.get('groupName') is not None:
            elements['groupName'] = kwargs['groupName']
        if kwargs.get('callingLineIdName') is not None:
            elements['callingLineIdName'] = kwargs['callingLineIdName']
        if kwargs.get('callingLineIdPhoneNumber') is not None:
            elements['callingLineIdPhoneNumber'] = kwargs['callingLineIdPhoneNumber']
        if kwargs.get('timeZone') is not None:
            elements['timeZone'] = kwargs['timeZone']
        if kwargs.get('locationDialingCode') is not None:
            elements['locationDialingCode'] = kwargs['locationDialingCode']
        if kwargs.get('contact') is not None:
            elements['contact'] = kwargs['contact']
        if kwargs.get('address') is not None:
            elements['address'] = kwargs['address']
        tables = []
        return locals()

    @staticmethod
    def GroupOutgoingCallingPlanOriginatingGetListRequest(serviceProviderId, groupId):
        name = 'GroupOutgoingCallingPlanOriginatingGetListRequest'
        elements = OrderedDict()
        elements['serviceProviderId'] = serviceProviderId
        elements['groupId'] = groupId
        tables = []
        return locals()

    @staticmethod
    def GroupOutgoingCallingPlanOriginatingModifyListRequest(serviceProviderId, groupId, **kwargs):
        name = 'GroupOutgoingCallingPlanOriginatingModifyListRequest'
        elements = OrderedDict()
        elements['serviceProviderId'] = serviceProviderId
        elements['groupId'] = groupId
        if kwargs.get('groupPermissions') is not None:
            elements['groupPermissions'] = kwargs['groupPermissions']
        if kwargs.get('departmentPermissions') is not None:
            elements['departmentPermissions'] = kwargs['departmentPermissions']
        tables = []
        return locals()

    @staticmethod
    def GroupOutgoingCallingPlanRedirectingGetListRequest(serviceProviderId, groupId):
        name = 'GroupOutgoingCallingPlanRedirectingGetListRequest'
        elements = OrderedDict()
        elements['serviceProviderId'] = serviceProviderId
        elements['groupId'] = groupId
        tables = []
        return locals()

    @staticmethod
    def GroupOutgoingCallingPlanRedirectingModifyListRequest(serviceProviderId, groupId, **kwargs):
        name = 'GroupOutgoingCallingPlanRedirectingModifyListRequest'
        elements = OrderedDict()
        elements['serviceProviderId'] = serviceProviderId
        elements['groupId'] = groupId
        if kwargs.get('groupPermissions') is not None:
            elements['groupPermissions'] = kwargs['groupPermissions']
        if kwargs.get('departmentPermissions') is not None:
            elements['departmentPermissions'] = kwargs['departmentPermissions']
        tables = []
        return locals()

    @staticmethod
    def GroupServiceAssignListRequest(serviceProviderId, groupId, serviceName):
        name = 'GroupServiceAssignListRequest'
        elements = OrderedDict()
        elements['serviceProviderId'] = serviceProviderId
        elements['groupId'] = groupId
        elements['serviceName'] = serviceName
        tables = []
        return locals()

    @staticmethod
    def GroupServiceGetAuthorizationListRequest(serviceProviderId, groupId):
        name = 'GroupServiceGetAuthorizationListRequest'
        elements = OrderedDict()
        elements['serviceProviderId'] = serviceProviderId
        elements['groupId'] = groupId
        tables = ['servicePacksAuthorizationTable', 'groupServicesAuthorizationTable', 'userServicesAuthorizationTable']
        return locals()

    @staticmethod
    def GroupServiceModifyAuthorizationListRequest(serviceProviderId, groupId, **kwargs):
        name = 'GroupServiceModifyAuthorizationListRequest'
        elements = OrderedDict()
        elements['serviceProviderId'] = serviceProviderId
        elements['groupId'] = groupId
        if kwargs.get('servicePackAuthorization') is not None:
            data = kwargs.get('servicePackAuthorization')
            if isinstance(data, dict):
                elements['servicePackAuthorization'] = data
            elif isinstance(data, list) and len(data):
                l = list()
                for g in data:
                    if isinstance(g, dict):
                        l.append(g)
                    else:
                        v = OrderedDict()
                        v['serviceName'] = g
                        v['authorizedQuantity'] = {'unlimited': True}
                        l.append(v)
                elements['servicePackAuthorization'] = l
        if kwargs.get('groupServiceAuthorization') is not None:
            data = kwargs.get('groupServiceAuthorization')
            if isinstance(data, dict):
                elements['groupServiceAuthorization'] = data
            elif isinstance(data, list) and len(data):
                l = list()
                for g in data:
                    if isinstance(g, dict):
                        l.append(g)
                    else:
                        v = OrderedDict()
                        v['serviceName'] = g
                        v['authorizedQuantity'] = {'unlimited': True}
                        l.append(v)
                elements['groupServiceAuthorization'] = l
        if kwargs.get('userServiceAuthorization') is not None:
            data = kwargs.get('userServiceAuthorization')
            if isinstance(data, dict):
                elements['userServiceAuthorization'] = data
            if isinstance(data, list) and len(data):
                l = list()
                for g in data:
                    if isinstance(g, dict):
                        l.append(g)
                    else:
                        v = OrderedDict()
                        v['serviceName'] = g
                        v['authorizedQuantity'] = {'unlimited': True}
                        l.append(v)
                elements['userServiceAuthorization'] = l
        tables = []
        return locals()

    @staticmethod
    def GroupVoiceMessagingGroupGetRequest(serviceProviderId, groupId):
        name = 'GroupVoiceMessagingGroupGetRequest'
        elements = OrderedDict()
        elements['serviceProviderId'] = serviceProviderId
        elements['groupId'] = groupId
        tables = []
        return locals()

    @staticmethod
    def GroupVoiceMessagingGroupModifyVoicePortalRequest(serviceProviderId, groupId, **kwargs):
        name = 'GroupVoiceMessagingGroupModifyVoicePortalRequest'
        elements = OrderedDict()
        elements['serviceProviderId'] = serviceProviderId
        elements['groupId'] = groupId
        if kwargs.get('serviceInstanceProfile') is not None:
            elements['serviceInstanceProfile'] = kwargs['serviceInstanceProfile']
        if kwargs.get('isActive') is not None:
            elements['isActive'] = kwargs['isActive']
        if kwargs.get('enableExtendedScope') is not None:
            elements['enableExtendedScope'] = kwargs['enableExtendedScope']
        if kwargs.get('allowIdentificationByPhoneNumberOrVoiceMailAliasesOnLogin') is not None:
            elements['allowIdentificationByPhoneNumberOrVoiceMailAliasesOnLogin'] = \
                kwargs['allowIdentificationByPhoneNumberOrVoiceMailAliasesOnLogin']
        if kwargs.get('useVoicePortalWizard') is not None:
            elements['useVoicePortalWizard'] = kwargs['useVoicePortalWizard']
        if kwargs.get('voicePortalExternalRoutingScope') is not None:
            elements['voicePortalExternalRoutingScope'] = kwargs['voicePortalExternalRoutingScope']
        if kwargs.get('useExternalRouting') is not None:
            elements['useExternalRouting'] = kwargs['useExternalRouting']
        if kwargs.get('externalRoutingAddress') is not None:
            elements['externalRoutingAddress'] = kwargs['externalRoutingAddress']
        if kwargs.get('homeZoneName') is not None:
            elements['homeZoneName'] = kwargs['homeZoneName']
        tables = []
        return locals()

    @staticmethod
    def UserVoiceMessagingUserGetVoiceManagementRequest17(userId):
        name = 'UserVoiceMessagingUserGetVoiceManagementRequest17'
        elements = OrderedDict()
        elements['userId'] = userId
        tables = []
        return locals()

    @staticmethod
    def LoginRequest14sp4(userId, signedPassword):
        name = 'LoginRequest14sp4'
        elements = OrderedDict()
        elements['userId'] = userId
        elements['signedPassword'] = signedPassword
        tables = []
        return locals()

    @staticmethod
    def LogoutRequest(userId, reason=None):
        name = 'LogoutRequest'
        elements = {
            'userId': userId
        }
        if reason is not None:
            elements['reason'] = reason
        tables = []
        return locals()

    @staticmethod
    def ServiceProviderAccessDeviceAddRequest14(serviceProviderId, deviceName, deviceType, **kwargs):
        name = 'ServiceProviderAccessDeviceAddRequest14'
        elements = OrderedDict()
        elements['serviceProviderId'] = serviceProviderId
        elements['deviceName'] = deviceName
        elements['deviceType'] = deviceType
        if kwargs.get('macAddress') is not None:
            elements['macAddress'] = kwargs['macAddress']
        if kwargs.get('username') is not None and kwargs.get('password') is not None:
            creds = OrderedDict()
            creds['userName'] = kwargs['username']
            creds['password'] = kwargs['password']
            elements['useCustomUserNamePassword'] = True
            elements['accessDeviceCredentials'] = creds
        tables = []
        return locals()

    @staticmethod
    def ServiceProviderAccessDeviceGetRequest18sp1(serviceProviderId, deviceName):
        name = 'ServiceProviderAccessDeviceGetRequest18sp1'
        elements = OrderedDict()
        elements['serviceProviderId'] = serviceProviderId
        elements['deviceName'] = deviceName
        tables = []
        return locals()

    @staticmethod
    def ServiceProviderAccessDeviceGetUserListRequest(serviceProviderId, deviceName, **kwargs):
        name = 'ServiceProviderAccessDeviceGetUserListRequest'
        elements = OrderedDict()
        elements['serviceProviderId'] = serviceProviderId
        elements['deviceName'] = deviceName
        if 'responseSizeLimit' in kwargs:
            elements['responseSizeLimit'] = kwargs['responseSizeLimit']
        if 'searchCriteriaLinePortUserPart' in kwargs:
            elements['searchCriteriaLinePortUserPart'] = kwargs['searchCriteriaLinePortUserPart']
        if 'searchCriteriaLinePortDomain' in kwargs:
            elements['searchCriteriaLinePortDomain'] = kwargs['searchCriteriaLinePortDomain']
        if 'searchCriteriaUserLastName' in kwargs:
            elements['searchCriteriaUserLastName'] = kwargs['searchCriteriaUserLastName']
        if 'searchCriteriaUserFirstName' in kwargs:
            elements['searchCriteriaUserFirstName'] = kwargs['searchCriteriaUserFirstName']
        if 'searchCriteriaDn' in kwargs:
            elements['searchCriteriaDn'] = kwargs['searchCriteriaDn']
        if 'searchCriteriaUserId' in kwargs:
            elements['searchCriteriaUserId'] = kwargs['searchCriteriaUserId']
        if 'searchCriteriaGroupId' in kwargs:
            elements['searchCriteriaGroupId'] = kwargs['searchCriteriaGroupId']
        if 'searchCriteriaExactEndpointType' in kwargs:
            elements['searchCriteriaExactEndpointType'] = kwargs['searchCriteriaExactEndpointType']
        if 'searchCriteriaExactUserType' in kwargs:
            elements['searchCriteriaExactUserType'] = kwargs['searchCriteriaExactUserType']
        if 'searchCriteriaExtension' in kwargs:
            elements['searchCriteriaExtension'] = kwargs['searchCriteriaExtension']
        if 'searchCriteriaExactUserDepartment' in kwargs:
            elements['searchCriteriaExactUserDepartment'] = kwargs['searchCriteriaExactUserDepartment']
        if 'searchCriteriaExactPortNumber' in kwargs:
            elements['searchCriteriaExactPortNumber'] = kwargs['searchCriteriaExactPortNumber']
        tables = ['deviceUserTable']
        return locals()

    @staticmethod
    def ServiceProviderAccessDeviceCustomTagAddRequest(serviceProviderId, deviceName, tagName, **kwargs):
        name = 'ServiceProviderAccessDeviceCustomTagAddRequest'
        elements = OrderedDict()
        elements['serviceProviderId'] = serviceProviderId
        elements['deviceName'] = deviceName
        elements['tagName'] = tagName
        if 'tagValue' in kwargs:
            elements['tagValue'] = kwargs['tagValue']
        tables = []
        return locals()

    @staticmethod
    def ServiceProviderAccessDeviceCustomTagDeleteListRequest(serviceProviderId, deviceName, tagName):
        name = 'ServiceProviderAccessDeviceCustomTagDeleteListRequest'
        elements = OrderedDict()
        elements['serviceProviderId'] = serviceProviderId
        elements['deviceName'] = deviceName
        elements['tagName'] = tagName
        tables = []
        return locals()

    @staticmethod
    def ServiceProviderAccessDeviceCustomTagGetListRequest(serviceProviderId, deviceName):
        name = 'ServiceProviderAccessDeviceCustomTagGetListRequest'
        elements = OrderedDict()
        elements['serviceProviderId'] = serviceProviderId
        elements['deviceName'] = deviceName
        tables = []
        return locals()

    @staticmethod
    def ServiceProviderAccessDeviceCustomTagModifyRequest(serviceProviderId, deviceName, tagName, **kwargs):
        name = 'ServiceProviderAccessDeviceCustomTagModifyRequest'
        elements = OrderedDict()
        elements['serviceProviderId'] = serviceProviderId
        elements['deviceName'] = deviceName
        elements['tagName'] = tagName
        if 'tagValue' in kwargs:
            elements['tagValue'] = kwargs['tagValue']
        tables = []
        return locals()

    @staticmethod
    def ServiceProviderAccessDeviceDeleteRequest(serviceProviderId, deviceName):
        name = 'ServiceProviderAccessDeviceDeleteRequest'
        elements = OrderedDict()
        elements['serviceProviderId'] = serviceProviderId
        elements['deviceName'] = deviceName
        tables = []
        return locals()

    @staticmethod
    def ServiceProviderAccessDeviceModifyUserRequest(serviceProviderId, deviceName, linePort, isPrimaryLinePort):
        name = 'ServiceProviderAccessDeviceModifyUserRequest'
        elements = OrderedDict()
        elements['serviceProviderId'] = serviceProviderId
        elements['deviceName'] = deviceName
        elements['linePort'] = linePort
        elements['isPrimaryLinePort'] = isPrimaryLinePort
        tables = []
        return locals()

    @staticmethod
    def ServiceProviderAccessDeviceResetRequest(serviceProviderId, deviceName):
        name = 'ServiceProviderAccessDeviceResetRequest'
        elements = OrderedDict()
        elements['serviceProviderId'] = serviceProviderId
        elements['deviceName'] = deviceName
        tables = []
        return locals()

    @staticmethod
    def ServiceProviderAddRequest13mp2(serviceProviderId, serviceProviderName, defaultDomain, **kwargs):
        name = 'ServiceProviderAddRequest13mp2'
        elements = OrderedDict()
        if kwargs.get('enterprise') is not None:
            elements['isEnterprise'] = str(kwargs['enterprise']).lower()
        elif kwargs.get('useCustomRoutingProfile') is not None:
            elements['useCustomRoutingProfile'] = str(kwargs['useCustomRoutingProfile']).lower()
        else:
            raise Exception('Expected enterprise or useCustomRoutingProfile')
        elements['serviceProviderId'] = serviceProviderId
        elements['defaultDomain'] = defaultDomain
        if serviceProviderName is not None:
            elements['serviceProviderName'] = serviceProviderName
        tables = []
        return locals()

    @staticmethod
    def ServiceProviderCallProcessingModifyPolicyRequest15(serviceProviderId, **kwargs):
        name = 'ServiceProviderCallProcessingModifyPolicyRequest15'
        elements = OrderedDict()
        elements['serviceProviderId'] = serviceProviderId
        if kwargs.get('useServiceProviderDCLIDSetting') is not None:
            elements['useServiceProviderDCLIDSetting'] = kwargs['useServiceProviderDCLIDSetting']
        if kwargs.get('useMaxSimultaneousCalls') is not None:
            elements['useMaxSimultaneousCalls'] = kwargs['useMaxSimultaneousCalls']
        if kwargs.get('maxSimultaneousCalls') is not None:
            elements['maxSimultaneousCalls'] = kwargs['maxSimultaneousCalls']
        if kwargs.get('useMaxSimultaneousVideoCalls') is not None:
            elements['useMaxSimultaneousVideoCalls'] = kwargs['useMaxSimultaneousVideoCalls']
        if kwargs.get('maxSimultaneousVideoCalls') is not None:
            elements['maxSimultaneousVideoCalls'] = kwargs['maxSimultaneousVideoCalls']
        if kwargs.get('useMaxCallTimeForAnsweredCalls') is not None:
            elements['useMaxCallTimeForAnsweredCalls'] = kwargs['useMaxCallTimeForAnsweredCalls']
        if kwargs.get('maxCallTimeForAnsweredCallsMinutes') is not None:
            elements['maxCallTimeForAnsweredCallsMinutes'] = kwargs['maxCallTimeForAnsweredCallsMinutes']
        if kwargs.get('useMaxCallTimeForUnansweredCalls') is not None:
            elements['useMaxCallTimeForUnansweredCalls'] = kwargs['useMaxCallTimeForUnansweredCalls']
        if kwargs.get('maxCallTimeForUnansweredCallsMinutes') is not None:
            elements['maxCallTimeForUnansweredCallsMinutes'] = kwargs['maxCallTimeForUnansweredCallsMinutes']
        if kwargs.get('mediaPolicySelection') is not None:
            elements['mediaPolicySelection'] = kwargs['mediaPolicySelection']
        if kwargs.get('supportedMediaSetName') is not None:
            elements['supportedMediaSetName'] = kwargs['supportedMediaSetName']
        if kwargs.get('networkUsageSelection') is not None:
            elements['networkUsageSelection'] = kwargs['networkUsageSelection']
        if kwargs.get('enforceGroupCallingLineIdentityRestriction') is not None:
            elements['enforceGroupCallingLineIdentityRestriction'] = \
                kwargs['enforceGroupCallingLineIdentityRestriction']
        if kwargs.get('allowEnterpriseGroupCallTypingForPrivateDialingPlan') is not None:
            elements['allowEnterpriseGroupCallTypingForPrivateDialingPlan'] = \
                kwargs['allowEnterpriseGroupCallTypingForPrivateDialingPlan']
        if kwargs.get('allowEnterpriseGroupCallTypingForPublicDialingPlan') is not None:
            elements['allowEnterpriseGroupCallTypingForPublicDialingPlan'] = \
                kwargs['allowEnterpriseGroupCallTypingForPublicDialingPlan']
        if kwargs.get('overrideCLIDRestrictionForPrivateCallCategory') is not None:
            elements['overrideCLIDRestrictionForPrivateCallCategory'] = \
                kwargs['overrideCLIDRestrictionForPrivateCallCategory']
        if kwargs.get('useEnterpriseCLIDForPrivateCallCategory') is not None:
            elements['useEnterpriseCLIDForPrivateCallCategory'] = kwargs['useEnterpriseCLIDForPrivateCallCategory']
        if kwargs.get('enableEnterpriseExtensionDialing') is not None:
            elements['enableEnterpriseExtensionDialing'] = kwargs['enableEnterpriseExtensionDialing']
        if kwargs.get('enforceEnterpriseCallingLineIdentityRestriction') is not None:
            elements['enforceEnterpriseCallingLineIdentityRestriction'] = \
                kwargs['enforceEnterpriseCallingLineIdentityRestriction']
        if kwargs.get('useSettingLevel') is not None:
            elements['useSettingLevel'] = kwargs['useSettingLevel']
        if kwargs.get('conferenceURI') is not None:
            elements['conferenceURI'] = kwargs['conferenceURI']
        if kwargs.get('useMaxConcurrentRedirectedCalls') is not None:
            elements['useMaxConcurrentRedirectedCalls'] = kwargs['useMaxConcurrentRedirectedCalls']
        if kwargs.get('maxConcurrentRedirectedCalls') is not None:
            elements['maxConcurrentRedirectedCalls'] = kwargs['maxConcurrentRedirectedCalls']
        if kwargs.get('useMaxFindMeFollowMeDepth') is not None:
            elements['useMaxFindMeFollowMeDepth'] = kwargs['useMaxFindMeFollowMeDepth']
        if kwargs.get('maxFindMeFollowMeDepth') is not None:
            elements['maxFindMeFollowMeDepth'] = kwargs['maxFindMeFollowMeDepth']
        if kwargs.get('maxRedirectionDepth') is not None:
            elements['maxRedirectionDepth'] = kwargs['maxRedirectionDepth']
        if kwargs.get('useMaxConcurrentFindMeFollowMeInvocations') is not None:
            elements['useMaxConcurrentFindMeFollowMeInvocations'] = kwargs['useMaxConcurrentFindMeFollowMeInvocations']
        if kwargs.get('maxConcurrentFindMeFollowMeInvocations') is not None:
            elements['maxConcurrentFindMeFollowMeInvocations'] = kwargs['maxConcurrentFindMeFollowMeInvocations']
        if kwargs.get('clidPolicy') is not None:
            elements['clidPolicy'] = kwargs['clidPolicy']
        if kwargs.get('emergencyClidPolicy') is not None:
            elements['emergencyClidPolicy'] = kwargs['emergencyClidPolicy']
        if kwargs.get('allowAlternateNumbersForRedirectingIdentity') is not None:
            elements['allowAlternateNumbersForRedirectingIdentity'] = \
                kwargs['allowAlternateNumbersForRedirectingIdentity']
        if kwargs.get('enableDialableCallerID') is not None:
            elements['enableDialableCallerID'] = kwargs['enableDialableCallerID']
        if kwargs.get('blockCallingNameForExternalCalls') is not None:
            elements['blockCallingNameForExternalCalls'] = kwargs['blockCallingNameForExternalCalls']
        if kwargs.get('allowConfigurableCLIDForRedirectingIdentity') is not None:
            elements['allowConfigurableCLIDForRedirectingIdentity'] = \
                kwargs['allowConfigurableCLIDForRedirectingIdentity']
        tables = []
        return locals()

    @staticmethod
    def ServiceProviderCPEConfigRebuildDeviceConfigFileRequest(serviceProviderId, deviceName):
        name = 'ServiceProviderCPEConfigRebuildDeviceConfigFileRequest'
        elements = OrderedDict()
        elements['serviceProviderId'] = serviceProviderId
        elements['deviceName'] = deviceName
        tables = []
        return locals()

    @staticmethod
    def ServiceProviderDeleteRequest(serviceProviderId):
        name = 'ServiceProviderDeleteRequest'
        elements = OrderedDict()
        elements['serviceProviderId'] = serviceProviderId
        tables = []
        return locals()

    @staticmethod
    def ServiceProviderDnAddListRequest(serviceProviderId, **kwargs):
        name = 'ServiceProviderDnAddListRequest'
        elements = OrderedDict()
        elements['serviceProviderId'] = serviceProviderId
        if kwargs.get('phoneNumber') is not None:
            elements['phoneNumber'] = kwargs['phoneNumber']
        if kwargs.get('dnRange') is not None:
            elements['dnRange'] = kwargs['dnRange']
        tables = []
        return locals()

    @staticmethod
    def ServiceProviderDnDeleteListRequest(serviceProviderId, **kwargs):
        name = 'ServiceProviderDnDeleteListRequest'
        elements = OrderedDict()
        elements['serviceProviderId'] = serviceProviderId
        if kwargs.get('phoneNumber') is not None:
            elements['phoneNumber'] = kwargs['phoneNumber']
        if kwargs.get('dnRange') is not None:
            elements['dnRange'] = kwargs['dnRange']
        tables = []
        return locals()

    @staticmethod
    def ServiceProviderDnGetSummaryListRequest(serviceProviderId):
        name = 'ServiceProviderDnGetSummaryListRequest'
        elements = OrderedDict()
        elements['serviceProviderId'] = serviceProviderId
        tables = ['dnSummaryTable']
        return locals()

    @staticmethod
    def ServiceProviderGetListRequest(**kwargs):
        name = 'ServiceProviderGetListRequest'
        elements = OrderedDict()
        if kwargs.get('enterprise') is not None:
            elements['isEnterprise'] = str(kwargs['enterprise']).lower()
        tables = ['serviceProviderTable']
        return locals()

    @staticmethod
    def ServiceProviderGetRequest17sp1(serviceProviderId):
        name = 'ServiceProviderGetRequest17sp1'
        elements = OrderedDict()
        elements['serviceProviderId'] = serviceProviderId
        tables = []
        return locals()

    @staticmethod
    def ServiceProviderServiceGetAuthorizationListRequest(serviceProviderId):
        name = 'ServiceProviderServiceGetAuthorizationListRequest'
        elements = OrderedDict()
        elements['serviceProviderId'] = serviceProviderId
        tables = ['groupServicesAuthorizationTable', 'userServicesAuthorizationTable']
        return locals()

    @staticmethod
    def ServiceProviderServiceModifyAuthorizationListRequest(serviceProviderId, **kwargs):
        name = 'ServiceProviderServiceModifyAuthorizationListRequest'
        elements = OrderedDict()
        elements['serviceProviderId'] = serviceProviderId
        if kwargs.get('groupServiceAuthorization') is not None:
            data = kwargs.get('groupServiceAuthorization')
            if isinstance(data, dict):
                elements['groupServiceAuthorization'] = data
            elif isinstance(data, list) and len(data):
                l = list()
                for g in data:
                    if isinstance(g, dict):
                        l.append(g)
                    else:
                        v = OrderedDict()
                        v['serviceName'] = g
                        v['authorizedQuantity'] = {'unlimited': True}
                        l.append(v)
                elements['groupServiceAuthorization'] = l
        if kwargs.get('userServiceAuthorization') is not None:
            data = kwargs.get('userServiceAuthorization')
            if isinstance(data, dict):
                elements['userServiceAuthorization'] = data
            if isinstance(data, list) and len(data):
                l = list()
                for g in data:
                    if isinstance(g, dict):
                        l.append(g)
                    else:
                        v = OrderedDict()
                        v['serviceName'] = g
                        v['authorizedQuantity'] = {'unlimited': True}
                        l.append(v)
                elements['userServiceAuthorization'] = l
        tables = []
        return locals()

    @staticmethod
    def ServiceProviderServicePackAddRequest(serviceProviderId, servicePackName, isAvailableForUse, servicePackQuantity,
                                             **kwargs):
        name = 'ServiceProviderServicePackAddRequest'
        elements = OrderedDict()
        elements['serviceProviderId'] = serviceProviderId
        elements['servicePackName'] = servicePackName
        if kwargs.get('servicePackDescription') is not None:
            elements['servicePackDescription'] = kwargs['servicePackDescription']
        elements['isAvailableForUse'] = isAvailableForUse
        elements['servicePackQuantity'] = servicePackQuantity
        if kwargs.get('serviceName') is not None:
            elements['serviceName'] = kwargs['serviceName']
        tables = []
        return locals()

    @staticmethod
    def ServiceProviderServicePackGetDetailListRequest(serviceProviderId, servicePackName):
        name = 'ServiceProviderServicePackGetDetailListRequest'
        elements = OrderedDict()
        elements['serviceProviderId'] = serviceProviderId
        elements['servicePackName'] = servicePackName
        tables = ['userServiceTable']
        return locals()

    @staticmethod
    def ServiceProviderServicePackGetListRequest(serviceProviderId):
        name = 'ServiceProviderServicePackGetListRequest'
        elements = OrderedDict()
        elements['serviceProviderId'] = serviceProviderId
        tables = []
        return locals()

    @staticmethod
    def SystemAccessDeviceGetAllRequest(**kwargs):
        name = 'SystemAccessDeviceGetAllRequest'
        elements = OrderedDict()
        if 'responseSizeLimit' in kwargs:
            elements['responseSizeLimit'] = kwargs['responseSizeLimit']
        if 'searchCriteriaDeviceName' in kwargs:
            elements['searchCriteriaDeviceName'] = kwargs['searchCriteriaDeviceName']
        if 'searchCriteriaDeviceMACAddress' in kwargs:
            elements['searchCriteriaDeviceMACAddress'] = kwargs['searchCriteriaDeviceMACAddress']
        if 'searchCriteriaDeviceNetAddress' in kwargs:
            elements['searchCriteriaDeviceNetAddress'] = kwargs['searchCriteriaDeviceNetAddress']
        if 'searchCriteriaGroupId' in kwargs:
            elements['searchCriteriaGroupId'] = kwargs['searchCriteriaGroupId']
        if 'searchCriteriaExactDeviceType' in kwargs:
            elements['searchCriteriaExactDeviceType'] = kwargs['searchCriteriaExactDeviceType']
        if 'searchCriteriaExactDeviceServiceProvider' in kwargs:
            elements['searchCriteriaExactDeviceServiceProvider'] = kwargs['searchCriteriaExactDeviceServiceProvider']
        tables = ['accessDeviceTable']
        return locals()

    @staticmethod
    def SystemAccessDeviceTypeGetListRequest():
        name = 'SystemAccessDeviceTypeGetListRequest'
        elements = OrderedDict()
        tables = []
        return locals()

    @staticmethod
    def SystemDeviceTypeGetRequest19(device_type):
        name = 'SystemDeviceTypeGetRequest19'
        elements = OrderedDict()
        elements['deviceType'] = device_type
        tables = []
        return locals()

    @staticmethod
    def SystemSIPDeviceTypeFileAddRequest20(device_type, file_format, remote_file_format, file_category, file_customization, file_source, use_http_digest_authentication, mac_based_file_authentication, user_name_password_file_authentication, mac_in_non_request_uri, allow_http, allow_https, allow_tftp, enable_caching, allow_upload_from_device, **kwargs):
        name = 'SystemSIPDeviceTypeFileAddRequest20'
        elements = OrderedDict()
        elements['deviceType'] = device_type
        elements['fileFormat'] = file_format
        elements['remoteFileFormat'] = remote_file_format
        elements['fileCategory'] = file_category
        elements['fileCustomization'] = file_customization
        elements['fileSource'] = file_source
        if 'uploadFile' in kwargs:
            elements['uploadFile'] = kwargs['uploadFile']
        elements['useHttpDigestAuthentication'] = use_http_digest_authentication
        elements['macBasedFileAuthentication'] = mac_based_file_authentication
        elements['userNamePasswordFileAuthentication'] = user_name_password_file_authentication
        elements['macInNonRequestURI'] = mac_in_non_request_uri
        if 'macFormatInNonRequestURI' in kwargs:
            elements['macFormatInNonRequestURI'] = kwargs['macFormatInNonRequestURI']
        elements['allowHttp'] = allow_http
        elements['allowHttps'] = allow_https
        elements['allowTftp'] = allow_tftp
        elements['enableCaching'] = enable_caching
        elements['allowUploadFromDevice'] = allow_upload_from_device
        if 'defaultExtendedFileCaptureMode' in kwargs:
            elements['defaultExtendedFileCaptureMode'] = kwargs['defaultExtendedFileCaptureMode']
        tables = []
        return locals()

    @staticmethod
    def SystemSIPDeviceTypeFileGetListRequest14sp8(device_type):
        name = 'SystemSIPDeviceTypeFileGetListRequest14sp8'
        elements = OrderedDict()
        elements['deviceType'] = device_type
        tables = ['deviceTypeFilesTable']
        return locals()

    @staticmethod
    def SystemSIPDeviceTypeFileGetRequest20(device_type, file_format):
        name = 'SystemSIPDeviceTypeFileGetRequest20'
        elements = OrderedDict()
        elements['deviceType'] = device_type
        elements['fileFormat'] = file_format
        tables = []
        return locals()

    @staticmethod
    def SystemSIPDeviceTypeFileModifyRequest16sp1(device_type, file_format, **kwargs):
        name = 'SystemSIPDeviceTypeFileModifyRequest16sp1'
        elements = OrderedDict()
        elements['deviceType'] = device_type
        elements['fileFormat'] = file_format
        if 'fileCustomization' in kwargs:
            elements['fileCustomization'] = kwargs['fileCustomization']
        if 'fileSource' in kwargs:
            elements['fileSource'] = kwargs['fileSource']
        if 'uploadFile' in kwargs:
            elements['uploadFile'] = kwargs['uploadFile']
        if 'useHttpDigestAuthentication' in kwargs:
            elements['useHttpDigestAuthentication'] = kwargs['useHttpDigestAuthentication']
        if 'macBasedFileAuthentication' in kwargs:
            elements['macBasedFileAuthentication'] = kwargs['macBasedFileAuthentication']
        if 'userNamePasswordFileAuthentication' in kwargs:
            elements['userNamePasswordFileAuthentication'] = kwargs['userNamePasswordFileAuthentication']
        if 'macInNonRequestURI' in kwargs:
            elements['macInNonRequestURI'] = kwargs['macInNonRequestURI']
        if 'macFormatInNonRequestURI' in kwargs:
            elements['macFormatInNonRequestURI'] = kwargs['macFormatInNonRequestURI']
        if 'allowHttp' in kwargs:
            elements['allowHttp'] = kwargs['allowHttp']
        if 'allowHttps' in kwargs:
            elements['allowHttps'] = kwargs['allowHttps']
        if 'allowTftp' in kwargs:
            elements['allowTftp'] = kwargs['allowTftp']
        if 'enableCaching' in kwargs:
            elements['enableCaching'] = kwargs['enableCaching']
        if 'allowUploadFromDevice' in kwargs:
            elements['allowUploadFromDevice'] = kwargs['allowUploadFromDevice']
        if 'defaultExtendedFileCaptureMode' in kwargs:
            elements['defaultExtendedFileCaptureMode'] = kwargs['defaultExtendedFileCaptureMode']
        tables = []
        return locals()

    @staticmethod
    def SystemSoftwareVersionGetRequest():
        name = 'SystemSoftwareVersionGetRequest'
        elements = {}
        tables = []
        return locals()

    @staticmethod
    def UserAccessDeviceResetRequest(userId, accessDevice):
        name = 'UserAccessDeviceResetRequest'
        elements = OrderedDict()
        elements['userId'] = userId
        elements['accessDevice'] = accessDevice
        tables = []
        return locals()

    @staticmethod
    def UserAddRequest17sp4(serviceProviderId, groupId, userId, lastName, firstName, callingLineIdLastName,
                            callingLineIdFirstName, **kwargs):
        name = 'UserAddRequest17sp4'
        elements = OrderedDict()
        elements['serviceProviderId'] = serviceProviderId
        elements['groupId'] = groupId
        elements['userId'] = userId
        elements['lastName'] = lastName
        elements['firstName'] = firstName
        elements['callingLineIdLastName'] = callingLineIdLastName
        elements['callingLineIdFirstName'] = callingLineIdFirstName
        if kwargs.get('hiraganaLastName') is not None:
            elements['hiraganaLastName'] = kwargs['hiraganaLastName']
        if kwargs.get('hiraganaFirstName') is not None:
            elements['hiraganaFirstName'] = kwargs['hiraganaFirstName']
        if kwargs.get('phoneNumber') is not None:
            elements['phoneNumber'] = kwargs['phoneNumber']
        if kwargs.get('extension') is not None:
            elements['extension'] = kwargs['extension']
        if kwargs.get('callingLineIdPhoneNumber') is not None:
            elements['callingLineIdPhoneNumber'] = kwargs['callingLineIdPhoneNumber']
        if kwargs.get('password') is not None:
            elements['password'] = kwargs['password']
        if kwargs.get('department') is not None:
            elements['department'] = kwargs['department']
        if kwargs.get('language') is not None:
            elements['language'] = kwargs['language']
        if kwargs.get('timeZone') is not None:
            elements['timeZone'] = kwargs['timeZone']
        if kwargs.get('alias') is not None:
            if not type(kwargs['alias']) == dict:
                raise Exception('alias must be a dict')
            elements['alias'] = kwargs['alias']
        if kwargs.get('accessDeviceEndpoint') is not None:
            elements['accessDeviceEndpoint'] = kwargs['accessDeviceEndpoint']
        elif kwargs.get('trunkAddressing') is not None:
            elements['trunkAddressing'] = kwargs['trunkAddressing']
        if kwargs.get('title') is not None:
            elements['title'] = kwargs['title']
        if kwargs.get('pagerPhoneNumber') is not None:
            elements['pagerPhoneNumber'] = kwargs['pagerPhoneNumber']
        if kwargs.get('mobilePhoneNumber') is not None:
            elements['mobilePhoneNumber'] = kwargs['mobilePhoneNumber']
        if kwargs.get('yahooId') is not None:
            elements['yahooId'] = kwargs['yahooId']
        if kwargs.get('addressLocation') is not None:
            elements['addressLocation'] = kwargs['addressLocation']
        if kwargs.get('address') is not None:
            if not type(kwargs['address']) == dict:
                raise Exception('address must be a dict')
            elements['address'] = kwargs['address']
        if kwargs.get('networkClassOfService') is not None:
            elements['networkClassOfService'] = kwargs['networkClassOfService']
        tables = []
        return locals()

    @staticmethod
    def UserAssignedServicesGetListRequest(userId):
        name = 'UserAssignedServicesGetListRequest'
        elements = OrderedDict()
        elements['userId'] = userId
        tables = []
        return locals()

    @staticmethod
    def UserAuthenticationModifyRequest(userId, **kwargs):
        name = 'UserAuthenticationModifyRequest'
        elements = OrderedDict()
        elements['userId'] = userId
        if kwargs.get('userName') is not None:
            elements['userName'] = kwargs['userName']
        if kwargs.get('newPassword') is not None:
            elements['newPassword'] = kwargs['newPassword']
        if kwargs.get('password') is not None:
            elements['password'] = kwargs['password']
        tables = []
        return locals()

    @staticmethod
    def UserBusyLampFieldGetRequest16sp2(userId):
        name = 'UserBusyLampFieldGetRequest16sp2'
        elements = OrderedDict()
        elements['userId'] = userId
        tables = ['monitoredUserTable']
        return locals()

    @staticmethod
    def UserBusyLampFieldModifyRequest(userId, **kwargs):
        name = 'UserBusyLampFieldModifyRequest'
        elements = OrderedDict()
        elements['userId'] = userId
        if kwargs.get('listURI') is not None:
            elements['listURI'] = kwargs['listURI']
        if kwargs.get('monitoredUserIdList') is not None:
            if len(kwargs['monitoredUserIdList']) == 0:
                elements['monitoredUserIdList'] = Nil()
            else:
                elements['monitoredUserIdList'] = {'userId': kwargs['monitoredUserIdList']}
        if kwargs.get('enableCallParkNotification') is not None:
            elements['enableCallParkNotification'] = kwargs['enableCallParkNotification']
        tables = []
        return locals()

    @staticmethod
    def UserCallForwardingAlwaysModifyRequest(userId, **kwargs):
        name = 'UserCallForwardingAlwaysModifyRequest'
        elements = OrderedDict()
        elements['userId'] = userId
        if kwargs.get('isActive') is not None:
            elements['isActive'] = kwargs['isActive']
        if kwargs.get('forwardToPhoneNumber') is not None:
            elements['forwardToPhoneNumber'] = kwargs['forwardToPhoneNumber']
        if kwargs.get('isRingSplashActive') is not None:
            elements['isRingSplashActive'] = kwargs['isRingSplashActive']
        tables = []
        return locals()

    @staticmethod
    def UserCallPickupGetRequest(userId):
        name = 'UserCallPickupGetRequest'
        elements = OrderedDict()
        elements['userId'] = userId
        tables = ['userTable']
        return locals()

    @staticmethod
    def UserCallProcessingModifyPolicyRequest14sp7(userId, **kwargs):
        name = 'UserCallProcessingModifyPolicyRequest14sp7'
        elements = OrderedDict()
        elements['userId'] = userId
        if kwargs.get('useUserCLIDSetting') is not None:
            elements['useUserCLIDSetting'] = kwargs['useUserCLIDSetting']
        if kwargs.get('useUserMediaSetting') is not None:
            elements['useUserMediaSetting'] = kwargs['useUserMediaSetting']
        if kwargs.get('useUserCallLimitsSetting') is not None:
            elements['useUserCallLimitsSetting'] = kwargs['useUserCallLimitsSetting']
        if kwargs.get('useUserDCLIDSetting') is not None:
            elements['useUserDCLIDSetting'] = kwargs['useUserDCLIDSetting']
        if kwargs.get('useMaxSimultaneousCalls') is not None:
            elements['useMaxSimultaneousCalls'] = kwargs['useMaxSimultaneousCalls']
        if kwargs.get('maxSimultaneousCalls') is not None:
            elements['maxSimultaneousCalls'] = kwargs['maxSimultaneousCalls']
        if kwargs.get('useMaxSimultaneousVideoCalls') is not None:
            elements['useMaxSimultaneousVideoCalls'] = kwargs['useMaxSimultaneousVideoCalls']
        if kwargs.get('maxSimultaneousVideoCalls') is not None:
            elements['maxSimultaneousVideoCalls'] = kwargs['maxSimultaneousVideoCalls']
        if kwargs.get('useMaxCallTimeForAnsweredCalls') is not None:
            elements['useMaxCallTimeForAnsweredCalls'] = kwargs['useMaxCallTimeForAnsweredCalls']
        if kwargs.get('maxCallTimeForAnsweredCallsMinutes') is not None:
            elements['maxCallTimeForAnsweredCallsMinutes'] = kwargs['maxCallTimeForAnsweredCallsMinutes']
        if kwargs.get('useMaxCallTimeForUnansweredCalls') is not None:
            elements['useMaxCallTimeForUnansweredCalls'] = kwargs['useMaxCallTimeForUnansweredCalls']
        if kwargs.get('maxCallTimeForUnansweredCallsMinutes') is not None:
            elements['maxCallTimeForUnansweredCallsMinutes'] = kwargs['maxCallTimeForUnansweredCallsMinutes']
        if kwargs.get('mediaPolicySelection') is not None:
            elements['mediaPolicySelection'] = kwargs['mediaPolicySelection']
        if kwargs.get('supportedMediaSetName') is not None:
            elements['supportedMediaSetName'] = kwargs['supportedMediaSetName']
        if kwargs.get('useMaxConcurrentRedirectedCalls') is not None:
            elements['useMaxConcurrentRedirectedCalls'] = kwargs['useMaxConcurrentRedirectedCalls']
        if kwargs.get('maxConcurrentRedirectedCalls') is not None:
            elements['maxConcurrentRedirectedCalls'] = kwargs['maxConcurrentRedirectedCalls']
        if kwargs.get('useMaxFindMeFollowMeDepth') is not None:
            elements['useMaxFindMeFollowMeDepth'] = kwargs['useMaxFindMeFollowMeDepth']
        if kwargs.get('maxFindMeFollowMeDepth') is not None:
            elements['maxFindMeFollowMeDepth'] = kwargs['maxFindMeFollowMeDepth']
        if kwargs.get('maxFindMeFollowMeDepth') is not None:
            elements['maxFindMeFollowMeDepth'] = kwargs['maxFindMeFollowMeDepth']
        if kwargs.get('maxRedirectionDepth') is not None:
            elements['maxRedirectionDepth'] = kwargs['maxRedirectionDepth']
        if kwargs.get('useMaxConcurrentFindMeFollowMeInvocations') is not None:
            elements['useMaxConcurrentFindMeFollowMeInvocations'] = kwargs['useMaxConcurrentFindMeFollowMeInvocations']
        if kwargs.get('maxConcurrentFindMeFollowMeInvocations') is not None:
            elements['maxConcurrentFindMeFollowMeInvocations'] = kwargs['maxConcurrentFindMeFollowMeInvocations']
        if kwargs.get('clidPolicy') is not None:
            elements['clidPolicy'] = kwargs['clidPolicy']
        if kwargs.get('emergencyClidPolicy') is not None:
            elements['emergencyClidPolicy'] = kwargs['emergencyClidPolicy']
        if kwargs.get('allowAlternateNumbersForRedirectingIdentity') is not None:
            elements['allowAlternateNumbersForRedirectingIdentity'] = kwargs['allowAlternateNumbersForRedirectingIdentity']
        if kwargs.get('useGroupName') is not None:
            elements['useGroupName'] = kwargs['useGroupName']
        if kwargs.get('enableDialableCallerID') is not None:
            elements['enableDialableCallerID'] = kwargs['enableDialableCallerID']
        if kwargs.get('blockCallingNameForExternalCalls') is not None:
            elements['blockCallingNameForExternalCalls'] = kwargs['blockCallingNameForExternalCalls']
        if kwargs.get('allowConfigurableCLIDForRedirectingIdentity') is not None:
            elements['allowConfigurableCLIDForRedirectingIdentity'] = kwargs['allowConfigurableCLIDForRedirectingIdentity']
        if kwargs.get('allowDepartmentCLIDNameOverride') is not None:
            elements['allowDepartmentCLIDNameOverride'] = kwargs['allowDepartmentCLIDNameOverride']
        tables = []
        return locals()

    @staticmethod
    def UserDeleteRequest(userId):
        name = 'UserDeleteRequest'
        elements = OrderedDict()
        elements['userId'] = userId
        tables = []
        return locals()

    @staticmethod
    def UserGetListInGroupRequest(serviceProviderId, groupId, **kwargs):
        name = 'UserGetListInGroupRequest'
        elements = OrderedDict()
        elements['serviceProviderId'] = serviceProviderId
        elements['GroupId'] = groupId
        if 'responseSizeLimit' in kwargs:
            elements['responseSizeLimit'] = kwargs['responseSizeLimit']
        if 'searchCriteriaUserLastName' in kwargs:
            elements['searchCriteriaUserLastName'] = kwargs['searchCriteriaUserLastName']
        if 'searchCriteriaUserFirstName' in kwargs:
            elements['searchCriteriaUserFirstName'] = kwargs['searchCriteriaUserFirstName']
        if 'searchCriteriaDn' in kwargs:
            elements['searchCriteriaDn'] = kwargs['searchCriteriaDn']
        if 'searchCriteriaEmailAddress' in kwargs:
            elements['searchCriteriaEmailAddress'] = kwargs['searchCriteriaEmailAddress']
        if 'searchCriteriaExactUserDepartment' in kwargs:
            elements['searchCriteriaExactUserDepartment'] = kwargs['searchCriteriaExactUserDepartment']
        if 'searchCriteriaExactUserInTrunkGroup' in kwargs:
            elements['searchCriteriaExactUserInTrunkGroup'] = kwargs['searchCriteriaExactUserInTrunkGroup']
        if 'searchCriteriaUserId' in kwargs:
            elements['searchCriteriaUserId'] = kwargs['searchCriteriaUserId']
        if 'searchCriteriaExtension' in kwargs:
            elements['searchCriteriaExtension'] = kwargs['searchCriteriaExtension']
        tables = ['userTable']
        return locals()

    @staticmethod
    def UserGetListInServiceProviderRequest(serviceProviderId, **kwargs):
        name = 'UserGetListInServiceProviderRequest'
        elements = OrderedDict()
        elements['serviceProviderId'] = serviceProviderId
        if 'responseSizeLimit' in kwargs:
            elements['responseSizeLimit'] = kwargs['responseSizeLimit']
        if 'searchCriteriaUserLastName' in kwargs:
            elements['searchCriteriaUserLastName'] = kwargs['searchCriteriaUserLastName']
        if 'searchCriteriaUserFirstName' in kwargs:
            elements['searchCriteriaUserFirstName'] = kwargs['searchCriteriaUserFirstName']
        if 'searchCriteriaDn' in kwargs:
            elements['searchCriteriaDn'] = kwargs['searchCriteriaDn']
        if 'searchCriteriaEmailAddress' in kwargs:
            elements['searchCriteriaEmailAddress'] = kwargs['searchCriteriaEmailAddress']
        if 'searchCriteriaExactUserInTrunkGroup' in kwargs:
            elements['searchCriteriaExactUserInTrunkGroup'] = kwargs['searchCriteriaExactUserInTrunkGroup']
        if 'searchCriteriaUserId' in kwargs:
            elements['searchCriteriaUserId'] = kwargs['searchCriteriaUserId']
        if 'searchCriteriaExtension' in kwargs:
            elements['searchCriteriaExtension'] = kwargs['searchCriteriaExtension']
        if 'searchCriteriaExactUserDepartment' in kwargs:
            elements['searchCriteriaExactUserDepartment'] = kwargs['searchCriteriaExactUserDepartment']
        tables = ['userTable']
        return locals()

    @staticmethod
    def UserGetListInSystemRequest(**kwargs):
        name = 'UserGetListInSystemRequest'
        elements = OrderedDict()
        if 'responseSizeLimit' in kwargs:
            elements['responseSizeLimit'] = kwargs['responseSizeLimit']
        if 'searchCriteriaUserLastName' in kwargs:
            elements['searchCriteriaUserLastName'] = kwargs['searchCriteriaUserLastName']
        if 'searchCriteriaUserFirstName' in kwargs:
            elements['searchCriteriaUserFirstName'] = kwargs['searchCriteriaUserFirstName']
        if 'searchCriteriaDn' in kwargs:
            elements['searchCriteriaDn'] = kwargs['searchCriteriaDn']
        if 'searchCriteriaEmailAddress' in kwargs:
            elements['searchCriteriaEmailAddress'] = kwargs['searchCriteriaEmailAddress']
        if 'searchCriteriaGroupId' in kwargs:
            elements['searchCriteriaGroupId'] = kwargs['searchCriteriaGroupId']
        if 'searchCriteriaExactServiceProvider' in kwargs:
            elements['searchCriteriaExactServiceProvider'] = kwargs['searchCriteriaExactServiceProvider']
        if 'searchCriteriaExactUserInTrunkGroup' in kwargs:
            elements['searchCriteriaExactUserInTrunkGroup'] = kwargs['searchCriteriaExactUserInTrunkGroup']
        if 'searchCriteriaExactUserNetworkClassOfService' in kwargs:
            elements['searchCriteriaExactUserNetworkClassOfService'] = kwargs['searchCriteriaExactUserNetworkClassOfService']
        if 'searchCriteriaUserId' in kwargs:
            elements['searchCriteriaUserId'] = kwargs['searchCriteriaUserId']
        if 'searchCriteriaExtension' in kwargs:
            elements['searchCriteriaExtension'] = kwargs['searchCriteriaExtension']
        tables = ['userTable']
        return locals()

    @staticmethod
    def UserGetRegistrationListRequest(userId):
        name = 'UserGetRegistrationListRequest'
        elements = {
            'userId': userId,
        }
        tables = ['registrationTable']
        return locals()

    @staticmethod
    def UserGetRequest19(userId):
        name = 'UserGetRequest19'
        elements = {
            'userId': userId,
        }
        tables = []
        return locals()

    @staticmethod
    def UserGetServiceInstanceListInSystemRequest(**kwargs):
        name = 'UserGetServiceInstanceListInSystemRequest'
        elements = OrderedDict()

        if 'responseSizeLimit' in kwargs:
            elements['responseSizeLimit'] = kwargs['responseSizeLimit']
        if 'searchCriteriaExactServiceType' in kwargs:
            elements['searchCriteriaExactServiceType'] = kwargs['searchCriteriaExactServiceType']
        if 'searchCriteriaUserId' in kwargs:
            elements['searchCriteriaUserId'] = kwargs['searchCriteriaUserId']
        if 'searchCriteriaUserLastName' in kwargs:
            elements['searchCriteriaUserLastName'] = kwargs['searchCriteriaUserLastName']
        if 'searchCriteriaDn' in kwargs:
            elements['searchCriteriaDn'] = kwargs['searchCriteriaDn']
        if 'searchCriteriaExtension' in kwargs:
            elements['searchCriteriaExtension'] = kwargs['searchCriteriaExtension']
        if 'searchCriteriaGroupId' in kwargs:
            elements['searchCriteriaGroupId'] = kwargs['searchCriteriaGroupId']
        if 'searchCriteriaExactServiceProvider' in kwargs:
            elements['searchCriteriaExactServiceProvider'] = kwargs['searchCriteriaExactServiceProvider']
        tables = ['serviceInstanceTable']
        return locals()

    @staticmethod
    def UserIntegratedIMPModifyRequest(userId, isActive):
        name = 'UserIntegratedIMPModifyRequest'
        elements = OrderedDict()
        elements['userId'] = userId
        elements['isActive'] = isActive
        tables = []
        return locals()

    @staticmethod
    def UserInterceptUserGetRequest16sp1(userId):
        name = 'UserInterceptUserGetRequest16sp1'
        elements = OrderedDict()
        elements['userId'] = userId
        tables = []
        return locals()

    @staticmethod
    def UserInterceptUserModifyRequest16(userId, **kwargs):
        name = 'UserInterceptUserModifyRequest16'
        elements = OrderedDict()
        elements['userId'] = userId
        if kwargs.get('isActive') is not None:
            elements['isActive'] = kwargs['isActive']
        if kwargs.get('announcementSelection') is not None:
            elements['announcementSelection'] = kwargs['announcementSelection']
        if kwargs.get('audioFile') is not None:
            elements['audioFile'] = kwargs['audioFile']
        if kwargs.get('videoFile') is not None:
            elements['videoFile'] = kwargs['videoFile']
        if kwargs.get('playNewPhoneNumber') is not None:
            elements['playNewPhoneNumber'] = kwargs['playNewPhoneNumber']
        if kwargs.get('newPhoneNumber') is not None:
            elements['newPhoneNumber'] = kwargs['newPhoneNumber']
        if kwargs.get('transferOnZeroToPhoneNumber') is not None:
            elements['transferOnZeroToPhoneNumber'] = kwargs['transferOnZeroToPhoneNumber']
        if kwargs.get('transferPhoneNumber') is not None:
            elements['transferPhoneNumber'] = kwargs['transferPhoneNumber']
        if kwargs.get('rerouteOutboundCalls') is not None:
            elements['rerouteOutboundCalls'] = kwargs['rerouteOutboundCalls']
        if kwargs.get('outboundReroutePhoneNumber') is not None:
            elements['outboundReroutePhoneNumber'] = kwargs['outboundReroutePhoneNumber']
        if kwargs.get('allowOutboundLocalCalls') is not None:
            elements['allowOutboundLocalCalls'] = kwargs['allowOutboundLocalCalls']
        if kwargs.get('inboundCallMode') is not None:
            elements['inboundCallMode'] = kwargs['inboundCallMode']
        if kwargs.get('alternateBlockingAnnouncement') is not None:
            elements['alternateBlockingAnnouncement'] = kwargs['alternateBlockingAnnouncement']
        if kwargs.get('routeToVoiceMail') is not None:
            elements['routeToVoiceMail'] = kwargs['routeToVoiceMail']
        tables = []
        return locals()

    @staticmethod
    def UserLinePortGetListRequest(userId):
        name = 'UserLinePortGetListRequest'
        elements = OrderedDict()
        elements['userId'] = userId
        tables = ['linePortTable']
        return locals()

    @staticmethod
    def UserModifyRequest17sp4(userId, **kwargs):
        name = 'UserModifyRequest17sp4'
        elements = OrderedDict()
        elements['userId'] = userId
        if kwargs.get('lastName') is not None:
            elements['lastName'] = kwargs['lastName']
        if kwargs.get('firstName') is not None:
            elements['firstName'] = kwargs['firstName']
        if kwargs.get('callingLineIdLastName') is not None:
            elements['callingLineIdLastName'] = kwargs['callingLineIdLastName']
        if kwargs.get('callingLineIdFirstName') is not None:
            elements['callingLineIdFirstName'] = kwargs['callingLineIdFirstName']
        if kwargs.get('hiraganaLastName') is not None:
            elements['hiraganaLastName'] = kwargs['hiraganaLastName']
        if kwargs.get('hiraganaFirstName') is not None:
            elements['hiraganaFirstName'] = kwargs['hiraganaFirstName']
        if kwargs.get('phoneNumber') is not None:
            elements['phoneNumber'] = kwargs['phoneNumber']
        if kwargs.get('extension') is not None:
            elements['extension'] = kwargs['extension']
        if kwargs.get('callingLineIdPhoneNumber') is not None:
            elements['callingLineIdPhoneNumber'] = kwargs['callingLineIdPhoneNumber']
        if kwargs.get('oldPassword') is not None:
            elements['oldPassword'] = kwargs['oldPassword']
        if kwargs.get('newPassword') is not None:
            elements['newPassword'] = kwargs['newPassword']
        if kwargs.get('department') is not None:
            elements['department'] = kwargs['department']
        if kwargs.get('language') is not None:
            elements['language'] = kwargs['language']
        if kwargs.get('timeZone') is not None:
            elements['timeZone'] = kwargs['timeZone']
        if kwargs.get('sipAliasList') is not None:
            elements['sipAliasList'] = kwargs['sipAliasList']
        if kwargs.get('endpoint') is not None:
            elements['endpoint'] = kwargs['endpoint']
        if kwargs.get('title') is not None:
            elements['title'] = kwargs['title']
        if kwargs.get('pagerPhoneNumber') is not None:
            elements['pagerPhoneNumber'] = kwargs['pagerPhoneNumber']
        if kwargs.get('mobilePhoneNumber') is not None:
            elements['mobilePhoneNumber'] = kwargs['mobilePhoneNumber']
        if kwargs.get('emailAddress') is not None:
            elements['emailAddress'] = kwargs['emailAddress']
        if kwargs.get('yahooId') is not None:
            elements['yahooId'] = kwargs['yahooId']
        if kwargs.get('addressLocation') is not None:
            elements['addressLocation'] = kwargs['addressLocation']
        if kwargs.get('address') is not None:
            if not type(kwargs['address']) == dict:
                raise Exception('address must be a dict')
            elements['address'] = kwargs['address']
        if kwargs.get('networkClassOfService') is not None:
            elements['networkClassOfService'] = kwargs['networkClassOfService']
        if kwargs.get('officeZoneName') is not None:
            elements['officeZoneName'] = kwargs['officeZoneName']
        if kwargs.get('primaryZoneName') is not None:
            elements['primaryZoneName'] = kwargs['primaryZoneName']
        if kwargs.get('impId') is not None:
            elements['impId'] = kwargs['impId']
        if kwargs.get('impPassword') is not None:
            elements['impPassword'] = kwargs['impPassword']
        tables = []
        return locals()

    @staticmethod
    def UserModifyUserIdRequest(userId, newUserId):
        name = 'UserModifyUserIdRequest'
        elements = OrderedDict()
        elements['userId'] = userId
        elements['newUserId'] = newUserId
        tables = []
        return locals()

    @staticmethod
    def UserOutgoingCallingPlanOriginatingGetRequest(userId):
        name = 'UserOutgoingCallingPlanOriginatingGetRequest'
        elements = OrderedDict()
        elements['userId'] = userId
        tables = []
        return locals()

    @staticmethod
    def UserOutgoingCallingPlanOriginatingModifyRequest(userId, **kwargs):
        name = 'UserOutgoingCallingPlanOriginatingModifyRequest'
        elements = OrderedDict()
        elements['userId'] = userId
        if kwargs.get('useCustomSettings') is not None:
            elements['useCustomSettings'] = kwargs['useCustomSettings']
        if kwargs.get('userPermissions') is not None:
            elements['userPermissions'] = kwargs['userPermissions']
        tables = []
        return locals()

    @staticmethod
    def UserOutgoingCallingPlanRedirectingGetRequest(userId):
        name = 'UserOutgoingCallingPlanRedirectingGetRequest'
        elements = OrderedDict()
        elements['userId'] = userId
        tables = []
        return locals()

    @staticmethod
    def UserOutgoingCallingPlanRedirectingModifyRequest(userId, **kwargs):
        name = 'UserOutgoingCallingPlanRedirectingModifyRequest'
        elements = OrderedDict()
        elements['userId'] = userId
        if kwargs.get('useCustomSettings') is not None:
            elements['useCustomSettings'] = kwargs['useCustomSettings']
        if kwargs.get('userPermissions') is not None:
            elements['userPermissions'] = kwargs['userPermissions']
        tables = []
        return locals()

    @staticmethod
    def UserPolycomPhoneServicesModifyRequest(userId, accessDevice, **kwargs):
        name = 'UserPolycomPhoneServicesModifyRequest'
        elements = OrderedDict()
        elements['userId'] = userId
        elements['accessDevice'] = accessDevice
        if kwargs.get('integratePhoneDirectoryWithBroadWorks') is not None:
            elements['integratePhoneDirectoryWithBroadWorks'] = kwargs['integratePhoneDirectoryWithBroadWorks']
        if kwargs.get('includeUserPersonalPhoneListInDirectory') is not None:
            elements['includeUserPersonalPhoneListInDirectory'] = kwargs['includeUserPersonalPhoneListInDirectory']
        if kwargs.get('includeGroupCustomContactDirectoryInDirectory') is not None:
            elements['includeGroupCustomContactDirectoryInDirectory'] = \
                kwargs['includeGroupCustomContactDirectoryInDirectory']
        if kwargs.get('groupCustomContactDirectory') is not None:
            elements['groupCustomContactDirectory'] = kwargs['groupCustomContactDirectory']
        tables = []
        return locals()

    @staticmethod
    def UserPortalPasscodeModifyRequest(userId, newPasscode, **kwargs):
        name = 'UserPortalPasscodeModifyRequest'
        elements = OrderedDict()
        elements['userId'] = userId
        if kwargs.get('oldPasscode') is not None:
            elements['oldPasscode'] = kwargs['oldPasscode']
        elements['newPasscode'] = newPasscode
        tables = []
        return locals()

    @staticmethod
    def UserPushToTalkModifyRequest(userId, **kwargs):
        name = 'UserPushToTalkModifyRequest'
        elements = OrderedDict()
        elements['userId'] = userId
        if 'allowAutoAnswer' in kwargs:
            elements['allowAutoAnswer'] = kwargs['allowAutoAnswer']
        if 'outgoingConnectionSelection' in kwargs:
            elements['outgoingConnectionSelection'] = kwargs['outgoingConnectionSelection']
        if 'accessListSelection' in kwargs:
            elements['accessListSelection'] = kwargs['accessListSelection']
        if 'selectedUserIdList' in kwargs:
            elements['selectedUserIdList'] = kwargs['selectedUserIdList']
        tables = []
        return locals()

    @staticmethod
    def UserSharedCallAppearanceAddEndpointRequest14sp2(userId, accessDeviceEndpoint, isActive, allowOrigination,
                                                        allowTermination):
        name = 'UserSharedCallAppearanceAddEndpointRequest14sp2'
        elements = OrderedDict()
        elements['userId'] = userId
        elements['accessDeviceEndpoint'] = accessDeviceEndpoint
        elements['isActive'] = isActive
        elements['allowOrigination'] = allowOrigination
        elements['allowTermination'] = allowTermination
        tables = []
        return locals()

    @staticmethod
    def UserSharedCallAppearanceDeleteEndpointListRequest14(userId, accessDeviceEndpoint):
        name = 'UserSharedCallAppearanceDeleteEndpointListRequest14'
        elements = OrderedDict()
        elements['userId'] = userId
        elements['accessDeviceEndpoint'] = accessDeviceEndpoint
        tables = []
        return locals()

    @staticmethod
    def UserSharedCallAppearanceGetRequest16sp2(userId):
        name = 'UserSharedCallAppearanceGetRequest16sp2'
        elements = OrderedDict()
        elements['userId'] = userId
        tables = ['endpointTable']
        return locals()

    @staticmethod
    def UserSharedCallAppearanceModifyRequest(userId, **kwargs):
        name = 'UserSharedCallAppearanceModifyRequest'
        elements = OrderedDict()
        elements['userId'] = userId
        if kwargs.get('alertAllAppearancesForClickToDialCalls') is not None:
            elements['alertAllAppearancesForClickToDialCalls'] = kwargs['alertAllAppearancesForClickToDialCalls']
        if kwargs.get('alertAllAppearancesForGroupPagingCalls') is not None:
            elements['alertAllAppearancesForGroupPagingCalls'] = kwargs['alertAllAppearancesForGroupPagingCalls']
        if kwargs.get('allowSCACallRetrieve') is not None:
            elements['allowSCACallRetrieve'] = kwargs['allowSCACallRetrieve']
        if kwargs.get('multipleCallArrangementIsActive') is not None:
            elements['multipleCallArrangementIsActive'] = kwargs['multipleCallArrangementIsActive']
        if kwargs.get('allowBridgingBetweenLocations') is not None:
            elements['allowBridgingBetweenLocations'] = kwargs['allowBridgingBetweenLocations']
        if kwargs.get('bridgeWarningTone') is not None:
            elements['bridgeWarningTone'] = kwargs['bridgeWarningTone']
        if kwargs.get('enableCallParkNotification') is not None:
            elements['enableCallParkNotification'] = kwargs['enableCallParkNotification']
        tables = []
        return locals()

    @staticmethod
    def UserServiceAssignListRequest(userId, **kwargs):
        name = 'UserServiceAssignListRequest'
        elements = OrderedDict()
        elements['userId'] = userId
        if kwargs.get('serviceName') is not None:
            elements['serviceName'] = kwargs['serviceName']
        if kwargs.get('servicePackName') is not None:
            elements['servicePackName'] = kwargs['servicePackName']
        tables = []
        return locals()

    @staticmethod
    def UserServiceGetAssignmentListRequest(userId, **kwargs):
        name = 'UserServiceGetAssignmentListRequest'
        elements = OrderedDict()
        elements['userId'] = userId
        tables = ['servicePacksAssignmentTable', 'userServicesAssignmentTable']
        return locals()

    @staticmethod
    def UserServiceUnassignListRequest(userId, **kwargs):
        name = 'UserServiceUnassignListRequest'
        elements = OrderedDict()
        elements['userId'] = userId
        if kwargs.get('serviceName') is not None:
            elements['serviceName'] = kwargs['serviceName']
        if kwargs.get('servicePackName') is not None:
            elements['servicePackName'] = kwargs['servicePackName']
        tables = []
        return locals()

    @staticmethod
    def UserSpeedDial100AddListRequest(userId, **kwargs):
        name = 'UserSpeedDial100AddListRequest'
        elements = OrderedDict()
        elements['userId'] = userId
        if kwargs.get('speedDialEntry') is not None:
            elements['speedDialEntry'] = kwargs['speedDialEntry']
        tables = []
        return locals()

    @staticmethod
    def UserSpeedDial100GetListRequest17sp1(userId):
        name = 'UserSpeedDial100GetListRequest17sp1'
        elements = OrderedDict()
        elements['userId'] = userId
        tables = []
        return locals()

    @staticmethod
    def UserSpeedDial100ModifyListRequest(userId, **kwargs):
        name = 'UserSpeedDial100ModifyListRequest'
        elements = OrderedDict()
        elements['userId'] = userId
        if kwargs.get('speedDialEntry') is not None:
            elements['speedDialEntry'] = kwargs['speedDialEntry']
        tables = []
        return locals()

    @staticmethod
    def UserThirdPartyVoiceMailSupportModifyRequest(userId, **kwargs):
        name = 'UserThirdPartyVoiceMailSupportModifyRequest'
        elements = OrderedDict()
        elements['userId'] = userId
        if 'isActive' in kwargs:
            elements['isActive'] = kwargs['isActive']
        if 'busyRedirectToVoiceMail' in kwargs:
            elements['busyRedirectToVoiceMail'] = kwargs['busyRedirectToVoiceMail']
        if 'noAnswerRedirectToVoiceMail' in kwargs:
            elements['noAnswerRedirectToVoiceMail'] = kwargs['noAnswerRedirectToVoiceMail']
        if 'serverSelection' in kwargs:
            elements['serverSelection'] = kwargs['serverSelection']
        if 'userServer' in kwargs:
            elements['userServer'] = kwargs['userServer']
        if 'mailboxIdType' in kwargs:
            elements['mailboxIdType'] = kwargs['mailboxIdType']
        if 'mailboxURL' in kwargs:
            elements['mailboxURL'] = kwargs['mailboxURL']
        if 'noAnswerNumberOfRings' in kwargs:
            elements['noAnswerNumberOfRings'] = kwargs['noAnswerNumberOfRings']
        if 'alwaysRedirectToVoiceMail' in kwargs:
            elements['alwaysRedirectToVoiceMail'] = kwargs['alwaysRedirectToVoiceMail']
        if 'outOfPrimaryZoneRedirectToVoiceMail' in kwargs:
            elements['outOfPrimaryZoneRedirectToVoiceMail'] = kwargs['outOfPrimaryZoneRedirectToVoiceMail']
        tables = []
        return locals()

    @staticmethod
    def UserVoiceMessagingUserModifyAdvancedVoiceManagementRequest(userId, **kwargs):
        name = 'UserVoiceMessagingUserModifyAdvancedVoiceManagementRequest'
        elements = OrderedDict()
        elements['userId'] = userId
        if kwargs.get('mailServerSelection') is not None:
            elements['mailServerSelection'] = kwargs['mailServerSelection']
        if kwargs.get('groupMailServerEmailAddress') is not None:
            elements['groupMailServerEmailAddress'] = kwargs['groupMailServerEmailAddress']
        if kwargs.get('groupMailServerUserId') is not None:
            elements['groupMailServerUserId'] = kwargs['groupMailServerUserId']
        if kwargs.get('groupMailServerPassword') is not None:
            elements['groupMailServerPassword'] = kwargs['groupMailServerPassword']
        if kwargs.get('useGroupDefaultMailServerFullMailboxLimit') is not None:
            elements['useGroupDefaultMailServerFullMailboxLimit'] = kwargs['useGroupDefaultMailServerFullMailboxLimit']
        if kwargs.get('groupMailServerFullMailboxLimit') is not None:
            elements['groupMailServerFullMailboxLimit'] = kwargs['groupMailServerFullMailboxLimit']
        if kwargs.get('personalMailServerNetAddress') is not None:
            elements['personalMailServerNetAddress'] = kwargs['personalMailServerNetAddress']
        if kwargs.get('personalMailServerProtocol') is not None:
            elements['personalMailServerProtocol'] = kwargs['personalMailServerProtocol']
        if kwargs.get('personalMailServerRealDeleteForImap') is not None:
            elements['personalMailServerRealDeleteForImap'] = kwargs['personalMailServerRealDeleteForImap']
        if kwargs.get('personalMailServerEmailAddress') is not None:
            elements['personalMailServerEmailAddress'] = kwargs['personalMailServerEmailAddress']
        if kwargs.get('personalMailServerUserId') is not None:
            elements['personalMailServerUserId'] = kwargs['personalMailServerUserId']
        if kwargs.get('personalMailServerPassword') is not None:
            elements['personalMailServerPassword'] = kwargs['personalMailServerPassword']
        tables = []
        return locals()

    @staticmethod
    def UserVoiceMessagingUserModifyVoiceManagementRequest(userId, **kwargs):
        name = 'UserVoiceMessagingUserModifyVoiceManagementRequest'
        elements = OrderedDict()
        elements['userId'] = userId
        if kwargs.get('isActive') is not None:
            elements['isActive'] = kwargs['isActive']
        if kwargs.get('processing') is not None:
            elements['processing'] = kwargs['processing']
        if kwargs.get('voiceMessageDeliveryEmailAddress') is not None:
            elements['voiceMessageDeliveryEmailAddress'] = kwargs['voiceMessageDeliveryEmailAddress']
        if kwargs.get('usePhoneMessageWaitingIndicator') is not None:
            elements['usePhoneMessageWaitingIndicator'] = kwargs['usePhoneMessageWaitingIndicator']
        if kwargs.get('sendVoiceMessageNotifyEmail') is not None:
            elements['sendVoiceMessageNotifyEmail'] = kwargs['sendVoiceMessageNotifyEmail']
        if kwargs.get('voiceMessageNotifyEmailAddress') is not None:
            elements['voiceMessageNotifyEmailAddress'] = kwargs['voiceMessageNotifyEmailAddress']
        if kwargs.get('sendCarbonCopyVoiceMessage') is not None:
            elements['sendCarbonCopyVoiceMessage'] = kwargs['sendCarbonCopyVoiceMessage']
        if kwargs.get('voiceMessageCarbonCopyEmailAddress') is not None:
            elements['voiceMessageCarbonCopyEmailAddress'] = kwargs['voiceMessageCarbonCopyEmailAddress']
        if kwargs.get('transferOnZeroToPhoneNumber') is not None:
            elements['transferOnZeroToPhoneNumber'] = kwargs['transferOnZeroToPhoneNumber']
        if kwargs.get('transferPhoneNumber') is not None:
            elements['transferPhoneNumber'] = kwargs['transferPhoneNumber']
        if kwargs.get('alwaysRedirectToVoiceMail') is not None:
            elements['alwaysRedirectToVoiceMail'] = kwargs['alwaysRedirectToVoiceMail']
        if kwargs.get('busyRedirectToVoiceMail') is not None:
            elements['busyRedirectToVoiceMail'] = kwargs['busyRedirectToVoiceMail']
        if kwargs.get('noAnswerRedirectToVoiceMail') is not None:
            elements['noAnswerRedirectToVoiceMail'] = kwargs['noAnswerRedirectToVoiceMail']
        if kwargs.get('outOfPrimaryZoneRedirectToVoiceMail') is not None:
            elements['outOfPrimaryZoneRedirectToVoiceMail'] = kwargs['outOfPrimaryZoneRedirectToVoiceMail']
        tables = []
        return locals()

    @staticmethod
    def UserCombinedGetRequest22(userId, **kwargs):
        name = 'UserCombinedGetRequest22'
        elements = OrderedDict()
        elements['userId'] = userId
        tables = []
        return locals()

    @staticmethod
    def UserCombinedModifyRequest(userId, **kwargs):
        name = 'UserCombinedModifyRequest'
        elements = OrderedDict()
        elements['userId'] = userId
        tables = []
        return locals()



class OCIBuilder:

    @staticmethod
    def build(schema, sessionId):
        xml = '<?xml version="1.0" encoding="ISO-8859-1"?>\n'
        xml += '<BroadsoftDocument protocol="OCI" xmlns="C" xmlns:xsi="https://www.w3.org/2001/XMLSchema-instance">\n'
        xml += '  <sessionId xmlns="">{}</sessionId>\n'.format(sessionId)
        xml += '  <command xsi:type="{}" xmlns="">\n'.format(schema['name'])
        xml += OCIBuilder._buildAttributesXml(schema['elements'])
        xml += '  </command>\n'
        xml += '</BroadsoftDocument>'
        return xml

    @staticmethod
    def _buildAttributesXml(data, level=2):
        xml = ''
        for key, value in data.items():
            if isinstance(value, bool):
                xml += ('    ' * level) + '<{}>{}</{}>\n'.format(key, str(value).lower(), key)
            elif isinstance(value, (int, float)):
                xml += ('    ' * level) + '<{}>{}</{}>\n'.format(key, str(value), key)
            elif isinstance(value, (str,)):
                xml += ('    ' * level) + '<{}>{}</{}>\n'.format(key, escape(value), key)
            elif isinstance(value, (dict, OrderedDict)):
                xml += ('    ' * level) + '<{}>\n'.format(key)
                xml += OCIBuilder._buildAttributesXml(value, level+1)
                xml += ('    ' * level) + '</{}>\n'.format(key)
            elif isinstance(value, (tuple, list)):
                xml += OCIBuilder._buildAttributesXml_list(key, value, level+1)
            elif isinstance(value, Nil):
                xml += ('    ' * level) + '<{} xsi:nil="true"/>\n'.format(key)
            elif value is None:
                pass
            else:
                print('var type not matched: {}'.format(type(value)))
        return xml

    @staticmethod
    def _buildAttributesXml_list(key, data, level=2):
        xml = ''
        for item in data:
            if isinstance(item, bool):
                xml += ('    ' * level) + '<{}>{}</{}>\n'.format(key, str(item).lower(), key)
            elif isinstance(item, (int, float)):
                xml += ('    ' * level) + '<{}>{}</{}>\n'.format(key, str(item), key)
            elif isinstance(item, (str,)):
                xml += ('    ' * level) + '<{}>{}</{}>\n'.format(key, escape(item), key)
            elif isinstance(item, (dict, OrderedDict)):
                xml += ('    ' * level) + '<{}>\n'.format(key)
                xml += OCIBuilder._buildAttributesXml(item, level+1)
                xml += ('    ' * level) + '</{}>\n'.format(key)
            elif isinstance(item, (tuple, list)):
                xml += OCIBuilder._buildAttributesXml_list(key, item, level+1)
            elif isinstance(item, Nil):
                xml += ('    ' * level) + '<{} xsi:nil="true"/>\n'.format(key)
            elif item is None:
                pass
            else:
                print('var type not matched: {}'.format(type(item)))
        return xml

