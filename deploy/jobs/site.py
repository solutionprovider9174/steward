# Python
import io
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
from deploy.models import Site, Device, DeviceType

# Third Party
from lib.pyutil.util import Util
from lib.pybw.broadworks import BroadWorks, Nil


def sync_device(id):
    device = Device.objects.get(id=id)
    device.state = Device.STATE_RUNNING
    device.save(update_fields=['state'])
    site = device.site
    # Sync with BroadWorks
    try:
        bw = BroadWorks(**settings.PLATFORMS['broadworks'])
        bw.LoginRequest14sp4()
        resp0 = bw.GroupAccessDeviceGetRequest18sp1(site.provider_id, site.group_id, device.name)
        if resp0['type'] != 'GroupAccessDeviceGetResponse18sp1':
            raise Exception(resp0['data']['summaryEnglish'])
        bw_device = resp0['data']

        if bw_device['deviceType'] != device.device_type.switch_type:
            # Get Line/ports
            resp1 = bw.GroupAccessDeviceGetUserListRequest(site.provider_id, site.group_id, device.name)
            if resp1['type'] != 'GroupAccessDeviceGetUserListResponse':
                raise Exception(resp1['data']['summaryEnglish'])
            line_ports = sorted(resp1['data']['deviceUserTable'], key=lambda k: k['Order'])
            # Get tags
            resp2 = bw.GroupAccessDeviceCustomTagGetListRequest(site.provider_id, site.group_id, device.name)
            if resp2['type'] != 'GroupAccessDeviceCustomTagGetListResponse':
                raise Exception(resp2['data']['summaryEnglish'])
            device_tags = resp2['data']['deviceCustomTagsTable']
            # Attempt device reboot (for good measure)
            resp3 = bw.GroupAccessDeviceResetRequest(site.provider_id, site.group_id, device.name)
            if resp3['type'] != 'c:SuccessResponse':
                raise Exception(resp3['data']['summaryEnglish'])
            # Remove associations with device
            for line_port in line_ports:
                if line_port['Endpoint Type'] == 'Primary':
                    # Remove Primary Line/Port from device
                    resp4 = bw.UserModifyRequest17sp4(userId=line_port['User Id'], endpoint=Nil())
                    if resp4['type'] != 'c:SuccessResponse':
                        raise Exception(resp4['data']['summaryEnglish'])
                elif line_port['Endpoint Type'] == 'Shared Call Appearance':
                    # Remove SCA from device
                    access_device_endpoint = OrderedDict()
                    access_device_endpoint['accessDevice'] = OrderedDict()
                    access_device_endpoint['accessDevice']['deviceLevel'] = 'Group'
                    access_device_endpoint['accessDevice']['deviceName'] = device.name
                    access_device_endpoint['linePort'] = line_port['Line/Port']
                    resp4 = bw.UserSharedCallAppearanceDeleteEndpointListRequest14(line_port['User Id'], access_device_endpoint)
                    if resp4['type'] != 'c:SuccessResponse':
                        raise Exception(resp4['data']['summaryEnglish'])
            # Delete device
            resp5 = bw.GroupAccessDeviceDeleteRequest(site.provider_id, site.group_id, device.name)
            if resp5['type'] != 'c:SuccessResponse':
                raise Exception(resp5['data']['summaryEnglish'])
            # Create device
            device.password = Util.random_password(length=16)
            resp6 = bw.GroupAccessDeviceAddRequest14(site.provider_id, site.group_id, device.name, device.device_type.switch_type, username=device.name, password=device.password)
            if resp6['type'] != 'c:SuccessResponse':
                raise Exception(resp6['data']['summaryEnglish'])
            device.save(update_fields=['password'])
            # Add tags
            for tag in device_tags:
                resp7 = bw.GroupAccessDeviceCustomTagAddRequest(site.provider_id, site.group_id, device.name, tag['Tag Name'], tag['Tag Value'])
                if resp7['type'] != 'c:SuccessResponse':
                    raise Exception(resp7['data']['summaryEnglish'])
            # Assign Line/ports
            for line_port in line_ports:
                if line_port['Endpoint Type'] == 'Primary':
                    # Add Primary Line/Port to new device
                    access_device_endpoint = OrderedDict()
                    access_device_endpoint['accessDevice'] = OrderedDict()
                    access_device_endpoint['accessDevice']['deviceLevel'] = 'Group'
                    access_device_endpoint['accessDevice']['deviceName'] = device.name
                    access_device_endpoint['linePort'] = line_port['Line/Port']
                    resp8 = bw.UserModifyRequest17sp4(userId=line_port['User Id'], endpoint={'accessDeviceEndpoint': access_device_endpoint})
                    if resp8['type'] != 'c:SuccessResponse':
                        raise Exception(resp8['data']['summaryEnglish'])
                elif line_port['Endpoint Type'] == 'Shared Call Appearance':
                    # Add SCA to new device
                    access_device_endpoint = OrderedDict()
                    access_device_endpoint['accessDevice'] = OrderedDict()
                    access_device_endpoint['accessDevice']['deviceLevel'] = 'Group'
                    access_device_endpoint['accessDevice']['deviceName'] = device.name
                    access_device_endpoint['linePort'] = line_port['Line/Port']
                    resp8 = bw.UserSharedCallAppearanceAddEndpointRequest14sp2(line_port['User Id'], access_device_endpoint, isActive=True, allowOrigination=True, allowTermination=True)
                    if resp8['type'] != 'c:SuccessResponse':
                        raise Exception(resp8['data']['summaryEnglish'])
            # Change SIP Authentication password for the Primary User
            for line_port in line_ports:
                if line_port['Endpoint Type'] == 'Primary':
                    resp9 = bw.UserAuthenticationModifyRequest(userId=line_port['User Id'], newPassword=Util.random_password(length=16))
                    if resp9['type'] != 'c:SuccessResponse':
                        raise Exception(resp9['data']['summaryEnglish'])
            # Rebuild the device config files
            resp10 = bw.GroupCPEConfigRebuildDeviceConfigFileRequest(site.provider_id, site.group_id, device.name)
            if resp10['type'] != 'c:SuccessResponse':
                raise Exception(resp10['data']['summaryEnglish'])
        else:
            # Update device profile password
            device.password = Util.random_password(length=16)
            resp1 = bw.GroupAccessDeviceModifyRequest14(site.provider_id, site.group_id, device.name, username=device.name, password=device.password)
            print(resp1)
            if resp1['type'] != 'c:SuccessResponse':
                raise Exception(resp1['data']['summaryEnglish'])
            # Get Line/ports
            resp2 = bw.GroupAccessDeviceGetUserListRequest(site.provider_id, site.group_id, device.name)
            if resp2['type'] != 'GroupAccessDeviceGetUserListResponse':
                raise Exception(resp2['data']['summaryEnglish'])
            line_ports = sorted(resp2['data']['deviceUserTable'], key=lambda k: k['Order'])
            # Change SIP Authentication password for the Primary User
            for line_port in line_ports:
                if line_port['Endpoint Type'] == 'Primary':
                    resp3 = bw.UserAuthenticationModifyRequest(userId=line_port['User Id'], newPassword=Util.random_password(length=16))
                    if resp3['type'] != 'c:SuccessResponse':
                        raise Exception(resp3['data']['summaryEnglish'])
            # Rebuild the device config files
            resp4 = bw.GroupCPEConfigRebuildDeviceConfigFileRequest(site.provider_id, site.group_id, device.name)
            if resp4['type'] != 'c:SuccessResponse':
                raise Exception(resp4['data']['summaryEnglish'])
            device.save(update_fields=['password'])
        device.state = Device.STATE_PROVISIONED
        device.save(update_fields=['state'])
        bw.LogoutRequest()
    except Exception as e:
        device.state = Device.STATE_ERROR
        device.save(update_fields=['state'])
        raise RuntimeError(e)


