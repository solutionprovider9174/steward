from django.urls import re_path
import deploy.views

app_name ='deploy'
urlpatterns = [
    re_path(r'^$', deploy.views.IndexRedirectView.as_view(), name='index'),
    re_path(r'^sites/$', deploy.views.SiteListView.as_view(), name='site-list'),
    re_path(r'^sites/import$', deploy.views.SiteCreateView.as_view(), name='site-create'),
    re_path(r'^site/(?P<pk>\d+)/$', deploy.views.SiteDetailView.as_view(), name='site-detail'),
    re_path(r'^device/(?P<pk>\d+)/$', deploy.views.DeviceDetailView.as_view(), name='device-detail'),
    re_path(r'^device/(?P<pk>\d+)/update$', deploy.views.DeviceUpdateView.as_view(), name='device-update'),
]
