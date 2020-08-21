# Python
import datetime

# Django
from django.db.models.signals import post_save
from django.dispatch import receiver

# Application
from routing import models


@receiver(post_save, sender=models.Record)
def route_post_save(sender, **kwargs):
    instance = kwargs['instance']
    instance.route.numbers.all().update(modified=datetime.datetime.now())
    print(instance)
