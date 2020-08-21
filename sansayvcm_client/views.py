#django
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.views.generic import TemplateView
from django.views.generic import ListView
from django.views.generic.edit import FormView

#Automate
import sansayvcm_client.forms
from sansayvcm_client.vcmclient import VcmClient
from sansayvcm_client.models import RouteTableLog
from django.contrib.auth.decorators import permission_required


# @permission_required('steward.can_go_in_sansayvcm')
class IndexView(TemplateView):
    permission_required('steward.can_go_in_sansayvcm')
    template_name = 'sansayvcm_client/index.html'

class SansayVcmRequestView(FormView):
    permission_required('steward.can_go_in_sansayvcm')
    template_name = 'sansayvcm_client/modify_route_table.html'
    form_class = sansayvcm_client.forms.ModifyRouteTableForm 
    success_url = '/sansay-vcm-request'

    def post(self, request, *args, **kwargs):
        form = self.form_class(request.POST)
        if form.is_valid():
            post = request.POST

            cluster = post.get('cluster')
            did = post.get('did')
            desc = 'Test 301Dev Number'

            client = VcmClient('update', 'route')
            result = client.send(cluster, desc, did)
            print(result)

            return HttpResponseRedirect('/sansay/sansay-vcm-request')

class VcmLogView(ListView):
    permission_required('steward.can_go_in_sansayvcm')
    model = RouteTableLog
    paginate_by = 100

