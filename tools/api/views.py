# Python
from collections import OrderedDict
import re
import requests

# Django
from django.conf import settings

# Third Party
from rest_framework.mixins import ListModelMixin
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet, ViewSet

# Library
from lib.pybw.broadworks import BroadWorks
from lib.pypalladion.palladion import Palladion

# Application
from tools import models
from tools.api import serializers


class ToolsRootView(APIView):

    def get(self, request, format=None):
        context = dict()
        context['processes'] = reverse('api:tools-process-list', request=request, format=format)
        context['registrations'] = reverse('api:tools-registration-list', request=request, format=format)
        context['dect'] = reverse('api:tools-dect-lookup', request=request, format=format)
        return Response(context)

class ProcessDetailAPIViewSet(ModelViewSet):
    queryset = models.Process.objects.all()
    serializer_class = serializers.ProcessSerializer


class RegistrationAPIViewSet(ViewSet):
    lookup_value_regex = '[^/]+'       #Just add this line & change your Regex if needed
    permission_classes = [IsAdminUser]

    def list(self, request, format=None):
        return Response()

    def retrieve(self, request, pk, format=None):
        user_id = pk
        public_device_ids = [12,24,25,31,37,40,41,44]
        requests.packages.urllib3.disable_warnings()
        palladion = Palladion(**settings.PLATFORMS['palladion'])
        pl_devices = { x['id']: x for x in palladion.devices() }
        bw = BroadWorks(**settings.PLATFORMS['broadworks'])
        bw.LoginRequest14sp4()

        if '@' in user_id:
            line_port = user_id
            user_line_id = line_port.split('@')[0]
            regs = sorted([reg for reg in palladion.registrations(user_line_id) if reg['dev_id'] in public_device_ids], key=lambda reg: reg['dev_id'])
            registrations = list()
            for reg in regs:
                registration = dict()
                if 'dev_id' in reg:
                    if reg['dev_id'] in pl_devices:
                        registration['device'] = pl_devices[reg['dev_id']]['name']
                    else:
                        registration['device'] = 'Unknown'
                if 'expires' in reg:
                    registration['expires'] = reg['expires']
                if 'expires_in' in reg:
                    registration['expires_in'] = reg['expires_in']
                if 'first_seen_ts' in reg:
                    registration['first_seen'] = reg['first_seen_ts']
                if 'last_seen_ts' in reg:
                    registration['last_seen'] = reg['last_seen_ts']
                if 'last_refreshed_ts' in reg:
                    registration['last_refreshed'] = reg['last_refreshed_ts']
                if 'srcip' in reg:
                    registration['ip_address'] = reg['srcip']
                if 'usrdev' in reg:
                    registration['user_agent'] = reg['usrdev']
                registrations.append(registration)
            if len(registrations) > 0:
                status = "Registered"
            else:
                status = "Not registered"
            rval = Response({
                "status": status,
                "registrations": registrations,
                "line_port": line_port,
            })
        else:
            user_id = None
            user_detail = None
            # Retrieve User by User Id
            resp1 = bw.UserGetRequest19(pk)
            if resp1['type'] != 'c:ErrorResponse':
                user_detail = resp1['data']
                user_id = pk
            if not user_id:
                # Retrieve User by DN
                resp2 = bw.UserGetListInSystemRequest(searchCriteriaDn=OrderedDict([('mode', 'Contains'), ('value', pk), ('isCaseInsensitive', True)]))
                if resp2['type'] != 'c:ErrorResponse' and 'userTable' in resp2['data'] and len(resp2['data']['userTable']) == 1:
                    user = resp2['data']['userTable'][0]
                    user_id = user['User Id']
            if not user_id:
                # No user could be found :-(
                rval = Response({"status": "User Id not found"})
                bw.LogoutRequest()
                return rval
            else:
                if not user_detail:
                    resp3 = bw.UserGetRequest19(user_id)
                    if resp3['type'] != 'c:ErrorResponse':
                        user_detail = resp3['data']
                    else:
                        rval = Response({"status": "User Id lookup error"})
                        bw.LogoutRequest()
                        return rval
                if 'accessDeviceEndpoint' in user_detail:
                    line_port = user_detail['accessDeviceEndpoint']['linePort']
                    user_line_id = line_port.split('@')[0]
                    regs = sorted([reg for reg in palladion.registrations(user_line_id) if reg['dev_id'] in public_device_ids], key=lambda reg: reg['dev_id'])
                    registrations = list()
                    for reg in regs:
                        registration = dict()
                        if 'dev_id' in reg:
                            if reg['dev_id'] in pl_devices:
                                registration['device'] = pl_devices[reg['dev_id']]['name']
                            else:
                                registration['device'] = 'Unknown'
                        if 'expires' in reg:
                            registration['expires'] = reg['expires']
                        if 'expires_in' in reg:
                            registration['expires_in'] = reg['expires_in']
                        if 'first_seen_ts' in reg:
                            registration['first_seen'] = reg['first_seen_ts']
                        if 'last_seen_ts' in reg:
                            registration['last_seen'] = reg['last_seen_ts']
                        if 'last_refreshed_ts' in reg:
                            registration['last_refreshed'] = reg['last_refreshed_ts']
                        if 'srcip' in reg:
                            registration['ip_address'] = reg['srcip']
                        if 'usrdev' in reg:
                            registration['user_agent'] = reg['usrdev']
                        registrations.append(registration)
                    if len(registrations) > 0:
                        status = "Registered"
                    else:
                        status = "Not registered"
                    rval = Response({
                        "broadworks": {
                            "provider_id": user_detail['serviceProviderId'],
                            "group_id": user_detail['groupId'],
                            "user_id": user_id,
                            "first_name": user_detail['firstName'],
                            "last_name": user_detail['lastName']
                        },
                        "status": status,
                        "registrations": registrations,
                        "line_port": line_port,
                    })
                else:
                    rval = Response({"status": "Not found"})
        bw.LogoutRequest()
        return rval


class DeviceDectLookupAPIView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request):
        provider_id = request.data.get('provider_id')
        group_id = request.data.get('group_id')
        device_name = request.data.get('device_name')
        bw = BroadWorks(**settings.PLATFORMS['broadworks'])
        bw.LoginRequest14sp4()

        # Get Device Tags
        resp1 = bw.GroupAccessDeviceCustomTagGetListRequest(provider_id, group_id, device_name)
        tags = {x['Tag Name']: x['Tag Value'] for x in resp1['data']['deviceCustomTagsTable']}
        data = list()
        for name,value in tags.items():
            m = re.search('^%HANDSET(?P<handset>\d+)LINE(?P<line>\d+)_LINEPORT%$', name)
            if m:
                gp = m.groupdict()
                user_id = tags.get('%HANDSET{}LINE{}_USERID%'.format(gp['handset'], gp['line']))
                data.append({'handset': gp['handset'], 'line': gp['line'], 'lineport': value, 'user_id': user_id})

        rval = Response(data)
        bw.LogoutRequest()
        return rval
