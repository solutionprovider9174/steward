# Python
import argparse
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
from routing.models import FraudBypass, Number, OutboundRoute, RemoteCallForward, Route, Transmission

# Third Party
import paramiko
from lib.pyutil.util import Util


class Command(BaseCommand):
    help = 'Export MetaSwitch to UDA file'

    def __init__(self, *args, **kwargs):
        super(Command, self).__init__(*args, **kwargs)
        self._funcs = {
            'fraud-bypass': self.export_fraud_bypass,
            'outbound-route': self.export_outbound_route,
            'remote-call-forward': self.export_remote_call_forward,
            'route': self.export_route,
        }

    def add_arguments(self, parser):
        parser.add_argument('--type', dest='type', choices=self._funcs.keys(), required=True)
        parser.add_argument('output_file', type=argparse.FileType('w'))

    def handle(self, *args, **options):
        # Call function from self._funcs dict
        output_file = options['output_file']
        func = self._funcs[options['type']]
        func(output_file)

    @transaction.non_atomic_requests
    def export_fraud_bypass(self, output_file):
        f = output_file
        # generate file
        context = dict()
        context['object_list'] = FraudBypass.objects.all()
        f.write(str(loader.render_to_string('routing/NVFILE_fraud_bypass.txt', context)))
        f.close()
        self.stdout.write(self.style.SUCCESS('Successfully exported Fraud Bypass file to {}'.format(f.name)))

    @transaction.non_atomic_requests
    def export_remote_call_forward(self, output_file):
        f = output_file
        # generate file
        context = dict()
        context['object_list'] = RemoteCallForward.objects.all()
        f.write(str(loader.render_to_string('routing/NVFILE_remote_call_forward.txt', context)))
        f.close()
        self.stdout.write(self.style.SUCCESS('Successfully exported Remote Call Forward file to {}'.format(f.name)))

    @transaction.non_atomic_requests
    def export_route(self, output_file):
        f = output_file
        # generate file
        context = dict()
        context['routes'] = Route.objects.filter(type=Route.TYPE_CHOICE_INTERNAL)
        context['numbers'] = Number.objects.filter(active=True).select_related('route')
        f.write(str(loader.render_to_string('routing/NVFILE_route.txt', context)))
        f.close()
        self.stdout.write(self.style.SUCCESS('Successfully exported Route file to {}'.format(f.name)))

    @transaction.non_atomic_requests
    def export_outbound_route(self, output_file):
        f = output_file
        # generate file
        context = dict()
        context['routes'] = Route.objects.filter(type=Route.TYPE_CHOICE_OUTBOUND)
        context['object_list'] = OutboundRoute.objects.all().select_related('end_office_route', 'long_distance_route')
        f.write(str(loader.render_to_string('routing/NVFILE_outbound_route.txt', context)))
        f.close()
        self.stdout.write(self.style.SUCCESS('Successfully exported Route file to {}'.format(f.name)))
