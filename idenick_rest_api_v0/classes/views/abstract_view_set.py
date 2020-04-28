"""abstract view"""
from typing import Any, Dict, Optional

from django.shortcuts import get_object_or_404
from rest_framework import serializers, status, viewsets
from rest_framework.response import Response

from idenick_app.models import AbstractEntry, Department, Device, Login
from idenick_rest_api_v0.classes.utils import (login_utils, request_utils,
                                               views_utils)


class AbstractViewSet(viewsets.ViewSet):

    def get_serializer_by_action(self, action: str, is_full: Optional[bool] = False) -> serializers.ModelSerializer:
        pass

    def _get_queryset(self, request, base_filter: Optional[bool] = False, with_dropped: Optional[bool] = False):
        # TODO: описание base_filter
        pass

    def _delete_or_restore(self, request, entity: AbstractEntry,
                           return_entity: Optional[AbstractEntry] = None):
        info = views_utils.DeleteRestoreStatusChecker(
            entity=entity, delete_mode=('delete' in request.data),
            anyTimeRestore=('anyTime' in request.data))
        if (info.status is views_utils.DeleteRestoreCheckStatus.DELETABLE) \
                or (info.status is views_utils.DeleteRestoreCheckStatus.RESTORABLE):
            info.entity.save()
            result = self._response4update_n_create(
                data=info.entity if return_entity is None else return_entity)
        elif info.status is views_utils.DeleteRestoreCheckStatus.ALREADY_DELETED:
            result = self._response4update_n_create(
                message="Удаленная ранее запись")
        elif info.status is views_utils.DeleteRestoreCheckStatus.ALREADY_RESTORED:
            result = self._response4update_n_create(
                message="Восстановленная ранее запись")
        elif info.status is views_utils.DeleteRestoreCheckStatus.EXPIRED_TIME:
            result = self._response4update_n_create(
                message="Доступное время для восстановления истекло")

        return result

    def _response4update_n_create(self, code=status.HTTP_200_OK, data=None, message=None):
        result = None
        if data is None:
            result = Response(
                {'message': message, 'success': False},
                headers={'Access-Control-Allow-Origin': '*',
                         'Content-Type': 'application/json'},
                status=(status.HTTP_400_BAD_REQUEST if (code == status.HTTP_200_OK) else code))
        else:
            result = Response(
                {
                    'data': self.get_serializer_by_action('retrieve')(data).data,
                    'success': True
                },
                headers={'Access-Control-Allow-Origin': '*',
                         'Content-Type': 'application/json'},
                status=code)
        return result

    def get_current_serializer(self, is_full: Optional[bool] = False) -> serializers.ModelSerializer:
        """return serializer by action"""
        return self.get_serializer_by_action(action=self.action, is_full=is_full)

    def _list_data(self, request, queryset=None, is_full: Optional[bool] = False):
        _queryset = self._get_queryset(request) if (
            queryset is None) else queryset

        page = request_utils.get_request_param(request, 'page', True)
        per_page = request_utils.get_request_param(request, 'perPage', True)

        paginated_queryset = _queryset
        if (page is not None) and (per_page is not None):
            offset = page * per_page
            limit = offset + per_page
            paginated_queryset = _queryset[offset:limit]

        organization = None
        login = login_utils.get_login(request.user)
        if ((login.role == Login.CONTROLLER) or (login.role == Login.REGISTRATOR)):
            organization = login.organization_id

        serializer = self.get_current_serializer(is_full=is_full)(paginated_queryset, many=True, context={
            'organization': organization})

        return {'data': serializer.data,
                'baseCount': self._get_queryset(request, base_filter=True).count(),
                'filteredCount': _queryset.count()}

    def _retrieve(self, request, pk=None, queryset=None, is_full: Optional[bool] = False):
        return request_utils.response(self._retrieve_data(request, pk, queryset, is_full=is_full))

    def _retrieve_data(self, request, pk, queryset=None, is_full: Optional[bool] = False):
        _queryset = self._get_queryset(request, with_dropped=('withDeleted' in request.GET)) if (
            queryset is None) else queryset
        entity = get_object_or_404(_queryset, pk=pk)

        organization = None
        login = login_utils.get_login(request.user)
        if ((login.role == Login.CONTROLLER) or (login.role == Login.REGISTRATOR)):
            organization = login.organization_id
        serializer = self.get_current_serializer(is_full=is_full)(entity, context={
            'organization': organization})

        return {'data': serializer.data}

    def _get_validation_error_msg(self, errors, object_class, update_verbose=True):
        msg_arr = []
        for field in errors.keys():
            sub_err = []
            err_prefix = ''
            for err in errors.get(field):
                sub_msg = None
                if (field == 'non_field_errors'):
                    if (err.code == 'unique') \
                            and ((object_class == Department) or (object_class == Device)):
                        err_prefix = 'Название: '
                        sub_msg = ('Подразделение' if (
                            object_class == Department) else 'Прибор') \
                            + ' с таким названием уже существует'
                    else:
                        sub_msg = err.capitalize()
                else:
                    sub_msg = err.capitalize()

                sub_err.append(sub_msg)

            sub_err_str = ', '.join(sub_err)
            if (field != 'non_field_errors'):
                err_prefix = None
                if (update_verbose):
                    verbose_name = str(
                        object_class._meta.get_field(field).verbose_name)
                    verbose_end = ''
                    if (verbose_name.endswith('е')):
                        verbose_end = 'м'

                    sub_err_str = sub_err_str.replace(
                        verbose_name, verbose_name + verbose_end)
                    err_prefix = verbose_name
                else:
                    err_prefix = field
                err_prefix += ': '

            msg_arr.append(err_prefix.capitalize() + sub_err_str)

        return '\n'.join(msg_arr).replace('.,', ',')

    def _alternative_valid(self, pk, data, errors, extra=None):
        return False

    def _validate_on_update(self,
                            pk: str,
                            serializer_class: serializers.ModelSerializer,
                            Object_class: AbstractEntry,
                            data: Dict[str, str],
                            extra: Optional[Any] = None
                            ):
        update = None
        serializer = serializer_class(
            data=data, context={'entity_id': int(pk)})
        if serializer.is_valid() or self._alternative_valid(pk, data, serializer.errors, extra):
            serializer = serializer_class(data, context={'entity_id': int(pk)})
            update = Object_class(**serializer.data)

        return {'update': update, 'serializer': serializer}
