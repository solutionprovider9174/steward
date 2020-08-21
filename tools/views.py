# Python
from collections import OrderedDict
import csv
import json
import requests
import importlib

# Django
from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.core.exceptions import PermissionDenied
from django.urls import reverse
from django.http import HttpResponseRedirect, HttpResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.generic import TemplateView
from django.views.generic.list import ListView
from django.views.generic.detail import DetailView

# Application
import tools.forms
from tools.models import Process

# Third Party
import django_rq
from lib.pybw.broadworks import BroadWorks, Nil
from lib.pypalladion.palladion import Palladion
from lib.pyutil.django.mixins import ProcessFormMixin
from redis import Redis
import rq

from django.contrib.auth.decorators import permission_required


# @permission_required('steward.can_go_in_tool')
class IndexView(LoginRequiredMixin, TemplateView):
    permission_required('steward.can_go_in_tool')
    template_name = 'tools/index.html'


class ProcessListView(LoginRequiredMixin, ListView):
    permission_required('steward.can_go_in_tool')
    model = Process
    paginate_by = 100

    def get_queryset(self):
        queryset = super(ProcessListView, self).get_queryset()
        # filter based upon permissions
        permissions = []
        for permission in ['tools.{}'.format(x) for x,y in Process._meta.permissions]:
            if self.request.user.has_perm(permission):
                permissions.append(permission)
        queryset = queryset.filter(view_permission__in=permissions)
        # defer content
        queryset = queryset.defer("content")
        return queryset


class ProcessDetailView(LoginRequiredMixin, DetailView):
    permission_required('steward.can_go_in_tool')
    model = Process

    def get_context_data(self, **kwargs):
        context = super(ProcessDetailView, self).get_context_data(**kwargs)
        context['parameters'] = json.dumps(context['object'].parameters)
        if not self.request.user.has_perm(context['object'].view_permission):
            raise PermissionDenied
        return context


class ToolView(ProcessFormMixin, TemplateView):
    permission_required('steward.can_go_in_tool')
    def form_valid(self, form, formset):
        """
        If the form is valid, redirect to the supplied URL.
        """
        parameters = form.cleaned_data
        platform = parameters.pop('platform')
        if formset:
            # Handle all our formset
            parameters['data'] = [ f.cleaned_data for f in formset if f.cleaned_data != {}]
        self.object = Process.objects.create(user=self.request.user,
                                             method=self.process_name,
                                             platform_type=Process.PLATFORM_BROADWORKS,
                                             platform_id=platform.id,
                                             parameters=parameters,
                                             start_timestamp=timezone.now(),
                                             end_timestamp=None,
                                             view_permission=self.permission_view)
        module = '.'.join(self.process_function.split('.')[:-1])
        method = self.process_function.split('.')[-1]
        importlib.import_module(module)
        process_function = eval(self.process_function)
        q = rq.Queue('tool', connection=Redis(host=settings.RQ_QUEUES['tool']['HOST'],
                                              port=settings.RQ_QUEUES['tool']['PORT'],
                                              db=settings.RQ_QUEUES['tool']['DB']), default_timeout=10800)
        q.enqueue_call(process_function, args=(self.object.pk,))
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        """
        Returns the supplied success URL.
        """
        if self.success_url:
            # Forcing possible reverse_lazy evaluation
            url = force_text(self.success_url)
        else:
            url = reverse('tools:process-detail', args=(self.object.pk,))
        return url


class CallParkPickupConfiguratorToolView(PermissionRequiredMixin, LoginRequiredMixin, ToolView):
    permission_required('steward.can_go_in_tool')
    permission_required = 'tools.process_call_park_pickup_configurator_exec'
    permission_view = 'tools.process_call_park_pickup_configurator_view'
    process_name = 'Call Park/Pickup Configurator'
    process_function = 'tools.jobs.call_park_pickup_configurator.call_park_pickup_configurator'
    template_name = 'tools/call_park_pickup_configurator.html'
    form_class = tools.forms.CallParkPickupForm


class DectConfiguratorToolView(PermissionRequiredMixin, LoginRequiredMixin, ToolView):
    permission_required('steward.can_go_in_tool')
    permission_required = 'tools.process_dect_configurator_exec'
    permission_view = 'tools.process_dect_configurator_view'
    process_name = 'DECT Configurator'
    process_function = 'tools.jobs.dect_configurator.dect_configurator'
    template_name = 'tools/dect_configurator.html'
    form_class = tools.forms.DeviceForm
    formset_class = tools.forms.DectLineForm
    formset_extra = 2


class DeviceSpecificMigrationToolView(PermissionRequiredMixin, LoginRequiredMixin, ToolView):
    permission_required('steward.can_go_in_tool')
    permission_required = 'tools.process_device_specific_migration_exec'
    permission_view = 'tools.process_device_specific_migration_view'
    process_name = 'Device Specific Migration'
    process_function = 'tools.jobs.device_specific_migration.device_specific_migration'
    template_name = 'tools/device_specific_migration_tool.html'
    form_class = tools.forms.TypedProviderGroupForm


class FirmwareReportView(PermissionRequiredMixin, LoginRequiredMixin, ToolView):
    permission_required('steward.can_go_in_tool')
    permission_required = 'tools.process_firmware_report_exec'
    permission_view = 'tools.process_firmware_report_view'
    process_name = 'Firmware Report'
    process_function = 'tools.jobs.firmware_report.firmware_report'
    template_name = 'tools/firmware_report.html'
    form_class = tools.forms.ProviderGroupForm


