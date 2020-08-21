from django.conf import settings
from django.conf.urls import include, url
from django.contrib import admin
import django.views.static

import api.urls
import toolbox.views


urlpatterns = [
    url(r'^$', toolbox.views.IndexRedirectView.as_view(), name='index'),

    url(r'^accounts/', include('django.contrib.auth.urls', namespace='auth')),
    url(r'^dashboards/', include('dashboard.urls', namespace='dashboard')),
    url(r'^deploy/', include('deploy.urls', namespace='deploy')),
    url(r'^django-rq/', include('django_rq.urls')),
    url(r'^dms/', include('dms.urls', namespace='dms')),
    url(r'^routing/', include('routing.urls', namespace='routing')),
    url(r'^tools/', include('tools.urls', namespace='tools')),
    url(r'^protected/(?P<path>.*)$', toolbox.views.ProtectedFileView.as_view()),

    # Django Rest Framework
    url(r'^api/', include(api.urls, namespace='api')),
    url(r'^api-auth/', include('rest_framework.urls', namespace='rest_framework')),
    # Django admin
    url(r'^admin/', admin.site.urls),
]

# Allow serving media content if in debug mode
if settings.DEBUG == True:
    urlpatterns += [
        url(r'^media/(?P<path>.*)$', django.views.static.serve, {'document_root': settings.MEDIA_ROOT,}),
    ]
