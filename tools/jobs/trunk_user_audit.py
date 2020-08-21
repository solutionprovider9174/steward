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


class TrunkUserAudit():
    _bw = None
    _process = None
    _fix = False
    _cache = None
    _services = None
    _ignored_services = ['Intercept User']

    def __init__(self, process, fix=False):
        self._cache = {'service_packs': dict(), 'groups_trunk_assigned': set()}
        self._process = process
        self._fix = fix
        self._bw = BroadWorks(url=self._process.platform.uri,
                              username=self._process.platform.username,
                              password=self._process.platform.password)
        self._bw.LoginRequest14sp4()
        # Get the services from LokiHelper's 'TrunkPack'
        resp = self._bw.ServiceProviderServicePackGetDetailListRequest('LokiHelper', 'TrunkPack')
        self._services = [ x['Service'] for x in resp['data']['userServiceTable']]

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

    def trunk_users(self):
        log = io.StringIO()
        summary = io.StringIO()

        # Get list of users
        log.write('UserGetListInSystemRequest(searchCriteriaExactUserInTrunkGroup={userInTrunkGroup: True}) ')
        resp0 = self._bw.UserGetListInSystemRequest(searchCriteriaExactUserInTrunkGroup={'userInTrunkGroup': True})
        log.write(self.parse_response(resp0, 0))
        users = resp0['data']['userTable']

        rval = {'log': log.getvalue(), 'summary': summary.getvalue(), 'users': users}
        log.close()
        summary.close()
        return rval

    def user_audit(self, user, level=1):
        log = io.StringIO()
        summary = io.StringIO()

        provider_id = user['Service Provider Id']
        group_id = user['Group Id']
        user_id = user['User Id']
        phone_number = user['Phone Number']
        extension = user['Extension']
        log.write('{}User {}::{}::{}\n'.format('    '*level, provider_id, group_id, user_id))

        if provider_id not in self._cache['service_packs']:
            # get provider service packs
            log.write('{}ServiceProviderServicePackGetListRequest({}) '.format('    '*(level+1), provider_id))
            resp1 = self._bw.ServiceProviderServicePackGetListRequest(serviceProviderId=provider_id)
            log.write(self.parse_response(resp1, (level+1)))
            packs = resp1['data']['servicePackName']
            if isinstance(packs, str):
                # if packs is a string it is a single instance
                packs = [packs]
            self._cache['service_packs'][provider_id] = {}
            for pack_name in packs:
                log.write('{}ServiceProviderServicePackGetDetailListRequest({}, {}) '.format('    '*(level+1), provider_id, pack_name))
                resp2 = self._bw.ServiceProviderServicePackGetDetailListRequest(provider_id, pack_name)
                log.write(self.parse_response(resp2, (level+1)))
                user_services = [ x['Service'] for x in resp2['data']['userServiceTable']]
                self._cache['service_packs'][provider_id][pack_name] = user_services
            # If no 'TrunkPack' create one
            if 'TrunkPack' not in self._cache['service_packs'][provider_id]:
                log.write("{}ServiceProviderServicePackAddRequest({}, {}, isAvailableForUse=True, servicePackQuantity={'unlimited': True}, serviceName={{...}}) ".format('    '*(level+1), provider_id, 'TrunkPack'))
                resp3 = self._bw.ServiceProviderServicePackAddRequest(provider_id, 'TrunkPack',
                                                                      isAvailableForUse=True,
                                                                      servicePackQuantity={'unlimited': True},
                                                                      serviceName=self._services)
                log.write(self.parse_response(resp3, (level+1)))

        log.write('{}UserServiceGetAssignmentListRequest({}) '.format('    '*(level+1), user_id))
        resp4 = self._bw.UserServiceGetAssignmentListRequest(user_id)
        log.write(self.parse_response(resp4, (level+1)))
        assigned_packs = [x['Service Pack Name'] for x in resp4['data']['servicePacksAssignmentTable'] if x['Assigned'] == 'true']
        assigned_services = [x['Service Name'] for x in resp4['data']['userServicesAssignmentTable'] if x['Assigned'] == 'true']

        # get services
        effective_services = assigned_services
        for pack_name in assigned_packs:
            effective_services += self._cache['service_packs'][provider_id][pack_name]

        # diff services
        bad_services = [item for item in effective_services if item not in self._services and item not in self._ignored_services]
        need_services = [item for item in self._services if item not in effective_services and item not in self._ignored_services]

        # write to summary file & fix if requested
        log.write("{}Found {} bad services: {}\n".format('    '*(level+1), len(bad_services), ','.join(bad_services)))
        log.write("{}Found {} needed services: {}\n".format('    '*(level+1), len(need_services), ','.join(need_services)))
        if bad_services or need_services:
            if self._fix:
                # determine services to remove / add
                if 'TrunkPack' not in assigned_packs:
                    if '{}::{}'.format(provider_id, group_id) not in self._cache['groups_trunk_assigned']:
                        log.write('{}GroupServiceModifyAuthorizationListRequest({}, {}, servicePackAuthorization={{...}}) '.format('    '*(level+1), provider_id, group_id))
                        resp5 = self._bw.GroupServiceModifyAuthorizationListRequest(provider_id, group_id, servicePackAuthorization=OrderedDict([('servicePackName', 'TrunkPack'), ('authorizedQuantity', {'unlimited': True})]))
                        log.write(self.parse_response(resp5, (level+1)))
                        self._cache['groups_trunk_assigned'].add('{}::{}'.format(provider_id, group_id))
                    log.write("{}UserServiceAssignListRequest({}, servicePackName=['TrunkPack']) ".format('    '*(level+1), user_id))
                    resp6 = self._bw.UserServiceAssignListRequest(user_id, servicePackName=['TrunkPack'])
                    log.write(self.parse_response(resp6, (level+1)))
                # remove all assigned services
                remove_service_packs = assigned_packs
                if 'TrunkPack' in remove_service_packs:
                    remove_service_packs.remove('TrunkPack')
                log.write('{}UserServiceUnassignListRequest({}, {{...}}) '.format('    '*(level+1), user_id))
                resp7 = self._bw.UserServiceUnassignListRequest(user_id, serviceName=assigned_services, servicePackName=remove_service_packs)
                log.write(self.parse_response(resp7, (level+1)))
                summary.write('"{}","{}","{}","{}","{}","{}"\n'.format(provider_id, group_id, user_id, ','.join(bad_services), ','.join(need_services), 'Success'))
            else:
                summary.write('"{}","{}","{}","{}","{}","{}"\n'.format(provider_id, group_id, user_id, ','.join(bad_services), ','.join(need_services), ''))

        rval = {'log': log.getvalue(), 'summary': summary.getvalue()}
        log.close()
        summary.close()
        return rval


def trunk_user_audit(process_id):
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
        fixup = process.parameters.get('fixup', 'False') in ['True', 'true']
        ta = TrunkUserAudit(process, fixup)

        # Initial content
        summary_html.write('<table class="table table-striped table-bordered table-hover">\n')
        summary_html.write('<tr>\n')
        summary_html.write('\t<th>Provider Id</th><th>Group Id</th><th>User Id</th><th>Bad Services</th><th>Needed Services</th><th>Result</th>\n')
        summary_html.write('</tr>\n')
        summary_html.write('<tbody>\n')
        summary_raw.write('"Provider Id","Group Id","User Id","Bad Services","Needed Services","Result"\n')

        # Audit!
        data = ta.trunk_users()
        log_raw.write(data['log'])
        summary_raw.write(data['summary'])
        for user in data['users']:
            data = ta.user_audit(user)
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
        summary_html.write('</tbody>\n</table>\n')
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
