"""checkpoint view"""
from typing import Optional

from django.db.models.query_utils import Q
from django.shortcuts import get_object_or_404
from rest_framework import status

from idenick_app.models import Checkpoint, Checkpoint2Organization, Login
from idenick_rest_api_v0.classes.utils import (login_utils, request_utils,
                                               views_utils)
from idenick_rest_api_v0.classes.views.abstract_view_set import AbstractViewSet
from idenick_rest_api_v0.serializers import checkpoint_serializers


class CheckpointViewSet(AbstractViewSet):
    def get_serializer_by_action(self, action: str, is_full: Optional[bool] = False):
        result = None
        if (action == 'list') or (action == 'retrieve'):
            result = checkpoint_serializers.ModelSerializer
        elif (action == 'create') or (action == 'partial_update'):
            result = checkpoint_serializers.CreateSerializer

        return result

    def _get_queryset(self, request, base_filter=False, with_dropped=False):
        queryset = Checkpoint.objects.all()

        dropped_filter = views_utils.get_deleted_filter(
            request, base_filter, with_dropped)
        if dropped_filter is views_utils.DeletedFilter.NON_DELETED.value:
            queryset = queryset.filter(dropped_at=None)
        elif dropped_filter is views_utils.DeletedFilter.DELETED_ONLY.value:
            queryset = queryset.exclude(dropped_at=None)

        login = login_utils.get_login(request.user)

        if not base_filter:
            name_filter = request_utils.get_request_param(request, 'name')
            if name_filter is not None:
                queryset = queryset.filter(name__icontains=name_filter)

        organization_filter = None
        if (login.role == Login.CONTROLLER) or (login.role == Login.REGISTRATOR):
            organization_filter = login.organization_id
        elif login.role == Login.ADMIN:
            organization_filter = request_utils.get_request_param(
                request, 'organization', True, base_filter=base_filter)
        if organization_filter is not None:
            group_id_list = queryset.values_list('id', flat=True)
            groups_queryset = Checkpoint2Organization.objects.filter(
                organization_id=organization_filter, checkpoint_id__in=group_id_list)

            if (login.role == Login.ADMIN) \
                    or (dropped_filter is views_utils.DeletedFilter.NON_DELETED.value):
                groups_queryset = groups_queryset.filter(dropped_at=None)
            elif dropped_filter is views_utils.DeletedFilter.DELETED_ONLY.value:
                groups_queryset = groups_queryset.exclude(dropped_at=None)

            queryset = queryset.filter(
                id__in=groups_queryset.values_list('checkpoint_id', flat=True))

        return queryset

    @login_utils.login_check_decorator()
    def list(self, request):
        result = self._list_data(request)

        return request_utils.response(result)

    @login_utils.login_check_decorator()
    def retrieve(self, request, pk=None):
        result = self._retrieve_data(request, pk)

        return request_utils.response(result)

    @login_utils.login_check_decorator(Login.REGISTRATOR, Login.ADMIN)
    def create(self, request):
        serializer_class = self.get_current_serializer()
        serializer = serializer_class(data=request.data)
        result = None
        if serializer.is_valid():
            group = Checkpoint(**serializer.data)
            group.save()

            login = login_utils.get_login(request.user)

            organization = None
            if login.role == Login.REGISTRATOR:
                organization = login.organization_id
            elif login.role == Login.ADMIN:
                organization = request_utils.get_request_param(
                    request, 'organization', is_int=True)

            if organization is not None:
                Checkpoint2Organization.objects.create(
                    **{'organization_id': organization,
                       'checkpoint_id': group.id})

            result = self._response4update_n_create(
                data=group, code=status.HTTP_201_CREATED)
        else:
            result = self._response4update_n_create(
                message=self._get_validation_error_msg(serializer.errors, Checkpoint))

        return result

    @login_utils.login_check_decorator(Login.REGISTRATOR, Login.ADMIN)
    def partial_update(self, request, pk=None):
        login = login_utils.get_login(request.user)
        delete_restore_mode = (login.role == Login.ADMIN) \
            and (('delete' in request.data) or ('restore' in request.data))

        entity: Checkpoint = get_object_or_404(
            self._get_queryset(request, with_dropped=delete_restore_mode), pk=pk)

        result = None
        if delete_restore_mode:
            result = self._delete_or_restore(request, entity)
        else:
            serializer_class = self.get_current_serializer()
            result = None

            valid_result = self._validate_on_update(
                pk, serializer_class, Checkpoint, request.data)
            serializer = valid_result.get('serializer')
            update = valid_result.get('update')
            if update is not None:
                entity.name = update.name
                entity.description = update.description
                entity.rights = update.rights
                entity.save()
                result = self._response4update_n_create(data=entity)
            else:
                result = self._response4update_n_create(
                    message=self._get_validation_error_msg(serializer.errors, Checkpoint))

        return result

    def _alternative_valid(self, pk, data, errors, extra):
        return (len(errors.keys()) == 1) and errors.keys().__contains__('name') and (errors.get('name')[0].code == 'unique') and not Checkpoint.objects.filter(name=data.get('name')).filter(~Q(id=pk)).exists()
