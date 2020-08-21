# Python
from shutil import copyfile
import os
import tempfile
import time

# Django
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.template import loader
from django.utils import timezone

# Application
from routing.models import FraudBypass, FraudBypassHistory, Number, OutboundRoute, OutboundRouteHistory, RemoteCallForward, RemoteCallForwardHistory, Route, Transmission

# Third Party
import paramiko
from lib.pyutil.util import Util


class Command(BaseCommand):
    help = 'Upload files to MetaSwitch'

    def __init__(self, *args, **kwargs):
        super(Command, self).__init__(*args, **kwargs)
        self._funcs = {
            'fraud-bypass': self.transfer_fraud_bypass,
            'outbound-route': self.transfer_outbound_route,
            'remote-call-forward': self.transfer_remote_call_forward,
            'route': self.transfer_route,
        }

    def add_arguments(self, parser):
        parser.add_argument('--type', dest='type', choices=self._funcs.keys(), required=True)

    def handle(self, *args, **options):
        # Call function from self._funcs dict
        func = self._funcs[options['type']]
        func()

    @transaction.non_atomic_requests
    def transfer_fraud_bypass(self):
        self.stdout.write(self.style.SUCCESS('Transfering Fraud Bypass File'))
        try:
            last_transmission = Transmission.objects.filter(
                result_state=Transmission.RESULT_CHOICE_SUCCESS,
                type=Transmission.TYPE_CHOICE_FRAUD_BYPASS).latest('last_modified')
        except Transmission.DoesNotExist:
            last_transmission = None
        try:
            last_modified = FraudBypassHistory.objects.latest('modified').modified
        except FraudBypassHistory.DoesNotExist:
            last_modified = None
        if last_transmission and last_transmission.last_modified and last_modified and last_transmission.last_modified >= last_modified:
            self.stdout.write(self.style.SUCCESS('No modifications since last transmission'))
            return
        transmission = Transmission.objects.create(result_state=Transmission.RESULT_CHOICE_PENDING, type=Transmission.TYPE_CHOICE_FRAUD_BYPASS, last_modified=last_modified)
        meta_settings = settings.PLATFORMS['metaswitch']
        dest_filename = meta_settings['filenames']['fraud-bypass']

        # generate file
        context = dict()
        context['object_list'] = FraudBypass.objects.all()
        f = tempfile.NamedTemporaryFile(delete=False)
        f.write(loader.render_to_string('routing/NVFILE_fraud_bypass.txt', context).encode())
        f.close()

        # transfer file
        if self._transfer_file(transmission, f, dest_filename):
            self._copy_to_meta_backup_path(f, dest_filename)
            self.stdout.write(self.style.SUCCESS('Successfully transfered Fraud Bypass file'))
        else:
            self.stdout.write(self.style.ERROR('Failed to transfer Fraud Bypass file'))

        # Cleanup
        os.remove(f.name)

    @transaction.non_atomic_requests
    def transfer_remote_call_forward(self):
        self.stdout.write(self.style.SUCCESS('Transfering Remote Call Forward File'))
        try:
            last_transmission = Transmission.objects.filter(result_state=Transmission.RESULT_CHOICE_SUCCESS, type=Transmission.TYPE_CHOICE_REMOTE_CALL_FORWARD).latest('last_modified')
        except Transmission.DoesNotExist:
            last_transmission = None
        try:
            last_modified = RemoteCallForwardHistory.objects.latest('modified').modified
        except RemoteCallForwardHistory.DoesNotExist:
            last_modified = None
        if last_transmission and last_transmission.last_modified and last_modified and last_transmission.last_modified >= last_modified:
            self.stdout.write(self.style.SUCCESS('No modifications since last transmission'))
            return
        transmission = Transmission.objects.create(result_state=Transmission.RESULT_CHOICE_PENDING, type=Transmission.TYPE_CHOICE_REMOTE_CALL_FORWARD, last_modified=last_modified)
        meta_settings = settings.PLATFORMS['metaswitch']
        dest_filename = meta_settings['filenames']['remote-call-forward']

        # generate file
        context = dict()
        context['object_list'] = RemoteCallForward.objects.all()
        f = tempfile.NamedTemporaryFile(delete=False)
        f.write(loader.render_to_string('routing/NVFILE_remote_call_forward.txt', context).encode())
        f.close()

        # transfer file
        if self._transfer_file(transmission, f, dest_filename):
            self._copy_to_meta_backup_path(f, dest_filename)
            self.stdout.write(self.style.SUCCESS('Successfully transfered Remote Call Forward file'))
        else:
            self.stdout.write(self.style.ERROR('Failed to transfer Remote Call Forward file'))

        # Cleanup
        os.remove(f.name)

    @transaction.non_atomic_requests
    def transfer_route(self):
        self.stdout.write(self.style.SUCCESS('Transfering Route File'))
        try:
            last_transmission = Transmission.objects.filter(result_state=Transmission.RESULT_CHOICE_SUCCESS, type=Transmission.TYPE_CHOICE_ROUTE).latest('last_modified')
        except Transmission.DoesNotExist:
            last_transmission = None
        try:
            last_modified = Number.objects.latest('modified').modified
        except Number.DoesNotExist:
            last_modified = None
        if last_transmission and last_transmission.last_modified and last_modified and last_transmission.last_modified >= last_modified:
            self.stdout.write(self.style.SUCCESS('No modifications since last transmission'))
            return
        transmission = Transmission.objects.create(result_state=Transmission.RESULT_CHOICE_PENDING, type=Transmission.TYPE_CHOICE_ROUTE, last_modified=last_modified)
        meta_settings = settings.PLATFORMS['metaswitch']
        dest_filename = meta_settings['filenames']['route']

        # generate file
        context = dict()
        context['routes'] = Route.objects.filter(type=Route.TYPE_CHOICE_INTERNAL)
        context['numbers'] = Number.objects.filter(active=True).select_related('route')
        f = tempfile.NamedTemporaryFile(delete=False)
        f.write(loader.render_to_string('routing/NVFILE_route.txt', context).encode())
        f.close()

        # transfer file
        if self._transfer_file(transmission, f, dest_filename):
            self._copy_to_meta_backup_path(f, dest_filename)
            self.stdout.write(self.style.SUCCESS('Successfully transfered Route file'))
        else:
            self.stdout.write(self.style.ERROR('Failed to transfer Route file'))

        # Cleanup
        os.remove(f.name)

    @transaction.non_atomic_requests
    def transfer_outbound_route(self):
        self.stdout.write(self.style.SUCCESS('Transfering Outbound Route File'))
        try:
            last_transmission = Transmission.objects.filter(result_state=Transmission.RESULT_CHOICE_SUCCESS, type=Transmission.TYPE_CHOICE_OUTBOUND_ROUTE).latest('last_modified')
        except Transmission.DoesNotExist:
            last_transmission = None
        try:
            last_modified = OutboundRouteHistory.objects.latest('modified').modified
        except OutboundRouteHistory.DoesNotExist:
            last_modified = None
        if last_transmission and last_transmission.last_modified and last_transmission.last_modified >= last_modified:
            self.stdout.write(self.style.SUCCESS('No modifications since last transmission'))
            return
        transmission = Transmission.objects.create(result_state=Transmission.RESULT_CHOICE_PENDING, type=Transmission.TYPE_CHOICE_OUTBOUND_ROUTE, last_modified=last_modified)
        meta_settings = settings.PLATFORMS['metaswitch']
        dest_filename = meta_settings['filenames']['outbound-route']

        # generate file
        context = dict()
        context['routes'] = Route.objects.filter(type=Route.TYPE_CHOICE_OUTBOUND)
        context['object_list'] = OutboundRoute.objects.all().select_related('end_office_route', 'long_distance_route')
        f = tempfile.NamedTemporaryFile(delete=False)
        f.write(loader.render_to_string('routing/NVFILE_outbound_route.txt', context).encode())
        f.close()

        # transfer file
        if self._transfer_file(transmission, f, dest_filename):
            self._copy_to_meta_backup_path(f, dest_filename)
            self.stdout.write(self.style.SUCCESS('Successfully transfered Outbound Route file'))
        else:
            self.stdout.write(self.style.ERROR('Failed to transfer Outbound Route file'))

        # Cleanup
        os.remove(f.name)

    def _copy_to_meta_backup_path(self, local_file, dest_filename):
        """Copy given local file to metaswitch backup directory.

        Args:
            local_file (NamedTemporaryFile): Source file
            dest_filename (str): Destination filename
        """
        meta_settings = settings.PLATFORMS['metaswitch']
        local_pathname = meta_settings['pathnames']['local']
        local_filename = os.path.join(local_pathname, dest_filename)
        copyfile(local_file.name, local_filename)

    def _transfer_file(self, transmission, local_file, remote_filename):
        rval = None
        try:
            file_hash = Util.md5(local_file.name)
            transmission.result_state = Transmission.RESULT_CHOICE_TRANSFERING
            transmission.checksum = file_hash
            transmission.save(update_fields=['result_state', 'checksum', 'last_modified'])

            meta_settings = settings.PLATFORMS['metaswitch']
            transport = paramiko.Transport((meta_settings['host'], meta_settings['port']))
            transport.connect(username=meta_settings['username'], password=meta_settings['password'])
            sftp = paramiko.sftp_client.SFTPClient.from_transport(transport)
            sftp.chdir(path=meta_settings['pathnames']['remote'])
            sftp.put(local_file.name, remote_filename)

            count = 0
            file_list = sftp.listdir()
            while remote_filename in file_list:
                if count * 5 >= 90:
                    raise Exception('File not retreived by remote server, aborting after {} seconds'.format(count*5))
                count += 1
                time.sleep(5)
                file_list = sftp.listdir()

            count = 0
            ok_filename = '{}@ok'.format(remote_filename)
            error_filename = '{}@fail'.format(remote_filename)
            file_list = sftp.listdir()
            while ok_filename not in file_list and error_filename not in file_list:
                if count * 5 >= 90:
                    raise Exception('File not processed by remote server, aborting after {} seconds'.format(count*5))
                count += 1
                time.sleep(5)
                file_list = sftp.listdir()

            if ok_filename in file_list:
                # retreive ok file
                transmission.result_state = Transmission.RESULT_CHOICE_SUCCESS
                transmission.result_timestamp = timezone.now()
                f = tempfile.NamedTemporaryFile(delete=False)
                f.close()
                sftp.get(ok_filename, f.name)
                with open(f.name) as r:
                    content = r.read()
                    transmission.result_data = content
                os.remove(f.name)
                del(f)
                rval = True
            elif error_filename in file_list:
                # retrieve error file
                transmission.result_state = Transmission.RESULT_CHOICE_FAILURE
                transmission.result_timestamp = timezone.now()
                f = tempfile.NamedTemporaryFile(delete=False)
                f.close()
                sftp.get(error_filename, f.name)
                with open(f.name) as r:
                    content = r.read()
                    transmission.result_data = content
                os.remove(f.name)
                del(f)
                rval = False
            transmission.save()
            return rval
        except Exception as e:
            transmission.result_state = Transmission.RESULT_CHOICE_FAILURE
            transmission.result_timestamp = timezone.now()
            transmission.result_data = str(e)
            transmission.save()
            return False
