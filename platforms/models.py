from django.db import models


class BroadworksPlatform(models.Model):
    name = models.CharField(max_length=32, unique=True)
    uri = models.CharField(max_length=1024)
    username = models.CharField(max_length=256)
    password = models.CharField(max_length=256)

    class Meta:
        ordering = ('name',)

    def __str__(self):
        return self.name
