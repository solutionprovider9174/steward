# Django
from django.urls import re_path, include

# Third Party
from rest_framework import routers

# Application
from routing.api import views


# Router
router = routers.DefaultRouter()
router.register(r'records', views.RecordViewSet, basename='routing-record')
router.register(r'routes', views.RouteViewSet, basename='routing-route')

urlpatterns = [
    re_path(r'^$', views.RouteRootView.as_view(), name='routing-root'),
    re_path(r'^numbers/$', views.NumberListView.as_view(), name='routing-number-list'),
    re_path(r'^numbers/(?P<cc>\d+)/(?P<number>\d+)/$', views.NumberDetailView.as_view(), name='routing-number-detail'),
    re_path(r'^fraud-bypass/$', views.FraudBypassListView.as_view(), name='routing-fraud-bypass-list'),
    re_path(r'^fraud-bypass/(?P<cc>\d+)/(?P<number>\d+)/$', views.FraudBypassDetailView.as_view(), name='routing-fraud-bypass-detail'),
    re_path(r'^remote-call-forward/$', views.RemoteCallForwardListView.as_view(), name='routing-remote-call-forward-list'),
    re_path(r'^remote-call-forward/(?P<called_number>\d+)/$', views.RemoteCallForwardDetailView.as_view(), name='routing-remote-call-forward-detail'),
    re_path(r'^outbound-route/$', views.OutboundRouteListView.as_view(), name='routing-outbound-route-list'),
    re_path(r'^outbound-route/(?P<number>\d+)/$', views.OutboundRouteDetailView.as_view(), name='routing-outbound-route-detail'),
    re_path(r'^', include(router.urls)),
]
