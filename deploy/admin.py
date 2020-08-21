from django.contrib import admin

from deploy.models import DeviceType


class DeviceTypeViewAdmin(admin.ModelAdmin):
    list_display = ('category', 'manufacturer', 'model')
admin.site.register(DeviceType, DeviceTypeViewAdmin)
