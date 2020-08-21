# django
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.postgres.fields import ArrayField, HStoreField, JSONField
from django.db import models
# local
from platforms.models import BroadworksPlatform
from steward.storage import ProtectedFileStorage


class Process(models.Model):
    STATUS_SCHEDULED = 0
    STATUS_COMPLETED = 1
    STATUS_CANCELED = 2
    STATUS_ERROR = 3
    STATUS_RUNNING = 4
    CHOICES_STATUS = (
        (STATUS_SCHEDULED, 'Scheduled'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_CANCELED, 'Cancled'),
        (STATUS_ERROR, 'Error'),
        (STATUS_RUNNING, 'Running'),
    )
    PLATFORM_BROADWORKS = 0
    user = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE, related_name='processes', verbose_name=('user'), null=False)
    method = models.CharField(max_length=256, null=False)
    platform_type = models.SmallIntegerField(null=False)
    platform_id = models.IntegerField(null=False)
    parameters = JSONField()
    start_timestamp = models.DateTimeField(null=False)
    end_timestamp = models.DateTimeField(null=True)
    status = models.PositiveSmallIntegerField(null=False, default=STATUS_SCHEDULED, choices=CHOICES_STATUS)
    exception = models.TextField()
    view_permission = models.CharField(max_length=64, db_index=True)

    @property
    def platform(self):
        if self.platform_type == Process.PLATFORM_BROADWORKS:
            return BroadworksPlatform.objects.get(pk=self.platform_id)
        return None

    def get_platform_type_display(self):
        if self.platform_type == Process.PLATFORM_BROADWORKS:
            return "Broadworks"
        return "Unknown"

    class Meta:
        ordering = ['-start_timestamp', '-end_timestamp']
        permissions = (
            ("process_busy_lamp_field_fixup_exec", "Busy Lamp Field Fixup Execute"),
            ("process_busy_lamp_field_fixup_view", "Busy Lamp Field Fixup View Results"),
            ("process_call_park_pickup_configurator_exec", "Call Park/Pickup Configurator Execute"),
            ("process_call_park_pickup_configurator_view", "Call Park/Pickup Configurator View Results"),
            ("process_dect_configurator_exec", "DECT Configurator Execute"),
            ("process_dect_configurator_view", "DECT Configurator View Results"),
            ("process_device_specific_migration_exec", "Device Specific Migration Execute"),
            ("process_device_specific_migration_view", "Device Specific Migration View Results"),
            ("process_firmware_report_exec", "Firmware Report Execute"),
            ("process_firmware_report_view", "Firmware Report View Results"),
            ("process_fraud_compliance_reset_exec", "Fraud Compliance Reset Tool Execute"),
            ("process_fraud_compliance_reset_view", "Fraud Compliance Reset Tool View Results"),
            ("process_lab_rebuild_exec", "Lab Rebuild Execute"),
            ("process_lab_rebuild_view", "Lab Rebuild View Results"),
            ("process_ptt_configurator_exec", "Push To Talk Configurator Execute"),
            ("process_ptt_configurator_view", "Push To Talk Configurator View Results"),
            ("process_registration_by_type_exec", "Registration by Type Report Execute"),
            ("process_registration_by_type_view", "Registration by Type Report View Results"),
            ("process_registration_report_exec", "Registration Report Execute"),
            ("process_registration_report_view", "Registration Report View Results"),
            ("process_speed_dial_configurator_exec", "Speed Dial Configurator Execute"),
            ("process_speed_dial_configurator_view", "Speed Dial Configurator View Results"),
            ("process_tag_removal_exec", "Tag Removal Tool Execute"),
            ("process_tag_removal_view", "Tag Removal Tool View Results"),
            ("process_tag_report_exec", "Tag Report Execute"),
            ("process_tag_report_view", "Tag Report View Results"),
            ("process_trunk_user_audit_exec", "Trunk Audit Execute"),
            ("process_trunk_user_audit_view", "Trunk Audit View Results"),
        )


class ProcessContent(models.Model):
    process = models.ForeignKey('Process',null=True, on_delete=models.CASCADE, related_name='content')
    tab = models.CharField(max_length=32)
    priority = models.PositiveSmallIntegerField(default=32767)
    raw = models.FileField(upload_to='process', storage=ProtectedFileStorage())
    html = models.FileField(upload_to='process', storage=ProtectedFileStorage())

    class Meta:
        ordering = ['priority', 'tab']
