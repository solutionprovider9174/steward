# Python
import argparse
import csv
import re
import time

# Django
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.template import loader
from django.utils import timezone

# Application
from routing.models import (
    FraudBypass, FraudBypassHistory, Number, NumberHistory, OutboundRoute,
    OutboundRouteHistory, RemoteCallForward, RemoteCallForwardHistory, Route,
)

# Third Party
import paramiko
from lib.pyutil.util import Util


class Command(BaseCommand):
    help = 'Import data from MetaSwitch UDA files'

    def __init__(self, *args, **kwargs):
        super(Command, self).__init__(*args, **kwargs)
        self._funcs = {
            'fraud-bypass': self.import_fraud_bypass,
            'outbound-route': self.import_outbound_route,
            'remote-call-forward': self.import_remote_call_forward,
            'route': self.import_route,
        }

    def add_arguments(self, parser):
        parser.add_argument('--type', dest='type', choices=self._funcs.keys(), required=True)
        parser.add_argument('--truncate', dest='truncate', action='store_true', default=False)
        parser.add_argument('input_file', type=argparse.FileType('r'))

    def handle(self, *args, **options):
        # Call function from self._funcs dict
        input_file = options['input_file']
        truncate = options['truncate']
        func = self._funcs[options['type']]
        func(input_file, truncate)

    @transaction.non_atomic_requests
    def import_fraud_bypass(self, input_file, truncate=False):
        create_count = 0
        update_count = 0
        error_count = 0
        User = get_user_model()
        steward_user,_ = User.objects.get_or_create(username='system', defaults={'first_name':'System', 'last_name':''})

        if truncate:
            FraudBypass.objects.all().delete()
            FraudBypassHistory.objects.all().delete()

        with open(input_file.name) as f:
            csv_file = csv.reader(f, delimiter=',')
            for row in csv_file:
                if len(row) >= 2:
                    if row[0].startswith(';') or row[0].startswith(' ') or row[0] == 'DN':
                        continue
                    number = row[0].strip()
                    if not re.match('^\d{10}$', number):
                        error_count += 1
                        self.stdout.write(self.style.ERROR('ERROR: Number {} is not 10 digits'.format(number)))
                        continue
                    trunk_number = row[1].strip()
                    if trunk_number == '999999':
                        obj, created = FraudBypass.objects.update_or_create(cc=1, number=number)
                        FraudBypassHistory.objects.create(number=number, user=steward_user, action='Imported')
                        if created:
                            create_count += 1
                        else:
                            update_count += 1
                    else:
                        error_count += 1
                        self.stdout.write(self.style.ERROR('ERROR: Trunkgroup {} is not 999999 as required for {}'.format(trunk_number, number)))
        self.stdout.write(self.style.SUCCESS('Successfully imported Fraud Bypass file >> Created: {} Updated: {} Error: {}'.format(create_count, update_count, error_count)))

    @transaction.non_atomic_requests
    def import_remote_call_forward(self, input_file, truncate=False):
        create_count = 0
        update_count = 0
        error_count = 0
        User = get_user_model()
        steward_user,_ = User.objects.get_or_create(username='system', defaults={'first_name':'System', 'last_name':''})

        if truncate:
            RemoteCallForward.objects.all().delete()
            RemoteCallForwardHistory.objects.all().delete()

        with open(input_file.name) as f:
            csv_file = csv.reader(f, delimiter=',')
            for row in csv_file:
                if len(row) == 3:
                    if row[0].startswith(';') or row[0].startswith(' ') or row[0] == 'DN':
                        continue
                    called_number = row[0].strip()
                    if not re.match('^\d{10}$', called_number):
                        error_count += 1
                        self.stdout.write(self.style.ERROR('ERROR: Called Number {} is not 10 digits'.format(called_number)))
                        continue
                    forward_number = row[2].strip()
                    if not re.match('^\d{10}$', forward_number):
                        error_count += 1
                        self.stdout.write(self.style.ERROR('ERROR: Called Number: {}, Forward Number {} is not 10 digits'.format(called_number, forward_number)))
                        continue
                    obj, created = RemoteCallForward.objects.update_or_create(called_number=called_number,
                                                                              forward_number=forward_number)
                    RemoteCallForwardHistory.objects.create(called_number=called_number,
                                                            user=steward_user,
                                                            action='Imported, Forward to {}'.format(forward_number))
                    if created:
                        create_count += 1
                    else:
                        update_count += 1
        self.stdout.write(self.style.SUCCESS('Successfully imported Fraud Bypass file >> Created: {} Updated: {} Error: {}'.format(create_count, update_count, error_count)))

    @transaction.non_atomic_requests
    def import_route(self, input_file, truncate=False):
        create_count = 0
        update_count = 0
        error_count = 0
        User = get_user_model()
        steward_user,_ = User.objects.get_or_create(username='system', defaults={'first_name':'System', 'last_name':''})
        trunks = {str(x.trunkgroup): x for x in Route.objects.filter(type=Route.TYPE_CHOICE_INTERNAL)}

        if truncate:
            Number.objects.all().delete()
            NumberHistory.objects.all().delete()

        with open(input_file.name) as f:
            csv_file = csv.reader(f, delimiter=',')
            for row in csv_file:
                if len(row) >= 2:
                    if row[0].startswith(';') or row[0].startswith(' ') or row[0] == 'DN':
                        continue
                    number = row[0].strip()
                    trunk_number = row[1].strip()
                    if trunk_number in trunks:
                        route = trunks[trunk_number]
                        obj, created = Number.objects.update_or_create(cc=1, number=number, defaults={'route': route})
                        NumberHistory.objects.create(cc=obj.cc, number=obj.number, user=steward_user, action='Imported to {}'.format(obj.route.name))
                        if created:
                            create_count += 1
                        else:
                            update_count += 1
                    else:
                        error_count += 1
                        self.stdout.write(self.style.ERROR('ERROR: Trunkgroup {} was not found for {}'.format(trunk_number, number)))
        self.stdout.write(self.style.SUCCESS('Successfully imported Route file >> Created: {} Updated: {} Error: {}'.format(create_count, update_count, error_count)))

    @transaction.non_atomic_requests
    def import_outbound_route(self, input_file, truncate=False):
        create_count = 0
        update_count = 0
        error_count = 0
        User = get_user_model()
        steward_user,_ = User.objects.get_or_create(username='system', defaults={'first_name':'System', 'last_name':''})
        trunks = {str(x.trunkgroup): x for x in Route.objects.filter(type=Route.TYPE_CHOICE_OUTBOUND)}

        if truncate:
            OutboundRoute.objects.all().delete()
            OutboundRouteHistory.objects.all().delete()

        with open(input_file.name) as f:
            csv_file = csv.reader(f, delimiter=',')
            for row in csv_file:
                if len(row) >= 3:
                    if row[0].startswith(';') or row[0].startswith(' ') or row[0] == 'DN':
                        continue
                    destination = row[0].strip()
                    end_office_trunk_number = row[1].strip()
                    long_distance_trunk_number = row[2].strip()
                    if end_office_trunk_number in trunks and long_distance_trunk_number in trunks:
                        end_office_trunk = trunks[end_office_trunk_number]
                        long_distance_trunk = trunks[long_distance_trunk_number]
                        obj, created = OutboundRoute.objects.update_or_create(number=destination, defaults={'end_office_route': end_office_trunk, 'long_distance_route': long_distance_trunk})
                        OutboundRouteHistory.objects.create(number=destination, user=steward_user, action='Imported to End Office "{}", Long Distance "{}"'.format(obj.end_office_route.name, obj.long_distance_route.name))
                        if created:
                            create_count += 1
                        else:
                            update_count += 1
                    else:
                        error_count += 1
                        if end_office_trunk_number not in trunks:
                            self.stdout.write(self.style.ERROR('ERROR: End Office Trunkgroup {} was not found for {}'.format(end_office_trunk_number, destination)))
                        if long_distance_trunk_number not in trunks:
                            self.stdout.write(self.style.ERROR('ERROR: Long Distance Trunkgroup {} was not found for {}'.format(long_distance_trunk_number, destination)))
        self.stdout.write(self.style.SUCCESS('Successfully imported Outbound Route file >> Created: {} Updated: {} Error: {}'.format(create_count, update_count, error_count)))
