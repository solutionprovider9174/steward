# Django
from django.urls import re_path, include

# Third Party
from rest_framework import routers

# Application
from tools.api import views


# Router
router = routers.DefaultRouter()
router.register(r'processes', views.ProcessDetailAPIViewSet, basename='tools-process')
router.register(r'registrations', views.RegistrationAPIViewSet, basename='tools-registration')


urlpatterns = [
    re_path(r'^$', views.ToolsRootView.as_view(), name='tools-root'),
    re_path(r'^dect-lookup$', views.DeviceDectLookupAPIView.as_view(), name='tools-dect-lookup'),
    re_path(r'^', include(router.urls)),
]
