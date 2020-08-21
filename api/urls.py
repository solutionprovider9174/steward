
from django.urls import re_path,include

from api import views
import routing.api.urls
import tools.api.urls

app_name ='api'
urlpatterns = [
    re_path(r'^$', views.RootAPIView.as_view(), name='index'),
    re_path(r'^routing/', include(routing.api.urls)),
    re_path(r'^tools/', include(tools.api.urls)),
]
