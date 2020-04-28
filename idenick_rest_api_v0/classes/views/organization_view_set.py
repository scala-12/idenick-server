"""organization view"""
from typing import Optional

from django.db.models.query_utils import Q
from django.shortcuts import get_object_or_404
from rest_framework import status

from idenick_app.models import (Checkpoint2Organization, Device2Organization,
                                Employee2Organization, Login, Organization)
from idenick_rest_api_v0.classes.utils import (login_utils, request_utils,
                                               views_utils)
from idenick_rest_api_v0.classes.views.abstract_view_set import AbstractViewSet
from idenick_rest_api_v0.serializers import organization_serializers


class OrganizationViewSet(AbstractViewSet):
    def get_serializer_by_action(self, action: str, is_full: Optional[bool] = False):
        result = None
        if (action == 'list') or (action == 'retrieve'):
            result = organization_serializers.ModelSerializer
        elif (action == 'create') or (action == 'partial_update'):
            result = organization_serializers.CreateSerializer

        return result

    def _get_queryset(self, request, base_filter=False, with_dropped=False):
        queryset = Organization.objects.all()

        dropped_filter = views_utils.get_deleted_filter(
            request, base_filter, with_dropped)
        if dropped_filter is views_utils.DeletedFilter.NON_DELETED.value:
            queryset = queryset.filter(dropped_at=None)
        elif dropped_filter is views_utils.DeletedFilter.DELETED_ONLY.value:
            queryset = queryset.exclude(dropped_at=None)

        if not base_filter:
            name_filter = request_utils.get_request_param(request, 'name')
            if name_filter is not None:
                queryset = queryset.filter(name__icontains=name_filter)

        checkpoint_filter = request_utils.get_request_param(
            request, 'checkpoint', True, base_filter=base_filter)
        if checkpoint_filter is not None:
            organization_id_list = queryset.values_list('id', flat=True)
            queryset = queryset.filter(id__in=Checkpoint2Organization.objects.filter(
                organization_id__in=organization_id_list).filter(dropped_at=None).filter(
                checkpoint_id=checkpoint_filter).values_list('organization', flat=True))
        device_filter = request_utils.get_request_param(
            request, 'device', True, base_filter=base_filter)
        if device_filter is not None:
            organization_id_list = queryset.values_list('id', flat=True)
            queryset = queryset.filter(id__in=Device2Organization.objects.filter(
                organization_id__in=organization_id_list).filter(dropped_at=None).filter(
                device_id=device_filter).values_list('organization', flat=True))
        employee_filter = request_utils.get_request_param(
            request, 'employee', True, base_filter=base_filter)
        if employee_filter is not None:
            organization_id_list = queryset.values_list('id', flat=True)
            queryset = queryset.filter(id__in=Employee2Organization.objects.filter(
                organization_id__in=organization_id_list).filter(dropped_at=None).filter(
                employee_id=employee_filter).values_list('organization', flat=True))

        return queryset

    @login_utils.login_check_decorator(Login.ADMIN)
    def list(self, request):
        result = self._list_data(request)

        return request_utils.response(result)

    @login_utils.login_check_decorator()
    def retrieve(self, request, pk=None):
        return self._retrieve(request, pk)

    @login_utils.login_check_decorator(Login.ADMIN)
    def create(self, request):
        serializer_class = self.get_current_serializer()
        serializer = serializer_class(data=request.data)
        result = None
        if serializer.is_valid():
            organization = Organization(**serializer.data)
            organization.save()
            result = self._response4update_n_create(
                data=organization, code=status.HTTP_201_CREATED)
        else:
            result = self._response4update_n_create(
                message=self._get_validation_error_msg(serializer.errors, Organization))

        return result

    @login_utils.login_check_decorator(Login.ADMIN)
    def partial_update(self, request, pk=None):
        login = login_utils.get_login(request.user)
        delete_restore_mode = (login.role == Login.ADMIN) \
            and (('delete' in request.data) or ('restore' in request.data))

        entity: Organization = get_object_or_404(self._get_queryset(request,
                                                                    with_dropped=delete_restore_mode),
                                                 pk=pk)

        result = None
        if delete_restore_mode:
            result = self._delete_or_restore(request, entity)
        else:
            serializer_class = self.get_current_serializer()
            result = None

            valid_result = self._validate_on_update(
                pk, serializer_class, Organization, request.data)
            serializer = valid_result.get('serializer')
            update = valid_result.get('update')
            if update is not None:
                entity.name = update.name
                entity.address = update.address
                entity.phone = update.phone
                entity.timezone = update.timezone
                entity.timesheet_start = update.timesheet_start
                entity.timesheet_end = update.timesheet_end
                entity.save()
                result = self._response4update_n_create(data=entity)
            else:
                result = self._response4update_n_create(
                    message=self._get_validation_error_msg(serializer.errors, Organization))

        return result

    def _alternative_valid(self, pk, data, errors, extra):
        return (len(errors.keys()) == 1) \
            and errors.keys().__contains__('name') \
            and (errors.get('name')[0].code == 'unique') \
            and not Organization.objects.filter(name=data.get('name')).filter(~Q(id=pk)).exists()
