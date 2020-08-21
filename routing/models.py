from django.conf import settings
from django.urls import reverse
from django.db import models
from django.template import engines
from django.core.validators import RegexValidator

NANPA_VALIDATOR = RegexValidator(regex='^\d{10}$', message='Must be 10 digits', code='nomatch')


class Route(models.Model):
    TYPE_CHOICE_INTERNAL = 0
    TYPE_CHOICE_OUTBOUND = 1
    TYPE_CHOICES = (
        (TYPE_CHOICE_INTERNAL, 'Internal'),
        (TYPE_CHOICE_OUTBOUND, 'Outbound'),
    )
    type = models.SmallIntegerField(choices=TYPE_CHOICES)
    name = models.CharField(max_length=32, unique=True)
    trunkgroup = models.PositiveIntegerField(null=True, default=None)

    class Meta:
        ordering = ('name',)

    def __str__(self):
        return self.name


class Record(models.Model):
    route = models.ForeignKey('Route',on_delete=models.SET_NULL, null =True, related_name='records')
    order = models.IntegerField(default=100)
    preference = models.IntegerField(default=10)
    flags = models.CharField(max_length=16, default='U')
    service = models.CharField(max_length=65, default='E2U+sip')
    regex = models.CharField(max_length=128, default='!^([^@]+)@([^@]+)$!^\1@HOST$!')
    replacement = models.CharField(max_length=128, default='.')

    def __str__(self):
        return '{} {} "{}" "{}" "{}" "{}"'.format(self.order, self.preference,
                                                  self.flags, self.service,
                                                  self.regex, self.replacement)


class Transmission(models.Model):
    TYPE_CHOICE_ROUTE = 0
    TYPE_CHOICE_FRAUD_BYPASS = 1
    TYPE_CHOICE_OUTBOUND_ROUTE = 2
    TYPE_CHOICE_REMOTE_CALL_FORWARD = 3
    TYPE_CHOICES = (
        (TYPE_CHOICE_ROUTE, 'Route'),
        (TYPE_CHOICE_FRAUD_BYPASS, 'Fraud Bypass'),
        (TYPE_CHOICE_OUTBOUND_ROUTE, 'Outbound Route'),
        (TYPE_CHOICE_REMOTE_CALL_FORWARD, 'Remote Call Forward'),
    )
    RESULT_CHOICE_PENDING = 0
    RESULT_CHOICE_TRANSFERING = 1
    RESULT_CHOICE_SUCCESS = 2
    RESULT_CHOICE_FAILURE = 3
    RESULT_CHOICES = (
        (RESULT_CHOICE_PENDING, 'Pending'),
        (RESULT_CHOICE_TRANSFERING, 'Transfering'),
        (RESULT_CHOICE_SUCCESS, 'Success'),
        (RESULT_CHOICE_FAILURE, 'Failure'),
    )
    type = models.SmallIntegerField(choices=TYPE_CHOICES)
    checksum = models.CharField(max_length=32, blank=True)
    last_modified = models.DateTimeField(null=True, default=None)
    result_state = models.SmallIntegerField(choices=RESULT_CHOICES)
    result_data = models.TextField()
    result_timestamp = models.DateTimeField(null=True, default=None)

    class Meta:
        ordering = ('-id',)

    def __str__(self):
        return "{} for last modified number at {}".format(self.get_result_state_display(), self.last_modified)


class Number(models.Model):
    route = models.ForeignKey('Route',on_delete=models.SET_NULL, null=True, related_name='numbers')
    cc = models.SmallIntegerField(default=1)
    number = models.CharField(max_length=64)
    modified = models.DateTimeField(auto_now=True)
    active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('cc', 'number')
        ordering = ('modified',)

    def get_absolute_api_url(self):
        return reverse('api:routing-number-detail', args=(self.cc, self.number))

    def get_desination(self):
        if self.destination:
            return self.destination
        else:
            return self.number

    @property
    def e164(self):
        return "+{}-{}".format(self.cc, self.number)

    @property
    def name(self):
        return '.'.join((str(self.cc) + str(self.number))[::-1]) + '.e164.arpa.'

    @property
    def records(self):
        django_engine = engines['django']
        context = {
            'cc': self.cc,
            'number': self.number,
            'destination': self.get_desination(),
        }
        rval = list()
        for record in self.route.records.all():
            rval.append(django_engine.from_string(record).render(context))
        return rval


class NumberHistory(models.Model):
    cc = models.SmallIntegerField(default=1)
    number = models.CharField(max_length=64)
    user = models.ForeignKey(settings.AUTH_USER_MODEL,null=True, on_delete=models.SET_NULL, related_name='+')
    modified = models.DateTimeField(auto_now=True)
    action = models.CharField(max_length=256)

    class Meta:
        ordering = ('-modified',)


class FraudBypass(models.Model):
    cc = models.SmallIntegerField(default=1)
    number = models.CharField(max_length=64, validators=[NANPA_VALIDATOR])
    modified = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('cc', 'number')
        ordering = ('number',)


class FraudBypassHistory(models.Model):
    cc = models.SmallIntegerField(default=1)
    number = models.CharField(max_length=64)
    user = models.ForeignKey(settings.AUTH_USER_MODEL,null=True, on_delete=models.SET_NULL, related_name='+')
    modified = models.DateTimeField(auto_now=True)
    action = models.CharField(max_length=256)

    class Meta:
        ordering = ('-modified',)


class OutboundRoute(models.Model):
    number = models.CharField(max_length=128, unique=True)
    end_office_route = models.ForeignKey('Route',null=True,on_delete=models.SET_NULL, related_name='+',  limit_choices_to={'type': Route.TYPE_CHOICE_OUTBOUND})
    long_distance_route = models.ForeignKey('Route',null =True, on_delete=models.SET_NULL, related_name='+', limit_choices_to={'type': Route.TYPE_CHOICE_OUTBOUND})
    comment = models.CharField(max_length=128, blank=True)
    modified = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('number',)


class OutboundRouteHistory(models.Model):
    number = models.CharField(max_length=128)
    user = models.ForeignKey(settings.AUTH_USER_MODEL,null=True, on_delete=models.SET_NULL, related_name='+')
    modified = models.DateTimeField(auto_now=True)
    action = models.CharField(max_length=256)

    class Meta:
        ordering = ('-modified',)


class RemoteCallForward(models.Model):
    called_number = models.CharField(max_length=128, unique=True, validators=[NANPA_VALIDATOR])
    forward_number = models.CharField(max_length=128, validators=[NANPA_VALIDATOR])
    modified = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('called_number',)


class RemoteCallForwardHistory(models.Model):
    called_number = models.CharField(max_length=128)
    user = models.ForeignKey(settings.AUTH_USER_MODEL,null=True,on_delete=models.SET_NULL, related_name='+')
    modified = models.DateTimeField(auto_now=True)
    action = models.CharField(max_length=256)

    class Meta:
        ordering = ('-modified',)
