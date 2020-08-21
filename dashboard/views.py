from django.shortcuts import render
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin

from django.contrib.auth.decorators import permission_required


# @permission_required('steward.can_go_in_dashboard')
class EmptyDashboardView(LoginRequiredMixin, TemplateView):
    permission_required('steward.can_go_in_dashboard')
    template_name = "dashboard/empty.html"

# @permission_required('steward.can_go_in_dashboard')
class VoipDashboardView(LoginRequiredMixin, TemplateView):
    permission_required('steward.can_go_in_dashboard')
    template_name = "dashboard/voip.html"
