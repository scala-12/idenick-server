"""device view"""
from typing import Optional

from django.db.models.query_utils import Q
from django.shortcuts import get_object_or_404
from rest_framework import status

from idenick_app.models import (
    Checkpoint, Device, Device2Organization, Login, Organization)
from idenick_rest_api_v0.classes.utils import (login_utils, request_utils,
                                               utils, views_utils)
from idenick_rest_api_v0.classes.views.abstract_view_set import AbstractViewSet
from idenick_rest_api_v0.serializers import (checkpoint_serializers,
                                             device_serializers,
                                             organization_serializers)


class DeviceViewSet(AbstractViewSet):
    def get_serializer_by_action(self, action: str, is_full: Optional[bool] = False):
        result = None
        if (action == 'list') or (action == 'retrieve'):
            result = device_serializers.ModelSerializer
        elif action == 'create':
            result = device_serializers.CreateSerializer
        elif action == 'partial_update':
            result = device_serializers.UpdateSerializer

        return result

    def _get_queryset(self, request, base_filter=False, with_dropped=False):
        queryset = Device.objects.all()

        dropped_filter = views_utils.get_deleted_filter(
            request, base_filter, with_dropped)
        if dropped_filter is views_utils.DeletedFilter.NON_DELETED.value:
            queryset = queryset.filter(dropped_at=None)
        elif dropped_filter is views_utils.DeletedFilter.DELETED_ONLY.value:
            queryset = queryset.exclude(dropped_at=None)

        login = login_utils.get_login(request.user)

        organization_filter = None
        if (login.role == Login.CONTROLLER) or (login.role == Login.REGISTRATOR):
            organization_filter = login.organization_id
            if with_dropped:
                organization_filter.update(with_dropped=True)
        elif login.role == Login.ADMIN:
            organization_filter = request_utils.get_request_param(
                request, 'organization', True, base_filter=base_filter)

        if not base_filter:
            name_filter = request_utils.get_request_param(request, 'name')
            if name_filter is not None:
                queryset = queryset.filter(
                    Q(name__icontains=name_filter) | Q(mqtt__icontains=name_filter))
        checkpoint_filter = request_utils.get_request_param(
            request, 'checkpoint', True, base_filter=base_filter)
        if checkpoint_filter is not None:
            checkpoint_devices = queryset.values(
                'id', 'checkpoint').filter(checkpoint=checkpoint_filter)\
                .values_list('id', flat=True)
            queryset = queryset.filter(id__in=checkpoint_devices)

        if organization_filter is not None:
            device_id_list = queryset.values_list('id', flat=True)
            devices_queryset = Device2Organization.objects.filter(
                organization_id=organization_filter, device_id__in=device_id_list)

            if (login.role == Login.ADMIN) \
                    or (dropped_filter is views_utils.DeletedFilter.NON_DELETED.value):
                devices_queryset = devices_queryset.filter(dropped_at=None)
            elif dropped_filter is views_utils.DeletedFilter.DELETED_ONLY.value:
                devices_queryset = devices_queryset.exclude(dropped_at=None)

            queryset = queryset.filter(
                id__in=devices_queryset.values_list('device_id', flat=True))

        return queryset

    @login_utils.login_check_decorator()
    def list(self, request):
        result = self._list_data(request)

        return request_utils.response(result)

    @login_utils.login_check_decorator()
    def retrieve(self, request, pk=None):
        result = self._retrieve_data(request, pk)

        login = login_utils.get_login(request.user)

        if 'full' in request.GET:
            entity = result.get('data')
            if (login.role == Login.CONTROLLER) or (login.role == Login.REGISTRATOR):
                if entity.get('dropped_at') is None:
                    dropped_at = Device2Organization.objects.get(
                        device=pk, organization=login.organization).dropped_at
                    if not (dropped_at is None):
                        entity.update(dropped_at=dropped_at.isoformat())
                        result.update(data=entity)

                result.update({'organization': organization_serializers.ModelSerializer(
                    Organization.objects.get(id=login.organization_id)).data})

            checkpoint_id = entity.get('checkpoint')
            if checkpoint_id is not None:
                result.update({'checkpoint':
                               checkpoint_serializers.ModelSerializer(
                                   Checkpoint.objects.get(id=checkpoint_id)).data})

        return request_utils.response(result)

    @login_utils.login_check_decorator(Login.REGISTRATOR, Login.ADMIN)
    def create(self, request):
        login = login_utils.get_login(request.user)
        serializer_class = self.get_current_serializer()
        device_data = request.data
        serializer = serializer_class(data=device_data)
        result = None
        if serializer.is_valid():
            device = Device(**serializer_class(device_data).data)
            device.save()

            organization = None
            if login.role == Login.REGISTRATOR:
                organization = login.organization_id
            elif login.role == Login.ADMIN:
                organization = request_utils.get_request_param(
                    request, 'organization', is_int=True)

            if organization is not None:
                Device2Organization.objects.create(
                    **{'organization_id': organization, 'device_id': device.id})

            result = self._response4update_n_create(
                data=device, code=status.HTTP_201_CREATED)
        else:
            result = self._response4update_n_create(
                message=self._get_validation_error_msg(serializer.errors, Device))

        return result

    @login_utils.login_check_decorator(Login.REGISTRATOR, Login.ADMIN)
    def partial_update(self, request, pk=None):
        login = login_utils.get_login(request.user)
        delete_restore_mode = ('delete' in request.data) or (
            'restore' in request.data)

        entity: Device = get_object_or_404(self._get_queryset(request,
                                                              with_dropped=delete_restore_mode),
                                           pk=pk)
        entity.device_type = 0 if entity.device_type is None else entity.device_type

        result = None
        if delete_restore_mode:
            if login.role == Login.ADMIN:
                result = self._delete_or_restore(request, entity)
            elif login.role == Login.REGISTRATOR:
                relations = Device2Organization.objects.filter(organization=login.organization,
                                                               device=entity)
                if relations.exists():
                    delete_or_restore_result = self._delete_or_restore(
                        request, entity=relations.first(), return_entity=entity)
                    if delete_or_restore_result.data.get('success'):
                        result = self._response4update_n_create(data=entity)
                    else:
                        result = delete_or_restore_result
        else:
            serializer_class = self.get_current_serializer()

            valid_result = self._validate_on_update(
                pk, serializer_class, Device, request.data)
            serializer = valid_result.get('serializer')
            update = valid_result.get('update')
            if update is not None:
                entity.name = update.name
                entity.description = update.description
                entity.config = update.config
                entity.timezone = update.timezone
                entity.checkpoint = update.checkpoint
                entity.save()
                result = self._response4update_n_create(data=entity)
            else:
                result = self._response4update_n_create(
                    message=self._get_validation_error_msg(serializer.errors, Device))

        return result

    def _alternative_valid(self, pk, data, errors, extra):
        return (len(errors.keys()) == 1) and errors.keys().__contains__('mqtt')\
            and (errors.get('mqtt')[0].code == 'unique')\
            and not Device.objects.filter(mqtt=data.get('mqtt')).exclude(id=pk).exists()
