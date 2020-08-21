import pytz

from django.db import models
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group


class Profile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    timezone = models.CharField(max_length=256, default='America/Chicago',
                                choices=((x,x) for x in pytz.country_timezones['US']))


class GroupDefaultView(models.Model):
    group = models.OneToOneField(Group, on_delete=models.CASCADE)
    priority = models.PositiveSmallIntegerField()
    view_name = models.CharField(max_length=256)
