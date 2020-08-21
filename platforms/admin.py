# django
from django.contrib import admin
# local
from .models import BroadworksPlatform


# Register your models here.
admin.site.register(BroadworksPlatform, admin.ModelAdmin)
