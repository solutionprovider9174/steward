from django.urls import re_path
import dashboard.views

app_name ='dashboard'
urlpatterns = [
    re_path(r'^$', dashboard.views.EmptyDashboardView.as_view(), name='empty'),
   re_path(r'^voip$', dashboard.views.VoipDashboardView.as_view(), name='voip'),
]
