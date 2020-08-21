from tools.models import Process

from rest_framework import serializers


class ProcessSerializer(serializers.ModelSerializer):
    class Meta:
        model = Process
        fields = ('user', 'method', 'parameters', 'start_timestamp', 'end_timestamp', 'status', 'exception')
