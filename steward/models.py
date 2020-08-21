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


from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from django.db import models


# User class
class CustomUser(AbstractUser):
    class Meta:
        permissions = (
            ("can_go_in_dashboard", "Can see dashboard for user"),
            ("can_go_in_deploy", "Can see deploy for user"),
            ("can_go_in_dms", "Can see dms for user"),
            ("can_go_in_platforms", "Can see platform for user"),
            ("can_go_in_routing", "Can see routing for user"),
            ("can_go_in_sansayvcm", "Can see sansayvcm for user"),
            ("can_go_in_toolbox", "Can see toolbox for user"),
            ("can_go_in_tool", "Can see tool for user"),

        )