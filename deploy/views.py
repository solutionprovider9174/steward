# Python
import csv
import importlib

# Django
from django.utils import timezone
from django.shortcuts import render
from django.urls import reverse
from django.views.generic.list import ListView
from django.core.exceptions import PermissionDenied
from django.views.generic.detail import (
    DetailView, BaseDetailView, SingleObjectTemplateResponseMixin)
from django.http import HttpResponseRedirect, HttpResponse
from django.views.generic import (
    TemplateView, CreateView, UpdateView, RedirectView)
from django.contrib.auth.mixins import (
    LoginRequiredMixin, PermissionRequiredMixin)

# Application
from deploy.models import Site, DeviceType, Device
from deploy.forms import SiteCreateForm, SiteActionForm, DeviceUpdateForm
import deploy.jobs.site

# Third Party
import rq
import django_rq
from redis import Redis
from lib.pyutil.django.mixins import (
    JSONResponseMixin, JSONModelMixin, ProcessFormMixin)

from django.contrib.auth.decorators import permission_required
class IndexRedirectView(RedirectView):
    permission_required('steward.can_go_in_deploy')
    permanent = False
    pattern_name = 'deploy:site-list'


class SiteListView(LoginRequiredMixin, ListView):
    permission_required('steward.can_go_in_deploy')
    model = Site


class SiteCreateView(LoginRequiredMixin, CreateView):

    model = Site
    form_class = SiteCreateForm
    @permission_required('steward.can_go_in_deploy')
    def form_valid(self, form):
        rval = super(SiteCreateView, self).form_valid(form)
        self.object.sync_state = Site.SYNC_STATE_SCHEDULED
        self.object.save(update_fields=['sync_state'])
        q = rq.Queue('deploy', connection=Redis(), default_timeout=10800)
        q.enqueue_call(deploy.jobs.site.sync_site, args=(self.object.pk,))
        return rval


class SiteDetailView(LoginRequiredMixin, ProcessFormMixin, JSONModelMixin, JSONResponseMixin, SingleObjectTemplateResponseMixin, BaseDetailView):
    model = Site
    form_class = SiteActionForm
    initial = { 'action': SiteActionForm.ACTION_SYNC }

    @permission_required('steward.can_go_in_deploy')
    def get_context_data(self, **kwargs):
        context = super(SiteDetailView, self).get_context_data(**kwargs)
        context['phone_device_types'] = DeviceType.objects.filter(category=DeviceType.CATEGORY_PHONE)
        return context

    @permission_required('steward.can_go_in_deploy')
    def form_valid(self, form):
        self.object = self.get_object()
        action = form.cleaned_data.get('action')
        if action == SiteActionForm.ACTION_SYNC:
            if self.object.sync_state > Site.SYNC_STATE_CLEAR:
                raise Exception('Sync state is not clear')
            self.object.sync_state = Site.SYNC_STATE_SCHEDULED
            self.object.save(update_fields=['sync_state'])
            q = rq.Queue('deploy', connection=Redis(), default_timeout=10800)
            q.enqueue_call(deploy.jobs.site.sync_site, args=(self.object.pk,))
        else:
            pass
        return HttpResponseRedirect(self.get_success_url())

    @permission_required('steward.can_go_in_deploy')
    def get_success_url(self):
        return self.object.get_absolute_url()


class DeviceDetailView(LoginRequiredMixin, JSONModelMixin, JSONResponseMixin, SingleObjectTemplateResponseMixin, BaseDetailView):
    model = Device


class DeviceUpdateView(LoginRequiredMixin, UpdateView):
    model = Device
    form_class = DeviceUpdateForm

    @permission_required('steward.can_go_in_deploy')
    def form_valid(self, form):
        rval = super(DeviceUpdateView, self).form_valid(form)
        if self.object.state > Device.STATE_CLEAR:
            raise Exception('State is not clear')
        if self.object.serial:
            self.object.state = Device.STATE_SCHEDULED
            self.object.save(update_fields=['state'])
            q = rq.Queue('deploy', connection=Redis(), default_timeout=10800)
            q.enqueue_call(deploy.jobs.site.sync_device, args=(self.object.pk,))
        else:
            self.object.state = Device.STATE_CLEAR
            self.object.save(update_fields=['state'])
        return rval

    @permission_required('steward.can_go_in_deploy')
    def form_invalid(self, form):
        print(form.errors)
        return super(DeviceUpdateView, self).form_invalid(form)
