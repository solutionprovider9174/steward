# Python
import io
import os
import csv
import re
import datetime
import traceback
from collections import OrderedDict

# Django
from django.utils import timezone
from django.conf import settings

# Application
from tools.models import Process, ProcessContent

# Third Party
from lib.pybw.broadworks import BroadWorks, Nil


def firmware_report(process_id):
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

    try:
        print("Process {}: {} -> {}".format(process_id, process.method, process.parameters))
        process.status = process.STATUS_RUNNING
        process.save(update_fields=['status'])

        content = dict()

        # Retrieve Data
        provider_id = process.parameters.get('provider_id', None)
        group_id = process.parameters.get('group_id', None)

        # Login to BroadWorks
        bw = BroadWorks(url=process.platform.uri,
                        username=process.platform.username,
                        password=process.platform.password)
        bw.LoginRequest14sp4()

        user_agent_regex = re.compile('^(?P<device_type>PolycomVVX-VVX_\d{3}|PolycomSoundStationIP-SSIP_\d{4}|PolycomSoundPointIP-SPIP_\d{3})-UA\/(?P<version>[\d\.]+)$')
        device_types = ['Polycom', 'Polycom_VVX300', 'Polycom_VVX400', 'Polycom_VVX500', 'Polycom_VVX600']

        summary_html.write('<table class="table table-striped table-bordered table-hover">\n')
        summary_html.write('<tr>\n')
        summary_html.write('\t<th>Provider Id</th><th>Group Id</th><th>Device Type</th><th>Device Name</th><th>Version</th><th>User Agent</th><th>Registered</th>\n')
        summary_html.write('</tr>\n')
        summary_html.write('<tbody>\n')
        summary_raw.write('"Provider Id","Group Id","Device Type","Device Name","Version","User Agent","Registered"\n')
        # Process Devices
        for device_type in device_types:
            if provider_id and group_id:
                resp3 = bw.SystemAccessDeviceGetAllRequest(searchCriteriaExactDeviceType={'deviceType': device_type},
                                                           searchCriteriaExactDeviceServiceProvider={'serviceProviderId': provider_id},
                                                           searchCriteriaGroupId=OrderedDict([
                                                                                              ('mode', 'Equal To'),
                                                                                              ('value', group_id),
                                                                                              ('isCaseInsensitive', False),
                                                                                            ]))
            elif provider_id:
                resp3 = bw.SystemAccessDeviceGetAllRequest(searchCriteriaExactDeviceType={'deviceType': device_type},
                                                           searchCriteriaExactDeviceServiceProvider={'serviceProviderId': provider_id})
            else:
                resp3 = bw.SystemAccessDeviceGetAllRequest(searchCriteriaExactDeviceType={'deviceType': device_type})
            devices = resp3['data']['accessDeviceTable']
            for idx, device in enumerate(devices):
                device_provider_id = device['Service Provider Id']
                device_group_id = device['Group Id']
                device_name = device['Device Name']

                if device_provider_id and device_group_id and device_name:
                    resp5 = bw.GroupAccessDeviceGetUserListRequest(device_provider_id, device_group_id, device_name)
                    users = resp5['data']['deviceUserTable']
                elif device_provider_id and device_name:
                    resp5 = bw.ServiceProviderAccessDeviceGetUserListRequest(device_provider_id, device_name)
                    users = resp5['data']['deviceUserTable']
                else:
                    continue
                device_user_agent = None
                device_registered = False
                device_uri = None
                for user in users:
                    user_id = user['User Id']
                    resp6 = bw.UserGetRegistrationListRequest(user_id)
                    registrations = resp6['data']['registrationTable']
                    for reg in registrations:
                        if reg['Device Name'] == device_name:
                            device_user_agent = reg['User Agent']
                            device_registered = True
                            device_uri = reg['URI']
                            break
                    else:
                        continue
                    break
                if device_registered:
                    m = user_agent_regex.match(device_user_agent)
                    if m:
                        reg_device_type = m.group('device_type')
                        reg_version = m.group('version')
                        summary_raw.write('"{}","{}","{}","{}","{}","{}","{}"\n'.format(device_provider_id, device_group_id, device_type, device_name, reg_version, device_user_agent, device_registered))
                        summary_html.write('<tr>\n')
                        summary_html.write('\t<td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td>\n'.format(device_provider_id, device_group_id, device_type, device_name, reg_version, device_user_agent, device_registered))
                        summary_html.write('</tr>\n')
                    else:
                        summary_raw.write('"{}","{}","{}","{}","{}","{}","{}"\n'.format(device_provider_id, device_group_id, device_type, device_name, '', device_user_agent, device_registered))
                        summary_html.write('<tr>\n')
                        summary_html.write('\t<td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td>\n'.format(device_provider_id, device_group_id, device_type, device_name, '', device_user_agent, device_registered))
                        summary_html.write('</tr>\n')
                else:
                    # Not registered, so blank version/UA
                    summary_raw.write('"{}","{}","{}","{}","{}","{}","{}"\n'.format(device_provider_id, device_group_id, device_type, device_name, '', '', device_registered))
                    summary_html.write('<tr>\n')
                    summary_html.write('\t<td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td>\n'.format(device_provider_id, device_group_id, device_type, device_name, '', '', device_registered))
                    summary_html.write('</tr>\n')

        # after things are finished
        # end html
        summary_html.write('</tbody>\n')
        summary_html.write('</table>\n')
        # save data
        process.status = process.STATUS_COMPLETED
        process.end_timestamp = timezone.now()
        process.save(update_fields=['status', 'end_timestamp'])
        bw.LogoutRequest()
    except Exception:
        process.status = process.STATUS_ERROR
        process.end_timestamp = timezone.now()
        process.exception = traceback.format_exc()
        process.save(update_fields=['status', 'exception', 'end_timestamp'])

    # Cleanup
    summary_html.close()
    summary_raw.close()
