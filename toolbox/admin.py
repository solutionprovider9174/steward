from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User

from toolbox.models import GroupDefaultView, Profile

class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False

class UserAdmin(BaseUserAdmin):
    inlines = (ProfileInline, )

# Re-register UserAdmin
admin.site.unregister(User)
admin.site.register(User, UserAdmin)


class GroupDefaultViewAdmin(admin.ModelAdmin):
    list_display = ('group', 'priority', 'view_name')
admin.site.register(GroupDefaultView, GroupDefaultViewAdmin)