class FraudComplianceResetToolView(PermissionRequiredMixin, LoginRequiredMixin, ToolView):
    permission_required('steward.can_go_in_tool')
    permission_required = 'tools.process_fraud_compliance_reset_exec'
    permission_view = 'tools.process_fraud_compliance_reset_view'
    process_name = 'Fraud Compliance Reset'
    process_function = 'tools.jobs.fraud_compliance_reset.fraud_compliance_reset'
    template_name = 'tools/fraud_compliance_reset_tool.html'
    form_class = tools.forms.TypedProviderGroupForm


class LabResetToolView(PermissionRequiredMixin, LoginRequiredMixin, ToolView):
    permission_required('steward.can_go_in_tool')
    permission_required = 'tools.process_lab_rebuild_exec'
    permission_view = 'tools.process_lab_rebuild_view'
    process_name = 'Lab Rebuild'
    process_function = 'tools.jobs.lab_rebuild.lab_rebuild'
    template_name = 'tools/lab_rebuild.html'
    form_class = tools.forms.EmptyForm


class PushToTalkConfiguratorToolView(PermissionRequiredMixin, LoginRequiredMixin, ToolView):
    permission_required('steward.can_go_in_tool')
    permission_required = 'tools.process_ptt_configurator_exec'
    permission_view = 'tools.process_ptt_configurator_view'
    process_name = 'Push To Talk Configurator'
    process_function = 'tools.jobs.ptt_configurator.ptt_configurator'
    template_name = 'tools/ptt_configurator.html'
    form_class = tools.forms.TypedProviderGroupForm


class RegistrationByTypeReportView(PermissionRequiredMixin, LoginRequiredMixin, ToolView):
    permission_required('steward.can_go_in_tool')
    permission_required = 'tools.process_registration_by_type_exec'
    permission_view = 'tools.process_registration_by_type_view'
    process_name = 'Registration By Type Report'
    process_function = 'tools.jobs.registration_by_type.registration_by_type'
    template_name = 'tools/registration_by_type.html'
    form_class = tools.forms.EmptyForm


class RegistrationReportView(PermissionRequiredMixin, LoginRequiredMixin, ToolView):
    permission_required('steward.can_go_in_tool')
    permission_required = 'tools.process_registration_report_exec'
    permission_view = 'tools.process_registration_report_view'
    process_name = 'Registration Report'
    process_function = 'tools.jobs.registration_report.registration_report'
    template_name = 'tools/registration_report.html'
    form_class = tools.forms.ProviderGroupForm


class SpeedDialConfiguratorToolView(PermissionRequiredMixin, LoginRequiredMixin, ToolView):
    permission_required('steward.can_go_in_tool')
    permission_required = 'tools.process_speed_dial_configurator_exec'
    permission_view = 'tools.process_speed_dial_configurator_view'
    process_name = 'Speed Dial Configurator'
    process_function = 'tools.jobs.speed_dial_configurator.speed_dial_configurator'
    template_name = 'tools/speed_dial_configurator.html'
    form_class = tools.forms.TypedProviderGroupForm
    formset_class = tools.forms.SpeedDialLineForm
    formset_extra = 5


class TagReportView(PermissionRequiredMixin, LoginRequiredMixin, ToolView):
    permission_required('steward.can_go_in_tool')
    permission_required = 'tools.process_tag_report_exec'
    permission_view = 'tools.process_tag_report_view'
    process_name = 'Tag Report'
    process_function = 'tools.jobs.tag_report.tag_report'
    template_name = 'tools/tag_report.html'
    form_class = tools.forms.TagReportForm


class TagRemovalToolView(PermissionRequiredMixin, LoginRequiredMixin, ToolView):
    permission_required('steward.can_go_in_tool')
    permission_required = 'tools.process_tag_removal_exec'
    permission_view = 'tools.process_tag_removal_view'
    process_name = 'Tag Removal'
    process_function = 'tools.jobs.tag_removal.tag_removal'
    template_name = 'tools/tag_removal_tool.html'
    form_class = tools.forms.TagRemovalForm


class TrunkAuditToolView(PermissionRequiredMixin, LoginRequiredMixin, ToolView):
    permission_required('steward.can_go_in_tool')
    permission_required = 'tools.process_trunk_user_audit_exec'
    permission_view = 'tools.process_trunk_user_audit_view'
    process_name = 'Trunk User Audit'
    process_function = 'tools.jobs.trunk_user_audit.trunk_user_audit'
    template_name = 'tools/trunk_user_audit.html'
    form_class = tools.forms.TrunkUserAuditForm


class BusyLampFieldFixupToolView(PermissionRequiredMixin, LoginRequiredMixin, ToolView):
    permission_required('steward.can_go_in_tool')
    permission_required = 'tools.process_busy_lamp_field_fixup_exec'
    permission_view = 'tools.process_busy_lamp_field_fixup_view'
    process_name = 'Busy Lamp Field (BLF) Fixup'
    process_function = 'tools.jobs.busy_lamp_field_fixup.blf_fixup'
    template_name = 'tools/busy_lamp_field_fixup.html'
    form_class = tools.forms.BusyLampFieldFixupForm
