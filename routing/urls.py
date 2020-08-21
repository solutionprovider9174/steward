from django.urls import re_path

# Application
import routing.views

app_name ='routing'
urlpatterns = [
   re_path(r'^fraud-bypass$', routing.views.FraudBypassListView.as_view(), name='fraud-bypass-list'),
   re_path(r'^fraud-bypass-history$', routing.views.FraudBypassHistoryListView.as_view(), name='fraud-bypass-history'),
   re_path(r'^fraud-bypass/create$', routing.views.FraudBypassCreateView.as_view(), name='fraud-bypass-create'),
   re_path(r'^fraud-bypass/(?P<pk>\d+)/delete$', routing.views.FraudBypassDeleteView.as_view(), name='fraud-bypass-delete'),
   re_path(r'^fraud-bypass/(?P<cc>\d+)/(?P<number>\d+)/$', routing.views.FraudBypassHistoryView.as_view(), name='fraud-bypass-history'),

   re_path(r'^numbers/search$', routing.views.NumberSearchView.as_view(), name='number-search'),
   re_path(r'^numbers/(?P<cc>\d+)/(?P<number>\d+)/$', routing.views.NumberHistoryView.as_view(), name='number-detail'),
   re_path(r'^number-history/$', routing.views.NumberHistoryListView.as_view(), name='number-history'),

   re_path(r'^outbound-routes$', routing.views.OutboundRouteListView.as_view(), name='outbound-route-list'),
   re_path(r'^outbound-routes-history$', routing.views.OutboundRouteHistoryListView.as_view(), name='outbound-route-history'),
   re_path(r'^outbound-routes/create$', routing.views.OutboundRouteCreateView.as_view(), name='outbound-route-create'),
   re_path(r'^outbound-route/(?P<pk>\d+)/edit$', routing.views.OutboundRouteUpdateView.as_view(), name='outbound-route-update'),
   re_path(r'^outbound-route/(?P<pk>\d+)/delete$', routing.views.OutboundRouteDeleteView.as_view(), name='outbound-route-delete'),

   re_path(r'^remote-call-forward$', routing.views.RemoteCallForwardSearchView.as_view(), name='remote-call-forward-search'),
   re_path(r'^remote-call-forward/history$', routing.views.RemoteCallForwardHistoryListView.as_view(), name='remote-call-forward-history'),
   re_path(r'^remote-call-forward/(?P<called_number>\d+)/$', routing.views.RemoteCallForwardHistoryDetailView.as_view(), name='remote-call-forward-history-detail'),

   re_path(r'^routes$', routing.views.RouteListView.as_view(), name='route-list'),
   re_path(r'^routes/add$', routing.views.RouteCreateView.as_view(), name='route-create'),
   re_path(r'^routes/(?P<pk>\d+)/$', routing.views.RouteDetailView.as_view(), name='route-detail'),
   re_path(r'^routes/(?P<pk>\d+)/edit$', routing.views.RouteUpdateView.as_view(), name='route-update'),
   re_path(r'^routes/(?P<pk>\d+)/delete$', routing.views.RouteDeleteView.as_view(), name='route-delete'),

   re_path(r'^transmissions$', routing.views.TransmissionListView.as_view(), name='transmission-list'),
   re_path(r'^transmissions/(?P<pk>\d+)/$', routing.views.TransmissionDetailView.as_view(), name='transmission-detail'),
]
