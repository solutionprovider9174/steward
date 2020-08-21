# Python
import io

# Django
from django.db import models
from django.urls import reverse
from django.contrib.postgres.fields import ArrayField

# Application

# Third Party
from lib.pyutil.django.models import NullCharField


class DeviceType(models.Model):
    CATEGORY_PHONE = 0
    CATEGORY_EQUIPMENT = 1
    CATEGORY_CHOICES = (
        (CATEGORY_PHONE, 'Phone'),
        (CATEGORY_EQUIPMENT, 'Equipment'),
    )
    category = models.PositiveSmallIntegerField(choices=CATEGORY_CHOICES)
    manufacturer = models.CharField(max_length=256)
    model = models.CharField(max_length=256)
    skus = ArrayField(models.CharField(max_length=32), default=[], blank=True)
    serial_format = models.CharField(max_length=256, blank=True)
    switch_type = models.CharField(max_length=256, unique=True)

    class Meta:
        ordering = ('manufacturer', 'model')


class Device(models.Model):
    STATE_PROVISIONED = -2
    STATE_ERROR = -1
    STATE_CLEAR = 0
    STATE_SCHEDULED = 1
    STATE_RUNNING = 2
    CHOICES_STATE_ALL = (
        (STATE_PROVISIONED, 'Provisioned'),
        (STATE_ERROR, 'Error'),
        (STATE_CLEAR, 'Clear'),
        (STATE_SCHEDULED, 'Scheduled'),
        (STATE_RUNNING, 'Running'),
    )
    CHOICES_STATE_PRIMARY = (STATE_CLEAR, STATE_SCHEDULED, STATE_RUNNING,)
    CHOICES_STATE_SUCCESS = (STATE_PROVISIONED,)
    CHOICES_STATE_ERROR = (STATE_ERROR,)
    site = models.ForeignKey('Site', on_delete=models.SET_NULL,null=True, related_name='devices')
    device_type = models.ForeignKey('DeviceType',on_delete=models.SET_NULL, null=True, related_name='devices')
    state = models.SmallIntegerField(null=False, default=STATE_CLEAR, choices=CHOICES_STATE_ALL)
    name = models.CharField(max_length=24, unique=True)
    serial = NullCharField(max_length=12, unique=True, null=True, blank=True, default=None)
    password = models.CharField(max_length=64)
    primary_user_id = models.CharField(max_length=256, default='', null=True)
    primary_user_name = models.CharField(max_length=256, default='', null=True)
    primary_user_dn = models.CharField(max_length=256, default='', null=True)
    line_port_count = models.PositiveSmallIntegerField(default=0)
    checkin_time = models.DateTimeField(null=True, default=None)

    def get_absolute_url(self):
        return reverse('deploy:device-detail', args=(str(self.id),))

    class Meta:
        unique_together = ('site', 'name')
        ordering = ('name',)


class Site(models.Model):
    STATUS_SCHEDULED = 0
    STATUS_COMPLETED = 1
    STATUS_CANCELED = 2
    STATUS_ERROR = 3
    STATUS_PROGRESS = 4
    CHOICES_STATUS = (
        (STATUS_SCHEDULED, 'Scheduled'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_CANCELED, 'Canceled'),
        (STATUS_ERROR, 'Error'),
        (STATUS_PROGRESS, 'In Progress'),
    )
    SYNC_STATE_ERROR = -1
    SYNC_STATE_CLEAR = 0
    SYNC_STATE_SCHEDULED = 1
    SYNC_STATE_RUNNING = 2
    CHOICES_SYNC_STATE = (
        (SYNC_STATE_ERROR, 'Error'),
        (SYNC_STATE_CLEAR, 'Clear'),
        (SYNC_STATE_SCHEDULED, 'Scheduled'),
        (SYNC_STATE_RUNNING, 'SYNC_STATE_RUNNING'),
    )
    status = models.PositiveSmallIntegerField(null=False, default=STATUS_SCHEDULED, choices=CHOICES_STATUS)
    sync_state = models.SmallIntegerField(null=False, default=SYNC_STATE_CLEAR, choices=CHOICES_SYNC_STATE)
    last_sync = models.DateTimeField(null=True, default=None)
    provider_id = models.CharField(max_length=128)
    group_id = models.CharField(max_length=128)
    completion_time = models.DateTimeField(null=True, default=None)

    name = models.CharField(max_length=256, blank=True)
    address_line1 = models.CharField(max_length=256, blank=True)
    address_line2 = models.CharField(max_length=256, blank=True)
    city = models.CharField(max_length=256, blank=True)
    state = models.CharField(max_length=64, blank=True)
    zip_code = models.CharField(max_length=10, blank=True)
    country = models.CharField(max_length=10, blank=True)

    def get_absolute_url(self):
        return reverse('deploy:site-detail', args=(str(self.id),))

    def get_full_address(self, new_line='\n'):
        address = io.StringIO()
        if self.address_line1:
            address.write(self.address_line1)
        if self.address_line2:
            if address.getvalue():
                address.write(new_line)
            address.write(self.address_line2)
        if self.city or self.state or self.zip_code:
            line = io.StringIO()
            if self.city:
                if line.getvalue():
                    line.write(' ')
                line.write(self.city)
            if self.state:
                if line.getvalue():
                    line.write(' ')
                line.write(self.state)
            if self.zip_code:
                if line.getvalue():
                    line.write(' ')
                line.write(self.zip_code)
            if line.getvalue():
                if address.getvalue():
                    address.write(new_line)
                address.write(line.getvalue())
                line.close()
        if address.getvalue():
            rval = address.getvalue()
            address.close()
        else:
            rval = None
        return rval

    def get_full_address_br(self):
        return self.get_full_address(new_line='<br/>')

    class Meta:
        unique_together = ("provider_id", "group_id")
        ordering = ('name',)
