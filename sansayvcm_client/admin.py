from django.contrib import admin

# Register your models here.
from .models import SansayVcmServer
from .models import SansayCluster

admin.site.register(SansayVcmServer)
admin.site.register(SansayCluster)

