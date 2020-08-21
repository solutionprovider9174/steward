# Django
from django.shortcuts import render
from django.views.generic import TemplateView
from django.views.generic.detail import DetailView

# Application
from deploy.models import Device

from django.contrib.auth.decorators import permission_required


# @permission_required('steward.can_go_in_dashboard')
class PolycomDefaultView(TemplateView):
    permission_required('steward.can_go_in_dms')
    content_type = 'application/xml'
    template_name = 'dms/polycom/000000000000.cfg'


class PolycomResyncView(TemplateView):
    permission_required('steward.can_go_in_dms')
    content_type = 'application/xml'
    template_name = 'dms/polycom/resync.cfg'


class PolycomView(DetailView):
    permission_required('steward.can_go_in_dms')
    content_type = 'application/xml'
    template_name = 'dms/polycom/%mac%-phone.cfg'
    model = Device
    slug_field = 'serial__iexact'
