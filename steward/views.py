from django.conf import settings
from django.http import Http404
from django.urls import reverse
from django.views.generic import View
from django.views.generic.base import RedirectView
from django.core.exceptions import ObjectDoesNotExist
from django.views.static import serve
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin

from steward.models import GroupDefaultView


class IndexRedirectView(RedirectView):
    permanent = False

    def get_redirect_url(self, *args, **kwargs):
        user = self.request.user
        view_name = 'dashboard:empty'
        view_priority = 0
        for group in user.groups.all():
            try:
                group_view = GroupDefaultView.objects.get(group=group)
                if group_view.priority > view_priority:
                    view_name = group_view.view_name
                    view_priority = group_view.priority
            except ObjectDoesNotExist:
                pass
        return reverse(view_name)


class ProtectedFileView(View):
    def get(self, request, *args, **kwargs):
        if request.user.is_anonymous():
            raise Http404("File not found")
        return serve(request, path=kwargs['path'], document_root=settings.PROTECTED_ROOT, show_indexes=False)
