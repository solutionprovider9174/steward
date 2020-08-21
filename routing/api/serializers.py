# third party
from rest_framework import serializers
from rest_framework.reverse import reverse, reverse_lazy
from rest_framework.serializers import raise_errors_on_nested_writes
from rest_framework.utils import model_meta
# local
from routing import models


class RecordSerializer(serializers.ModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name='api:routing-record-detail')
    class Meta:
        model = models.Record
        fields = ('url', 'id', 'route', 'order', 'preference', 'flags', 'service', 'regex', 'replacement')


class RouteSerializer(serializers.ModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name='api:routing-route-detail')
    records = RecordSerializer(many=True, read_only=True)
    class Meta:
        model = models.Route
        fields = ('url', 'id', 'name', 'trunkgroup', 'records', 'type')


class NumberSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Number
        fields = ('cc', 'number', 'route', 'modified')

    def create(self, validated_data):
        raise_errors_on_nested_writes('create', self, validated_data)
        ModelClass = self.Meta.model
        info = model_meta.get_field_info(ModelClass)
        many_to_many = {}
        for field_name, relation_info in info.relations.items():
            if relation_info.to_many and (field_name in validated_data):
                many_to_many[field_name] = validated_data.pop(field_name)

        try:
            cc = validated_data.pop('cc')
            number = validated_data.pop('number')
            validated_data['active'] = True
            instance,created = ModelClass.objects.update_or_create(cc=cc, number=number, defaults=validated_data)
        except TypeError as exc:
            msg = (
                'Got a `TypeError` when calling `%s.objects.create()`. '
                'This may be because you have a writable field on the '
                'serializer class that is not a valid argument to '
                '`%s.objects.create()`. You may need to make the field '
                'read-only, or override the %s.create() method to handle '
                'this correctly.\nOriginal exception text was: %s.' %
                (
                    ModelClass.__name__,
                    ModelClass.__name__,
                    self.__class__.__name__,
                    exc
                )
            )
            raise TypeError(msg)

        # Save many-to-many relationships after the instance is created.
        if many_to_many:
            for field_name, value in many_to_many.items():
                setattr(instance, field_name, value)

        return instance


class FraudBypassSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.FraudBypass
        fields = ('cc', 'number', 'modified')

    def create(self, validated_data):
        raise_errors_on_nested_writes('create', self, validated_data)
        ModelClass = self.Meta.model
        info = model_meta.get_field_info(ModelClass)
        many_to_many = {}
        for field_name, relation_info in info.relations.items():
            if relation_info.to_many and (field_name in validated_data):
                many_to_many[field_name] = validated_data.pop(field_name)

        try:
            cc = validated_data.pop('cc')
            number = validated_data.pop('number')
            instance,created = ModelClass.objects.update_or_create(cc=cc, number=number)
        except TypeError as exc:
            msg = (
                'Got a `TypeError` when calling `%s.objects.create()`. '
                'This may be because you have a writable field on the '
                'serializer class that is not a valid argument to '
                '`%s.objects.create()`. You may need to make the field '
                'read-only, or override the %s.create() method to handle '
                'this correctly.\nOriginal exception text was: %s.' %
                (
                    ModelClass.__name__,
                    ModelClass.__name__,
                    self.__class__.__name__,
                    exc
                )
            )
            raise TypeError(msg)

        # Save many-to-many relationships after the instance is created.
        if many_to_many:
            for field_name, value in many_to_many.items():
                setattr(instance, field_name, value)

        return instance


class OutboundRouteSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.OutboundRoute
        fields = ('number', 'end_office_route', 'long_distance_route', 'comment', 'modified')

    def create(self, validated_data):
        raise_errors_on_nested_writes('create', self, validated_data)
        ModelClass = self.Meta.model
        info = model_meta.get_field_info(ModelClass)
        many_to_many = {}
        for field_name, relation_info in info.relations.items():
            if relation_info.to_many and (field_name in validated_data):
                many_to_many[field_name] = validated_data.pop(field_name)

        try:
            number = validated_data.pop('number')
            instance,created = ModelClass.objects.update_or_create(number=number, defaults=validated_data)
        except TypeError as exc:
            msg = (
                'Got a `TypeError` when calling `%s.objects.create()`. '
                'This may be because you have a writable field on the '
                'serializer class that is not a valid argument to '
                '`%s.objects.create()`. You may need to make the field '
                'read-only, or override the %s.create() method to handle '
                'this correctly.\nOriginal exception text was: %s.' %
                (
                    ModelClass.__name__,
                    ModelClass.__name__,
                    self.__class__.__name__,
                    exc
                )
            )
            raise TypeError(msg)

        # Save many-to-many relationships after the instance is created.
        if many_to_many:
            for field_name, value in many_to_many.items():
                setattr(instance, field_name, value)

        return instance


class RemoteCallForwardSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.RemoteCallForward
        fields = ('called_number', 'forward_number', 'modified')
