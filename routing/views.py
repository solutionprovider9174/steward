# Django
from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.urls import reverse, reverse_lazy
from django.http import HttpResponseRedirect, HttpResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.generic import (
    CreateView, DeleteView, DetailView, ListView, UpdateView, TemplateView,
)

# Application
from routing.models import (
    FraudBypass, FraudBypassHistory, Number, NumberHistory, OutboundRoute, OutboundRouteHistory, Record,
    RemoteCallForward, RemoteCallForwardHistory, Route, Transmission,
)
from django.contrib.auth.decorators import permission_required


# @permission_required('steward.can_go_in_dashboard')

class TransmissionListView(LoginRequiredMixin, ListView):
    permission_required('steward.can_go_in_routing')
    model = Transmission
    paginate_by = 100


class TransmissionDetailView(LoginRequiredMixin, DetailView):
    permission_required('steward.can_go_in_routing')
    model = Transmission


class NumberSearchView(LoginRequiredMixin, TemplateView):
    permission_required('steward.can_go_in_routing')
    template_name = 'routing/number_search.html'
    # @permission_required('steward.can_go_in_routing')
    def get_context_data(self, **kwargs):
        context = super(NumberSearchView, self).get_context_data(**kwargs)
        context['number_count'] = Number.objects.filter(active=True).count()
        return context


class NumberHistoryView(LoginRequiredMixin, TemplateView):
    permission_required('steward.can_go_in_routing')
    template_name = 'routing/number_history.html'
    @permission_required('steward.can_go_in_routing')
    def get_object(self):
        try:
            return Number.objects.get(cc=self.kwargs.get('cc'), number=self.kwargs.get('number'))
        except Number.DoesNotExist:
            return None

    @permission_required('steward.can_go_in_routing')
    def get_context_data(self, **kwargs):
        context = super(NumberHistoryView, self).get_context_data(**kwargs)
        context['object'] = self.get_object()
        context['cc'] = self.kwargs.get('cc')
        context['number'] = self.kwargs.get('number')
        context['history_list'] = NumberHistory.objects.filter(cc=self.kwargs.get('cc'), number=self.kwargs.get('number'))
        return context


class NumberHistoryListView(LoginRequiredMixin, ListView):
    permission_required('steward.can_go_in_routing')
    model = NumberHistory
    paginate_by = 100


class RouteCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    permission_required('steward.can_go_in_routing')
    model = Route
    fields = ('name', 'trunkgroup', 'type')
    permission_required = 'routing.change_route'

    def get_success_url(self):
        return reverse('routing:route-detail', args=(self.object.id,))


class RouteDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    permission_required('steward.can_go_in_routing')
    model = Route
    success_url = reverse_lazy('routing:route-list')
    permission_required = 'routing.change_route'


class RouteDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    permission_required('steward.can_go_in_routing')
    model = Route
    permission_required = 'routing.change_route'


class RouteListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    permission_required('steward.can_go_in_routing')
    model = Route
    paginate_by = 100
    permission_required = 'routing.change_route'


class RouteUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    permission_required('steward.can_go_in_routing')
    model = Route
    fields = ('name',)
    permission_required = 'routing.change_route'

    def get_success_url(self):
        return reverse('routing:route-detail', args=(self.object.id,))


class FraudBypassCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    permission_required('steward.can_go_in_routing')

    model = FraudBypass
    fields = ('number',)
    success_url = reverse_lazy('routing:fraud-bypass-list')
    permission_required = 'routing.change_fraudbypass'

    def form_valid(self, form):
        rval = super(FraudBypassCreateView, self).form_valid(form)
        FraudBypassHistory.objects.create(cc=self.object.cc, number=self.object.number, user=self.request.user, action='Created')
        return rval


class FraudBypassDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    permission_required('steward.can_go_in_routing')
    model = FraudBypass
    success_url = reverse_lazy('routing:fraud-bypass-list')
    permission_required = 'routing.change_fraudbypass'

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        success_url = self.get_success_url()
        FraudBypassHistory.objects.create(cc=self.object.cc, number=self.object.number, user=request.user, action='Deleted')
        self.object.delete()
        return HttpResponseRedirect(success_url)


class FraudBypassListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    permission_required('steward.can_go_in_routing')
    model = FraudBypass
    paginate_by = 100
    permission_required = 'routing.change_fraudbypass'


class FraudBypassHistoryView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    permission_required('steward.can_go_in_routing')
    template_name = 'routing/fraudbypass_history.html'
    permission_required = 'routing.change_fraudbypass'

    def get_object(self):
        try:
            return FraudBypass.objects.get(cc=self.kwargs.get('cc'), number=self.kwargs.get('number'))
        except FraudBypass.DoesNotExist:
            return None

    def get_context_data(self, **kwargs):
        context = super(FraudBypassHistoryView, self).get_context_data(**kwargs)
        context['object'] = self.get_object()
        context['cc'] = self.kwargs.get('cc')
        context['number'] = self.kwargs.get('number')
        context['history_list'] = FraudBypassHistory.objects.filter(cc=self.kwargs.get('cc'), number=self.kwargs.get('number'))
        return context


class FraudBypassHistoryListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    permission_required('steward.can_go_in_routing')
    model = FraudBypassHistory
    paginate_by = 100
    permission_required = 'routing.change_fraudbypass'


class OutboundRouteCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    permission_required('steward.can_go_in_routing')
    model = OutboundRoute
    fields = ('number', 'end_office_route', 'long_distance_route', 'comment',)
    success_url = reverse_lazy('routing:outbound-route-list')
    permission_required = 'routing.change_outboundroute'

    def form_valid(self, form):
        rval = super(OutboundRouteCreateView, self).form_valid(form)
        OutboundRouteHistory.objects.create(number=self.object.number, user=self.request.user, action='Created, End Office: {}, Long Distance: {}'.format(self.object.end_office_route.name, self.object.long_distance_route.name))
        return rval


class OutboundRouteDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    permission_required('steward.can_go_in_routing')
    model = OutboundRoute
    success_url = reverse_lazy('routing:outbound-route-list')
    permission_required = 'routing.change_outboundroute'

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        success_url = self.get_success_url()
        OutboundRouteHistory.objects.create(number=self.object.number, user=request.user, action='Deleted')
        self.object.delete()
        return HttpResponseRedirect(success_url)


class OutboundRouteListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    permission_required('steward.can_go_in_routing')
    model = OutboundRoute
    paginate_by = 100
    permission_required = 'routing.change_outboundroute'


class OutboundRouteUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    permission_required('steward.can_go_in_routing')
    model = OutboundRoute
    fields = ('end_office_route', 'long_distance_route', 'comment',)
    success_url = reverse_lazy('routing:outbound-route-list')
    permission_required = 'routing.change_outboundroute'

    def form_valid(self, form):
        rval = super(OutboundRouteUpdateView, self).form_valid(form)
        OutboundRouteHistory.objects.create(number=self.object.number, user=self.request.user, action='Updated, End Office: {}, Long Distance: {}'.format(self.object.end_office_route.name, self.object.long_distance_route.name))
        return rval

class OutboundRouteHistoryListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    permission_required('steward.can_go_in_routing')
    model = OutboundRouteHistory
    paginate_by = 100
    permission_required = 'routing.change_outboundroute'


class RemoteCallForwardSearchView(LoginRequiredMixin, TemplateView):
    permission_required('steward.can_go_in_routing')
    template_name = 'routing/remotecallforward_search.html'

    def get_context_data(self, **kwargs):
        context = super(RemoteCallForwardSearchView, self).get_context_data(**kwargs)
        context['number_count'] = RemoteCallForward.objects.count()
        return context


class RemoteCallForwardHistoryListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    permission_required('steward.can_go_in_routing')
    model = RemoteCallForwardHistory
    paginate_by = 100
    permission_required = 'routing.change_remotecallforward'


class RemoteCallForwardHistoryDetailView(LoginRequiredMixin, TemplateView):
    permission_required('steward.can_go_in_routing')
    template_name = 'routing/remotecallforwardhistory_detail.html'

    def get_context_data(self, **kwargs):
        context = super(RemoteCallForwardHistoryDetailView, self).get_context_data(**kwargs)
        context['called_number'] = self.kwargs.get('called_number')
        context['history_list'] = RemoteCallForwardHistory.objects.filter(called_number=self.kwargs.get('called_number'))
        return context
