# Python
from collections import OrderedDict
import requests

# Django
from django.conf import settings

# Third Party

import django_filters
# updated from rest_framework.filters import FilterSet
# to django_filters.rest_framework import FilterSet
from django_filters.rest_framework import FilterSet
from rest_framework.generics import GenericAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.mixins import (
    CreateModelMixin, DestroyModelMixin, ListModelMixin, RetrieveModelMixin,
    UpdateModelMixin,
)
from rest_framework.permissions import (
    DjangoModelPermissionsOrAnonReadOnly, IsAdminUser, IsAuthenticated,
)
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet, ViewSet

# Application
from routing import models
from routing.api import serializers


class RouteRootView(APIView):
    def get(self, request, format=None):
        args = {'request': request, 'format': format}
        context = dict()
        context['fraud-bypass'] = reverse('api:routing-fraud-bypass-list', **args)
        context['numbers'] = reverse('api:routing-number-list', **args)
        context['outbound-routes'] = reverse('api:routing-outbound-route-list', **args)
        context['records'] = reverse('api:routing-record-list', **args)
        context['remote-call-forward'] = reverse('api:routing-remote-call-forward-list', **args)
        context['routes'] = reverse('api:routing-route-list', **args)
        return Response(context)


class RouteViewSet(ModelViewSet):
    queryset = models.Route.objects.all()
    permission_classes = (DjangoModelPermissionsOrAnonReadOnly, IsAuthenticated,)
    serializer_class = serializers.RouteSerializer
    filter_fields = ('type',)

class RecordViewSet(ModelViewSet):
    queryset = models.Record.objects.all()
    permission_classes = (DjangoModelPermissionsOrAnonReadOnly, IsAuthenticated,)
    serializer_class = serializers.RecordSerializer


class NumberFilter(FilterSet):
    modified_gt = django_filters.IsoDateTimeFilter(field_name='modified', lookup_expr='gt')
    modified_lte = django_filters.IsoDateTimeFilter(field_name='modified', lookup_expr='lte')
    class Meta:
        model = models.Number
        fields = ['cc', 'number', 'route', 'active', 'modified_gt', 'modified_lte']


