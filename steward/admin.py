from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import CustomUser
from steward.models import GroupDefaultView, Profile

class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False

class UserAdmin(admin.ModelAdmin):
    # inlines = (ProfileInline, )
    pass
# Re-register UserAdmin
admin.site.register(CustomUser, UserAdmin)

# class ProfileAdmin(admin.ModelAdmin):
#     pass
#
# admin.site.register(Profile, ProfileAdmin)

class GroupDefaultViewAdmin(admin.ModelAdmin):
    list_display = ('group', 'priority', 'view_name')
admin.site.register(GroupDefaultView, GroupDefaultViewAdmin)
