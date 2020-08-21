from django.urls import re_path
import dms.views
app_name ='dms'
urlpatterns = [
    re_path(r'^000000000000\.cfg$', dms.views.PolycomDefaultView.as_view(), name='polycom-default'),
    re_path(r'^polycom-resync\.cfg$', dms.views.PolycomResyncView.as_view(), name='polycom-resync'),
    re_path(r'^(?P<slug>[0-9a-fA-F]{12})-phone\.cfg$', dms.views.PolycomView.as_view(), name='polycom'),
]