class NumberListView(UpdateModelMixin, ListModelMixin, CreateModelMixin, GenericAPIView):
    queryset = models.Number.objects.filter(active=True)
    permission_classes = (DjangoModelPermissionsOrAnonReadOnly, IsAuthenticated,)
    serializer_class = serializers.NumberSerializer
    filter_class = NumberFilter
    _instance = None

    def get_queryset(self):
        queryset = super(NumberListView, self).get_queryset()
        q = self.request.query_params.get('q', None)
        if q is not None:
            if q.startswith('^'):
                queryset = queryset.filter(number__startswith=q[1:])
            elif q.endswith('$'):
                queryset = queryset.filter(number__endswith=q[:-1])
            else:
                queryset = queryset.filter(number__contains=q)
        return queryset

    def get(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            data = serializer.data
            for item in data:
                item['url'] = '{}://{}{}'.format(request.scheme, request.META.get('HTTP_HOST'), reverse('api:routing-number-detail', args=(item.get('cc'), item.get('number'))))
            return self.get_paginated_response(data)

        serializer = self.get_serializer(queryset, many=True)
        data = serializer.data
        for item in data:
            item['url'] = '{}://{}{}'.format(request.scheme, request.META.get('HTTP_HOST'), reverse('api:routing-number-detail', args=(item.get('cc'), item.get('number'))))
        return Response(data)

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        route = models.Route.objects.get(pk=serializer.data['route'])
        models.NumberHistory.objects.create(cc=serializer.data['cc'], number=serializer.data['number'], user=request.user, action='Routes to {}'.format(route.name))
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def get_object(self):
        if self._instance:
            return self._instance
        else:
            cc = self.request.data.get('cc', None)
            number = self.request.data.get('number', None)
            self._instance = models.Number.objects.get(cc=cc, number=number)
            return self._instance

    def put(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            instance.active = True
            partial = kwargs.pop('partial', False)
            serializer = self.get_serializer(instance, data=request.data, partial=partial)
            serializer.is_valid(raise_exception=True)
            self.perform_update(serializer)
            data = serializer.data
            data['url'] = '{}://{}{}'.format(request.scheme, request.META.get('HTTP_HOST'), reverse('api:routing-number-detail', args=(instance.cc, instance.number)))
            models.NumberHistory.objects.create(cc=instance.cc, number=instance.number, user=request.user, action='Routes to {}'.format(instance.route.name))
            return Response(data)
        except models.Number.DoesNotExist:
            resp = self.create(request, *args, **kwargs)
            route = models.Route.objects.get(id=resp.data.get('route'))
            models.NumberHistory.objects.create(cc=resp.data.get('cc'), number=resp.data.get('number'), user=request.user, action='Routes to {}'.format(route.name))
            return resp


class NumberDetailView(RetrieveUpdateDestroyAPIView):
    queryset = models.Number.objects.filter(active=True)
    permission_classes = (DjangoModelPermissionsOrAnonReadOnly, IsAuthenticated,)
    serializer_class = serializers.NumberSerializer

    def get_object(self):
        queryset = self.get_queryset()
        return queryset.get(cc=self.kwargs['cc'], number=self.kwargs['number'])

    def get(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        data = serializer.data
        data['url'] = '{}://{}{}'.format(request.scheme, request.META.get('HTTP_HOST'), reverse('api:routing-number-detail', args=(instance.cc, instance.number)))
        return Response(data)

    def put(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        models.NumberHistory.objects.create(cc=instance.cc, number=instance.number, user=request.user, action='Routes to {}'.format(instance.route.name))
        return Response(serializer.data)

    def delete(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.active = False
        instance.save()
        models.NumberHistory.objects.create(cc=instance.cc, number=instance.number, user=request.user, action='Deleted')
        return Response(status=status.HTTP_204_NO_CONTENT)


class FraudBypassFilter(FilterSet):
    modified_gt = django_filters.IsoDateTimeFilter(field_name='modified', lookup_expr='gt')
    modified_lte = django_filters.IsoDateTimeFilter(field_name='modified', lookup_expr='lte')
    class Meta:
        model = models.FraudBypass
        fields = ['cc', 'number', 'modified_gt', 'modified_lte']


class FraudBypassListView(ListModelMixin, CreateModelMixin, GenericAPIView):
    queryset = models.FraudBypass.objects.all()
    permission_class = (DjangoModelPermissionsOrAnonReadOnly, IsAuthenticated,)
    serializer_class = serializers.FraudBypassSerializer
    filter_class = FraudBypassFilter

    def get_queryset(self):
        queryset = super(FraudBypassListView, self).get_queryset()
        q = self.request.query_params.get('q', None)
        if q is not None:
            if q.startswith('^'):
                queryset = queryset.filter(number__startswith=q[1:])
            elif q.endswith('$'):
                queryset = queryset.filter(number__endswith=q[:-1])
            else:
                queryset = queryset.filter(number__contains=q)
        return queryset

    def get(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            data = serializer.data
            for item in data:
                item['url'] = '{}://{}{}'.format(request.scheme, request.META.get('HTTP_HOST'), reverse('api:routing-fraud-bypass-detail', args=(item.get('cc'), item.get('number'))))
            return self.get_paginated_response(data)

        serializer = self.get_serializer(queryset, many=True)
        data = serializer.data
        for item in data:
            item['url'] = '{}://{}{}'.format(request.scheme, request.META.get('HTTP_HOST'), reverse('api:routing-fraud-bypass-detail', args=(item.get('cc'), item.get('number'))))
        return Response(data)

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        models.FraudBypassHistory.objects.create(cc=serializer.data['cc'], number=serializer.data['number'], user=request.user, action='Created')
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


class FraudBypassDetailView(RetrieveUpdateDestroyAPIView):
    queryset = models.FraudBypass.objects.all()
    permission_classes = (DjangoModelPermissionsOrAnonReadOnly, IsAuthenticated,)
    serializer_class = serializers.FraudBypassSerializer

    def get_object(self):
        queryset = self.get_queryset()
        return queryset.get(cc=self.kwargs['cc'], number=self.kwargs['number'])

    def get(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        data = serializer.data
        data['url'] = '{}://{}{}'.format(request.scheme, request.META.get('HTTP_HOST'), reverse('api:routing-fraud-bypass-detail', args=(instance.cc, instance.number)))
        return Response(data)

    def put(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        models.FraudBypassHistory.objects.create(cc=instance.cc, number=instance.number, user=request.user, action='Updated')
        return Response(serializer.data)

    def delete(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()
        models.FraudBypassHistory.objects.create(cc=instance.cc, number=instance.number, user=request.user, action='Deleted')
        return Response(status=status.HTTP_204_NO_CONTENT)


class OutboundRouteFilter(FilterSet):
    modified_gt = django_filters.IsoDateTimeFilter(field_name='modified', lookup_expr='gt')
    modified_lte = django_filters.IsoDateTimeFilter(field_name='modified', lookup_expr='lte')
    class Meta:
        model = models.OutboundRoute
        fields = ['number', 'end_office_route', 'long_distance_route', 'modified_gt', 'modified_lte']


class OutboundRouteListView(ListModelMixin, CreateModelMixin, GenericAPIView):
    queryset = models.OutboundRoute.objects.all()
    permission_classe = (DjangoModelPermissionsOrAnonReadOnly, IsAuthenticated,)
    serializer_class = serializers.OutboundRouteSerializer
    filter_class = OutboundRouteFilter

    def get_queryset(self):
        queryset = super(OutboundRouteListView, self).get_queryset()
        q = self.request.query_params.get('q', None)
        if q is not None:
            if q.startswith('^'):
                queryset = queryset.filter(number__startswith=q[1:])
            elif q.endswith('$'):
                queryset = queryset.filter(number__endswith=q[:-1])
            else:
                queryset = queryset.filter(number__contains=q)
        return queryset

    def get(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            data = serializer.data
            for item in data:
                item['url'] = '{}://{}{}'.format(request.scheme, request.META.get('HTTP_HOST'), reverse('api:routing-outbound-route-detail', args=(item.get('number'),)))
            return self.get_paginated_response(data)

        serializer = self.get_serializer(queryset, many=True)
        data = serializer.data
        for item in data:
            item['url'] = '{}://{}{}'.format(request.scheme, request.META.get('HTTP_HOST'), reverse('api:routing-outbound-route-detail', args=(item.get('number'),)))
        return Response(data)

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        models.OutboundRouteHistory.objects.create(number=serializer.data['number'], user=request.user, action='Created')
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


class OutboundRouteDetailView(RetrieveUpdateDestroyAPIView):
    queryset = models.OutboundRoute.objects.all()
    permission_classes = (DjangoModelPermissionsOrAnonReadOnly, IsAuthenticated,)
    serializer_class = serializers.OutboundRouteSerializer

    def get_object(self):
        queryset = self.get_queryset()
        return queryset.get(number=self.kwargs['number'])

    def get(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        data = serializer.data
        data['url'] = '{}://{}{}'.format(request.scheme, request.META.get('HTTP_HOST'), reverse('api:routing-outbound-route-detail', args=(instance.number,)))
        return Response(data)

    def put(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        models.OutboundRouteHistory.objects.create(number=instance.number, user=request.user, action='Updated')
        return Response(serializer.data)

    def delete(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()
        models.OutboundRouteHistory.objects.create(number=instance.number, user=request.user, action='Deleted')
        return Response(status=status.HTTP_204_NO_CONTENT)


class RemoteCallForwardFilter(FilterSet):
    modified_gt = django_filters.IsoDateTimeFilter(field_name='modified', lookup_expr='gt')
    modified_lte = django_filters.IsoDateTimeFilter(field_name='modified', lookup_expr='lte')
    class Meta:
        model = models.RemoteCallForward
        fields = ['called_number', 'forward_number', 'modified_gt', 'modified_lte']


class RemoteCallForwardListView(ListModelMixin, CreateModelMixin, GenericAPIView):
    queryset = models.RemoteCallForward.objects.all()
    permission_classe = (DjangoModelPermissionsOrAnonReadOnly, IsAuthenticated,)
    serializer_class = serializers.RemoteCallForwardSerializer
    filter_class = RemoteCallForwardFilter

    def get_queryset(self):
        queryset = super(RemoteCallForwardListView, self).get_queryset()
        q = self.request.query_params.get('q', None)
        if q is not None:
            if q.startswith('^'):
                queryset = queryset.filter(called_number__startswith=q[1:])
            elif q.endswith('$'):
                queryset = queryset.filter(called_number__endswith=q[:-1])
            else:
                queryset = queryset.filter(called_number__contains=q)
        return queryset

    def get(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            data = serializer.data
            for item in data:
                item['url'] = '{}://{}{}'.format(request.scheme, request.META.get('HTTP_HOST'), reverse('api:routing-remote-call-forward-detail', args=(item.get('called_number'),)))
            return self.get_paginated_response(data)

        serializer = self.get_serializer(queryset, many=True)
        data = serializer.data
        for item in data:
            item['url'] = '{}://{}{}'.format(request.scheme, request.META.get('HTTP_HOST'), reverse('api:routing-remote-call-forward-detail', args=(item.get('called_number'),)))
        return Response(data)

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        models.RemoteCallForwardHistory.objects.create(called_number=serializer.data['called_number'],
                                                       user=request.user,
                                                       action='Created, Called Number: {} Forward Number {}'.format(
                                                           serializer.data['called_number'],
                                                           serializer.data['forward_number']))
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


class RemoteCallForwardDetailView(RetrieveUpdateDestroyAPIView):
    queryset = models.RemoteCallForward.objects.all()
    permission_classes = (DjangoModelPermissionsOrAnonReadOnly, IsAuthenticated,)
    serializer_class = serializers.RemoteCallForwardSerializer

    def get_object(self):
        queryset = self.get_queryset()
        return queryset.get(called_number=self.kwargs['called_number'])

    def get(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        data = serializer.data
        data['url'] = '{}://{}{}'.format(request.scheme, request.META.get('HTTP_HOST'), reverse('api:routing-remote-call-forward-detail', args=(instance.called_number,)))
        return Response(data)

    def put(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        models.RemoteCallForwardHistory.objects.create(called_number=instance.called_number, user=request.user, action='Updated')
        return Response(serializer.data)

    def delete(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()
        models.RemoteCallForwardHistory.objects.create(called_number=instance.called_number, user=request.user, action='Deleted')
        return Response(status=status.HTTP_204_NO_CONTENT)