def sync_site(id):
    obj = Site.objects.get(id=id)
    obj.sync_state = Site.SYNC_STATE_RUNNING
    obj.save(update_fields=['sync_state'])
    # Sync with BroadWorks
    try:
        bw = BroadWorks(**settings.PLATFORMS['broadworks'])
        bw.LoginRequest14sp4()
        # Update site information
        resp0 = bw.GroupGetRequest14sp7(obj.provider_id, obj.group_id)
        data = resp0['data']
        if 'groupName' in data:
            obj.name = data['groupName']
        else:
            obj.name = ''
        if 'address' in data:
            if 'addressLine1' in data['address']:
                obj.address_line1 = data['address']['addressLine1']
            else:
                obj.address_line1 = ''
            if 'addressLine2' in data['address']:
                obj.address_line2 = data['address']['addressLine2']
            else:
                obj.address_line2 = ''
            if 'city' in data['address']:
                obj.city = data['address']['city']
            else:
                obj.city = ''
            if 'stateOrProvince' in data['address']:
                obj.city = data['address']['stateOrProvince']
            else:
                obj.city = ''
            if 'zipOrPostalCode' in data['address']:
                obj.zip_code = data['address']['zipOrPostalCode']
            else:
                obj.zip_code = ''
            obj.save()
        # Get devices
        device_names = []
        resp1 = bw.GroupAccessDeviceGetListRequest(obj.provider_id, obj.group_id)
        if 'accessDeviceTable' in resp1['data']:
            devices = resp1['data']['accessDeviceTable']
            for device in devices:
                device_name = device.get('Device Name')
                device_type = device.get('Device Type')
                device_mac = device.get('MAC Address')
                primary_user_id = None
                primary_user_name = None
                primary_user_phone_number = None
                primary_user_extension = None
                line_port_count = 0

                resp2 = bw.GroupAccessDeviceGetUserListRequest(obj.provider_id, obj.group_id, device_name)
                if 'deviceUserTable' in resp2['data'] and len(resp2['data']['deviceUserTable']) > 0:
                    line_ports = sorted(resp2['data']['deviceUserTable'], key=lambda k: "None" if k['Order'] is None else k['Order'])
                    line_port_count = len(line_ports)
                    for line_port in line_ports:
                        if line_port['Endpoint Type'] == 'Primary':
                            primary_user_id = line_port['User Id']
                            try:
                                resp3 = bw.UserGetRequest19(primary_user_id)
                                primary_user_name = ' '.join([resp3['data']['firstName'], resp3['data']['lastName']])
                                if 'phoneNumber' in resp3['data']:
                                    primary_user_phone_number = resp3['data']['phoneNumber']
                                if 'extension' in resp3['data']:
                                    primary_user_extension = resp3['data']['extension']
                            except Exception as e:
                                pass

                if primary_user_phone_number and primary_user_extension:
                    primary_user_dn = '{}x{}'.format(primary_user_phone_number, primary_user_extension)
                elif primary_user_phone_number:
                    primary_user_dn = primary_user_phone_number
                elif primary_user_extension:
                    primary_user_dn = 'x{}'.format(primary_user_extension)
                else:
                    primary_user_dn = ''

                try:
                    dt = DeviceType.objects.get(switch_type=device_type)
                except DeviceType.DoesNotExist as e:
                    dt = None
                Device.objects.update_or_create(site=obj, name=device_name,
                                                defaults={'device_type': dt,
                                                          # 'serial': device_mac,
                                                          'primary_user_id': primary_user_id,
                                                          'primary_user_name': primary_user_name,
                                                          'primary_user_dn': primary_user_dn,
                                                          'line_port_count': line_port_count})
                device_names.append(device_name)
        # Remove devices that are not in BroadWorks
        for device in obj.devices.all():
            if device.name not in device_names:
                device.delete()
        bw.LogoutRequest()
    except Exception as e:
        obj.sync_state = Site.SYNC_STATE_ERROR
        obj.save(update_fields=['sync_state'])
        raise RuntimeError(e)
    obj.sync_state = Site.SYNC_STATE_CLEAR
    obj.save(update_fields=['sync_state'])
