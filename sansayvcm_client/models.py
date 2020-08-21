from django.db import models

class SansayVcmServer(models.Model):
    name = models.CharField(max_length=32, unique=True)
    uri = models.CharField(max_length=1021)
    username = models.CharField(max_length=256)
    password = models.CharField(max_length=256)
    
    class Meta:
        ordering = ('name',)

    def __str__(self):
        return self.name


class SansayCluster(models.Model):
    server = models.ForeignKey(SansayVcmServer, on_delete=models.CASCADE)
    name = models.CharField(max_length=32, unique=True)
    cluster_id = models.IntegerField()
    route_table = models.CharField(max_length=32)

    class Meta:
        ordering = ('name',)

    def __str__(self):
        return self.name


class RouteTableLog(models.Model):
    cluster_id = models.CharField(max_length=32)
    number = models.CharField(max_length=64)
    action = models.CharField(max_length=32)
    xmlcfg = models.TextField(null=True)
    result_status = models.CharField(max_length=32)
    result_data = models.TextField(null=True)
    created = models.DateTimeField(null=True, default=None)
    
    class Meta:
        ordering = ('-created',)

