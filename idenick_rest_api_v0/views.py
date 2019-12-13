"""views"""
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional

from django.contrib.auth.models import User
from django.db.models.expressions import Value
from django.db.models.functions.text import Concat
from django.db.models.query_utils import Q
from django.http.request import QueryDict
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import api_view
from rest_framework.response import Response

from idenick_app.models import (AbstractEntry, Department, Device,
                                Device2Organization, DeviceGroup,
                                DeviceGroup2Organization, Employee,
                                Employee2Department, Employee2Organization,
                                Login, Organization)
from idenick_rest_api_v0.classes.utils import (login_utils, relation_utils,
                                               report_utils, request_utils,
                                               utils)
from idenick_rest_api_v0.classes.utils.mqtt_utils import BiometryType
from idenick_rest_api_v0.classes.utils.mqtt_utils import \
    registrate_biometry as registrate_biometry_by_device
from idenick_rest_api_v0.serializers import (DepartmentSerializers,
                                             DeviceGroupSerializers,
                                             DeviceSerializers,
                                             EmployeeSerializers,
                                             LoginSerializer,
                                             OrganizationSerializers,
                                             UserSerializer)


class _ErrorMessage(Enum):
    UNIQUE_DEPARTMENT_NAME = 'Подразделение с таким названием уже существует'


class _AbstractViewSet(viewsets.ViewSet):
    _serializer_classes = None

    def _get_queryset(self, request, base_filter=False, with_dropped=False):
        pass

    def _delete_or_restore(self, request, entity: AbstractEntry,
                           return_entity: Optional[AbstractEntry] = None):
        info = _DeleteRestoreStatusChecker(
            entity=entity, delete_mode=('delete' in request.data))
        if (info.status is _DeleteRestoreCheckStatus.DELETABLE) \
                or (info.status is _DeleteRestoreCheckStatus.RESTORABLE):
            info.entity.save()
            result = self._response4update_n_create(
                data=info.entity if return_entity is None else return_entity)
        elif info.status is _DeleteRestoreCheckStatus.ALREADY_DELETED:
            result = self._response4update_n_create(
                message="Удаленная ранее запись")
        elif info.status is _DeleteRestoreCheckStatus.ALREADY_RESTORED:
            result = self._response4update_n_create(
                message="Восстановленная ранее запись")
        elif info.status is _DeleteRestoreCheckStatus.EXPIRED_TIME:
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
                    'data': self._serializer_classes.get('retrieve')(data).data,
                    'success': True
                },
                headers={'Access-Control-Allow-Origin': '*',
                         'Content-Type': 'application/json'},
                status=code)
        return result

    def get_serializer_class(self):
        """return serializer by action"""
        return self._serializer_classes[self.action]

    def _list_data(self, request, queryset=None):
        _queryset = self._get_queryset(request) if (
            queryset is None) else queryset

        page = request_utils.get_request_param(request, 'page', True)
        per_page = request_utils.get_request_param(request, 'perPage', True)

        if (page is not None) and (per_page is not None):
            offset = page * per_page
            limit = offset + per_page
            _queryset = _queryset[offset:limit]

        organization = None
        login = login_utils.get_login(request.user)
        if ((login.role == Login.CONTROLLER) or (login.role == Login.REGISTRATOR)):
            organization = login.organization_id

        serializer = self.get_serializer_class()(_queryset, many=True, context={
            'organization': organization})

        return {'data': serializer.data, 'count': self._get_queryset(request, True).count()}

    def _retrieve(self, request, pk=None, queryset=None):
        return request_utils.response(self._retrieve_data(request, pk, queryset))

    def _retrieve_data(self, request, pk, queryset=None):
        _queryset = self._get_queryset(request, with_dropped=('withDeleted' in request.GET)) if (
            queryset is None) else queryset
        entity = get_object_or_404(_queryset, pk=pk)

        organization = None
        login = login_utils.get_login(request.user)
        if ((login.role == Login.CONTROLLER) or (login.role == Login.REGISTRATOR)):
            organization = login.organization_id
        serializer = self.get_serializer_class()(entity, context={
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

    def _validate_on_update(self, pk, serializer_class, Object_class, data, extra=None):
        update = None
        serializer = serializer_class(data=data)
        if serializer.is_valid():
            update = Object_class(**serializer.data)
        elif self._alternative_valid(pk, data, serializer.errors, extra):
            serializer = serializer_class(data)
            update = Object_class(**serializer.data)

        return {'update': update, 'serializer': serializer}


class _DeleteRestoreCheckStatus(Enum):
    """result of  delete/restore entity"""
    DELETABLE = 'DELETABLE'
    ALREADY_DELETED = 'ALREADY_DELETED'
    RESTORABLE = 'RESTORABLE'
    ALREADY_RESTORED = 'ALREADY_RESTORED'
    EXPIRED_TIME = 'EXPIRED_TIME'


@dataclass
class _DeleteRestoreStatusChecker:
    """info about delete/restore entity"""

    def __init__(self, entity: AbstractEntry, delete_mode: Optional[bool] = True):
        status = None
        if delete_mode:
            if entity.dropped_at is None:
                entity.dropped_at = datetime.now()
                status = _DeleteRestoreCheckStatus.DELETABLE
            else:
                status = _DeleteRestoreCheckStatus.ALREADY_DELETED
        elif entity.dropped_at is not None:
            if (datetime.now() - entity.dropped_at.replace(tzinfo=None)) < timedelta(minutes=5):
                entity.dropped_at = None
                status = _DeleteRestoreCheckStatus.RESTORABLE
            else:
                status = _DeleteRestoreCheckStatus.EXPIRED_TIME
        else:
            status = _DeleteRestoreCheckStatus.ALREADY_RESTORED

        self.status = status
        self.entity = entity


class OrganizationViewSet(_AbstractViewSet):
    _serializer_classes = {
        'list': OrganizationSerializers.ModelSerializer,
        'retrieve': OrganizationSerializers.ModelSerializer,
        'create': OrganizationSerializers.CreateSerializer,
        'partial_update': OrganizationSerializers.CreateSerializer,
    }

    def _get_queryset(self, request, base_filter=False, with_dropped=False):
        queryset = Organization.objects.all()
        if not with_dropped:
            queryset = queryset.filter(dropped_at=None)

        if not base_filter:
            name_filter = request_utils.get_request_param(request, 'name')
            if name_filter is not None:
                queryset = queryset.filter(name__icontains=name_filter)

        device_group_filter = request_utils.get_request_param(
            request, 'deviceGroup', True, base_filter=base_filter)
        if device_group_filter is not None:
            organization_id_list = queryset.values_list('id', flat=True)
            queryset = queryset.filter(id__in=DeviceGroup2Organization.objects.filter(
                organization_id__in=organization_id_list).filter(dropped_at=None).filter(
                device_group_id=device_group_filter).values_list('organization', flat=True))
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
        serializer_class = self.get_serializer_class()
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
            serializer_class = self.get_serializer_class()
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


class DepartmentViewSet(_AbstractViewSet):
    _serializer_classes = {
        'list': DepartmentSerializers.ModelSerializer,
        'retrieve': DepartmentSerializers.ModelSerializer,
        'create': DepartmentSerializers.CreateSerializer,
        'partial_update': DepartmentSerializers.CreateSerializer,
    }

    def _get_queryset(self, request, base_filter=False, with_dropped=False):
        login = login_utils.get_login(request.user)
        queryset = Department.objects.all()
        if not with_dropped:
            queryset = queryset.filter(dropped_at=None)

        role = login.role
        if (role == Login.CONTROLLER) or (role == Login.REGISTRATOR):
            queryset = queryset.filter(
                organization_id=login.organization_id)

        if not base_filter:
            name_filter = request_utils.get_request_param(request, 'name')
            if name_filter is not None:
                queryset = queryset.filter(name__icontains=name_filter)

        employee_filter = request_utils.get_request_param(
            request, 'employee', True, base_filter=base_filter)
        if employee_filter is not None:
            queryset = queryset.filter(id__in=Employee2Department.objects.filter(
                employee_id=employee_filter).values_list('department_id', flat=True))

        return queryset

    @login_utils.login_check_decorator(Login.REGISTRATOR, Login.CONTROLLER)
    def list(self, request):
        queryset = self._get_queryset(request)

        result = self._list_data(request, queryset)

        if 'full' in request.GET:
            organizations_ids = set(
                map(lambda d: d.get('organization'), result.get('data')))
            result.update(
                {'organizations': utils.get_organizations_by_id(organizations_ids)})

        return request_utils.response(result)

    @login_utils.login_check_decorator(Login.REGISTRATOR, Login.CONTROLLER)
    def retrieve(self, request, pk=None):
        result = self._retrieve_data(request, pk)

        if 'full' in request.GET:
            result.update({'organization': OrganizationSerializers.ModelSerializer(
                Organization.objects.get(id=result.get('data',).get('organization'))).data})

        return request_utils.response(result)

    @login_utils.login_check_decorator(Login.REGISTRATOR)
    def create(self, request):
        serializer_class = self.get_serializer_class()

        department_data = QueryDict('', mutable=True)
        department_data.update(request.data)
        department_data.update(
            {'organization': login_utils.get_login(request.user).organization_id})
        serializer = serializer_class(data=department_data)
        result = None

        if serializer.is_valid():
            department = Department(**serializer.data)
            if Department.objects.filter(name=department.name).exists():
                result = self._response4update_n_create(
                    message=_ErrorMessage.UNIQUE_DEPARTMENT_NAME.value)
            else:
                department.save()
                result = self._response4update_n_create(
                    data=department, code=status.HTTP_201_CREATED)
        else:
            result = self._response4update_n_create(
                message=self._get_validation_error_msg(serializer.errors, Department))

        return result

    @login_utils.login_check_decorator(Login.REGISTRATOR)
    def partial_update(self, request, pk=None):
        login = login_utils.get_login(request.user)
        delete_restore_mode = (login.role == Login.ADMIN) \
            and (('delete' in request.data) or ('restore' in request.data))

        entity: Department = get_object_or_404(
            self._get_queryset(request, with_dropped=delete_restore_mode), pk=pk)

        result = None
        if delete_restore_mode:
            result = self._delete_or_restore(request, entity)
        else:
            serializer_class = self.get_serializer_class()
            result = None

            department_data = QueryDict('', mutable=True)
            department_data.update(request.data)
            organization_id = {'organization': Login.objects.get(
                user=request.user).organization_id}
            department_data.update(organization_id)

            valid_result = self._validate_on_update(
                pk, serializer_class, Department, department_data, organization_id)
            serializer = valid_result.get('serializer')
            update = valid_result.get('update')
            if update is not None:
                entity.name = update.name
                entity.rights = update.rights
                entity.address = update.address
                entity.description = update.description
                entity.save()
                result = self._response4update_n_create(data=entity)
            else:
                result = self._response4update_n_create(
                    message=self._get_validation_error_msg(serializer.errors, Department))

        return result

    def _alternative_valid(self, pk, data, errors, extra):
        return (len(errors.keys()) == 1) \
            and errors.keys().__contains__('non_field_errors') \
            and (errors.get('non_field_errors')[0].code == 'unique') \
            and not Department.objects.filter(Q(name=data.get('name'))
                                              & Q(organization_id=extra.get('organization'))) \
            .filter(~Q(id=pk)).exists()


class EmployeeViewSet(_AbstractViewSet):
    _serializer_classes = {
        'list': EmployeeSerializers.ModelSerializer,
        'retrieve': EmployeeSerializers.ModelSerializer,
        'create': EmployeeSerializers.CreateSerializer,
        'partial_update': EmployeeSerializers.CreateSerializer,
    }

    def _get_queryset(self, request, base_filter=False, with_dropped=False):
        queryset = Employee.objects.all()

        login = login_utils.get_login(request.user)

        organization_filter = {'id': None, 'with_dropped': False}
        if (login.role == Login.CONTROLLER) or (login.role == Login.REGISTRATOR):
            organization_filter.update(id=login.organization_id)
            if with_dropped:
                organization_filter.update(with_dropped=True)
        elif login.role == Login.ADMIN:
            if not with_dropped:
                queryset = queryset.filter(dropped_at=None)
            organization_filter.update(id=request_utils.get_request_param(
                request, 'organization', True, base_filter=base_filter))

        if not base_filter:
            name_filter = request_utils.get_request_param(request, 'name')
            if name_filter is not None:
                queryset = queryset.annotate(
                    full_name=Concat('last_name', Value(
                        ' '), 'first_name', Value(' '), 'patronymic'),
                ).filter(Q(full_name__icontains=name_filter)
                         | Q(last_name__icontains=name_filter)
                         | Q(first_name__icontains=name_filter)
                         | Q(patronymic__icontains=name_filter))

        department_filter = request_utils.get_request_param(
            request, 'department', True, base_filter=base_filter)
        if (department_filter is not None):
            queryset = queryset.filter(
                id__in=Employee2Department.objects.filter(
                    department_id=department_filter).values_list('employee', flat=True))

        if organization_filter.get('id') is not None:
            employee_id_list = queryset.values_list('id', flat=True)
            filter_props = {
                'organization_id': organization_filter.get('id'),
                'employee_id__in': employee_id_list
            }
            if not organization_filter.get('with_dropped'):
                filter_props.update(dropped_at=None)

            queryset = queryset.filter(id__in=Employee2Organization.objects.filter(**filter_props)
                                       .values_list('employee', flat=True))

        return queryset

    @login_utils.login_check_decorator()
    def list(self, request):
        queryset = self._get_queryset(request)

        result = self._list_data(request, queryset)

        return request_utils.response(result)

    @login_utils.login_check_decorator()
    def retrieve(self, request, pk):
        result = self._retrieve_data(request, pk)

        login = login_utils.get_login(request.user)
        if (login.role == Login.CONTROLLER) or (login.role == Login.REGISTRATOR):
            entity = result.get('data')
            if entity.get('dropped_at') is None:
                dropped_at = Employee2Organization.objects.get(
                    employee=pk, organization=login.organization).dropped_at
                if not (dropped_at is None):
                    entity.update(dropped_at=dropped_at.isoformat())
                    result.update(data=entity)

            result.update({'departments_count': Employee2Department.objects.filter(
                employee_id=pk).filter(department__organization_id=login.organization_id).count()})
            if 'full' in request.GET:
                organization = OrganizationSerializers.ModelSerializer(
                    login.organization).data

                result.update({'organization': organization})

        if 'photo' in request.GET:
            pass

        return request_utils.response(result)

    @login_utils.login_check_decorator(Login.REGISTRATOR, Login.ADMIN)
    def partial_update(self, request, pk=None):
        login = login_utils.get_login(request.user)
        delete_restore_mode = ('delete' in request.data) or (
            'restore' in request.data)

        entity: Employee = get_object_or_404(
            self._get_queryset(request, with_dropped=delete_restore_mode), pk=pk)

        result = None
        if delete_restore_mode:
            if login.role == Login.ADMIN:
                result = self._delete_or_restore(request, entity)
            elif login.role == Login.REGISTRATOR:
                relations = Employee2Organization.objects.filter(organization=login.organization,
                                                                 employee=entity)
                if relations.exists():
                    delete_or_restore_result = self._delete_or_restore(
                        request, entity=relations.first(), return_entity=entity)
                    if delete_or_restore_result.data.get('success'):
                        result = self._response4update_n_create(data=entity)
                    else:
                        result = delete_or_restore_result
        else:
            serializer_class = self.get_serializer_class()
            serializer = serializer_class(data=request.data)
            result = None
            login = login_utils.get_login(request.user)
            if serializer.is_valid():
                data = serializer.data
                entity.last_name = data.get('last_name', entity.last_name)
                entity.first_name = data.get(
                    'first_name', entity.first_name)
                entity.patronymic = data.get(
                    'patronymic', entity.patronymic)
                entity.save()

                result = self._response4update_n_create(data=entity)

        return result

    @login_utils.login_check_decorator(Login.REGISTRATOR, Login.ADMIN)
    def create(self, request):
        serializer_class = self.get_serializer_class()
        serializer = serializer_class(data=request.data)
        result = None

        login = login_utils.get_login(request.user)
        if serializer.is_valid():
            employee = Employee(**serializer.data)
            employee.save()

            organization = None
            if login.role == Login.REGISTRATOR:
                organization = login.organization_id
            elif login.role == Login.ADMIN:
                organization = request_utils.get_request_param(
                    request, 'organization', is_int=True)

            if organization is not None:
                Employee2Organization.objects.create(
                    **{'organization_id': organization, 'employee_id': employee.id})

            result = self._response4update_n_create(
                data=employee, code=status.HTTP_201_CREATED)
        else:
            result = self._response4update_n_create(
                message=self._get_validation_error_msg(serializer.errors, Employee))

        return result


class _UserViewSet(_AbstractViewSet):
    _serializer_classes = {
        'list': LoginSerializer.FullSerializer,
        'retrieve': LoginSerializer.FullSerializer,
        'create': LoginSerializer.CreateSerializer,
        'partial_update': LoginSerializer.UpdateSerializer,
    }

    def _user_role(self, request):
        return Login.REGISTRATOR if (login_utils.get_login(request.user).role == Login.ADMIN) \
            else Login.CONTROLLER

    def _get_queryset(self, request, base_filter=False, with_dropped=False):
        queryset = Login.objects.filter(
            role=self._user_role(request))
        if not with_dropped:
            queryset = queryset.filter(dropped_at=None)

        if not base_filter:
            name_filter = request_utils.get_request_param(request, 'name')
            if name_filter is not None:
                users_ids = set(map(lambda i: UserSerializer(i).data.get('id'), User.objects.annotate(
                    full_name_1=Concat('last_name', Value(' '), 'first_name'),
                    full_name_2=Concat('first_name', Value(' '), 'last_name'),
                ).filter(Q(full_name_1__icontains=name_filter) | Q(full_name_2__icontains=name_filter)
                         | Q(last_name__icontains=name_filter) | Q(first_name__icontains=name_filter))))
                queryset = queryset.filter(user_id__in=users_ids)

        login = login_utils.get_login(request.user)
        if login.role == Login.REGISTRATOR:
            queryset = queryset.filter(organization__id=login.organization_id)

        organization_filter = request_utils.get_request_param(
            request, 'organization', True, base_filter=base_filter)
        if organization_filter is not None:
            queryset = queryset.filter(organization__id=organization_filter)

        return queryset

    @login_utils.login_check_decorator(Login.REGISTRATOR, Login.ADMIN)
    def list(self, request):
        queryset = self._get_queryset(request)

        result = self._list_data(request, queryset)

        if 'full' in request.GET:
            organizations_ids = set(
                map(lambda d: d.get('organization'), result.get('data')))

            result.update(
                {'organizations': utils.get_organizations_by_id(organizations_ids)})

        return request_utils.response(result)

    def _retrieve_user(self, request, pk=None):
        result = self._retrieve_data(
            request=request, pk=pk, queryset=self._get_queryset(request))
        if 'full' in request.GET:
            result.update({'organization': OrganizationSerializers.ModelSerializer(
                Organization.objects.get(id=result.get('data').get('organization'))).data})

        return request_utils.response(result)

    def _create(self, request):
        serializer_class = self.get_serializer_class()
        serializer = serializer_class(data=request.data)
        result = None

        if serializer.is_valid():
            current_user = login_utils.get_login(request.user)
            organization_id = None
            if current_user.role == Login.REGISTRATOR:
                organization_id = current_user.organization_id
            elif current_user.role == Login.ADMIN:
                organization_id = int(request.data.get('organization'))

            user_data = User(**serializer.data)
            if user_data.username and user_data.password:
                user = User.objects.create_user(
                    username=user_data.username, password=user_data.password)
                if (user_data.last_name):
                    user.last_name = user_data.last_name
                if (user_data.first_name):
                    user.first_name = user_data.first_name
                user.save()

                login = Login.objects.get(user=user)
                login.organization = Organization.objects.get(
                    id=organization_id)
                login.role = self._user_role(request)
                login.save()
                result = self._response4update_n_create(
                    data=login, code=status.HTTP_201_CREATED)
            else:
                result = self._response4update_n_create(
                    message='Name is empty')
        else:
            result = self._response4update_n_create(
                message=self._get_validation_error_msg(serializer.errors, User, True))

        return result

    def _partial_update(self, request, pk=None):
        login = get_object_or_404(Login.objects.all(), pk=pk)
        user = login.user

        serializer_class = self.get_serializer_class()
        serializer = serializer_class(request.data)
        update = serializer.data
        if update.get('first_name', '') != '':
            user.first_name = update.get('first_name')
        if update.get('last_name', '') != '':
            user.last_name = update.get('last_name')
        # it is for mysql-connector-python
        user.is_superuser = False
        user.is_staff = False

        user.save()
        result = self._response4update_n_create(data=login)

        return result


class UserViewSet(_UserViewSet):
    @login_utils.login_check_decorator(Login.REGISTRATOR, Login.ADMIN)
    def retrieve(self, request, pk=None):
        return self._retrieve_user(request, pk=pk)


class RegistratorViewSet(_UserViewSet):
    @login_utils.login_check_decorator(Login.ADMIN)
    def create(self, request):
        return self._create(request)

    @login_utils.login_check_decorator(Login.ADMIN)
    def retrieve(self, request, pk=None):
        return self._retrieve_user(request, pk=pk)

    @login_utils.login_check_decorator(Login.ADMIN)
    def partial_update(self, request, pk=None):
        return self._partial_update(request, pk)


class ControllerViewSet(_UserViewSet):
    @login_utils.login_check_decorator(Login.REGISTRATOR)
    def create(self, request):
        return self._create(request)

    @login_utils.login_check_decorator(Login.REGISTRATOR)
    def retrieve(self, request, pk=None):
        return self._retrieve_user(request, pk)

    @login_utils.login_check_decorator(Login.REGISTRATOR)
    def partial_update(self, request, pk=None):
        return self._partial_update(request, pk)


class DeviceViewSet(_AbstractViewSet):
    _serializer_classes = {
        'list': DeviceSerializers.ModelSerializer,
        'retrieve': DeviceSerializers.ModelSerializer,
        'create': DeviceSerializers.CreateSerializer,
        'partial_update': DeviceSerializers.UpdateSerializer,
    }

    def _get_queryset(self, request, base_filter=False, with_dropped=False):
        queryset = Device.objects.all()

        login = login_utils.get_login(request.user)

        organization_filter = {'id': None, 'with_dropped': False}
        if (login.role == Login.CONTROLLER) or (login.role == Login.REGISTRATOR):
            organization_filter.update(id=login.organization_id)
            if with_dropped:
                organization_filter.update(with_dropped=True)
        elif login.role == Login.ADMIN:
            if not with_dropped:
                queryset = queryset.filter(dropped_at=None)
            organization_filter.update(id=request_utils.get_request_param(
                request, 'organization', True, base_filter=base_filter))

        if not base_filter:
            name_filter = request_utils.get_request_param(request, 'name')
            if name_filter is not None:
                queryset = queryset.filter(
                    Q(name__icontains=name_filter) | Q(mqtt__icontains=name_filter))
        device_group_filter = request_utils.get_request_param(
            request, 'deviceGroup', True, base_filter=base_filter)
        if device_group_filter is not None:
            queryset = queryset.filter(device_group_id=device_group_filter)

        if organization_filter.get('id') is not None:
            device_id_list = queryset.values_list('id', flat=True)
            filter_props = {
                'organization_id': organization_filter.get('id'),
                'device_id__in': device_id_list
            }
            if not organization_filter.get('with_dropped'):
                filter_props.update(dropped_at=None)

            queryset = queryset.filter(id__in=Device2Organization.objects.filter(**filter_props)
                                       .values_list('device_id', flat=True))

        return queryset

    @login_utils.login_check_decorator()
    def list(self, request):
        queryset = self._get_queryset(request)

        result = self._list_data(request, queryset)

        return request_utils.response(result)

    @login_utils.login_check_decorator()
    def retrieve(self, request, pk=None):
        result = self._retrieve_data(request, pk)

        login = login_utils.get_login(request.user)

        if ('full' in request.GET) and ((login.role == Login.CONTROLLER) or (login.role == Login.REGISTRATOR)):
            entity = result.get('data')
            if entity.get('dropped_at') is None:
                dropped_at = Device2Organization.objects.get(
                    device=pk, organization=login.organization).dropped_at
                if not (dropped_at is None):
                    entity.update(dropped_at=dropped_at.isoformat())
                    result.update(data=entity)

            result.update({'organization': OrganizationSerializers.ModelSerializer(
                Organization.objects.get(id=login.organization_id)).data})

        return request_utils.response(result)

    @login_utils.login_check_decorator(Login.REGISTRATOR, Login.ADMIN)
    def create(self, request):
        login = login_utils.get_login(request.user)
        serializer_class = self.get_serializer_class()
        device_data = request.data
        device_data.device_group = request_utils.get_request_param(
            request, 'deviceGroup', is_int=True)
        serializer = serializer_class(data=device_data)
        result = None
        if serializer.is_valid():
            device = Device(**serializer.data)
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
            serializer_class = self.get_serializer_class()

            device_data = QueryDict('', mutable=True)
            device_data.update(request.data)
            device_data.update({'mqtt': entity.mqtt})
            device_data.update({'device_type': entity.device_type})

            valid_result = self._validate_on_update(
                pk, serializer_class, Device, device_data)
            serializer = valid_result.get('serializer')
            update = valid_result.get('update')
            if update is not None:
                entity.name = update.name
                entity.description = update.description
                entity.config = update.config
                entity.timezone = update.timezone
                entity.save()
                result = self._response4update_n_create(data=entity)
            else:
                result = self._response4update_n_create(
                    message=self._get_validation_error_msg(serializer.errors, Device))

        return result

    def _alternative_valid(self, pk, data, errors, extra):
        return (len(errors.keys()) == 1) and errors.keys().__contains__('mqtt')\
            and (errors.get('mqtt')[0].code == 'unique')\
            and not Device.objects.filter(mqtt=data.get('mqtt')).filter(~Q(id=pk)).exists()


class DeviceGroupViewSet(_AbstractViewSet):
    _serializer_classes = {
        'list': DeviceGroupSerializers.ModelSerializer,
        'retrieve': DeviceGroupSerializers.ModelSerializer,
        'create': DeviceGroupSerializers.CreateSerializer,
        'partial_update': DeviceGroupSerializers.CreateSerializer,
    }

    def _get_queryset(self, request, base_filter=False, with_dropped=False):
        queryset = DeviceGroup.objects.all()
        if not with_dropped:
            queryset = queryset.filter(dropped_at=None)

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
            queryset = queryset.filter(id__in=DeviceGroup2Organization.objects.filter(
                device_group_id__in=group_id_list).filter(
                organization_id=organization_filter).values_list('device_group_id', flat=True))

        return queryset

    @login_utils.login_check_decorator()
    def list(self, request):
        queryset = self._get_queryset(request)

        result = self._list_data(request, queryset)

        return request_utils.response(result)

    @login_utils.login_check_decorator()
    def retrieve(self, request, pk=None):
        result = self._retrieve_data(request, pk)

        return request_utils.response(result)

    @login_utils.login_check_decorator(Login.REGISTRATOR, Login.ADMIN)
    def create(self, request):
        serializer_class = self.get_serializer_class()
        serializer = serializer_class(data=request.data)
        result = None
        if serializer.is_valid():
            group = DeviceGroup(**serializer.data)
            group.save()

            login = login_utils.get_login(request.user)

            organization = None
            if login.role == Login.REGISTRATOR:
                organization = login.organization_id
            elif login.role == Login.ADMIN:
                organization = request_utils.get_request_param(
                    request, 'organization', is_int=True)

            if organization is not None:
                DeviceGroup2Organization.objects.create(
                    **{'organization_id': organization,
                       'device_group_id': group.id})

            result = self._response4update_n_create(
                data=group, code=status.HTTP_201_CREATED)
        else:
            result = self._response4update_n_create(
                message=self._get_validation_error_msg(serializer.errors, DeviceGroup))

        return result

    @login_utils.login_check_decorator(Login.REGISTRATOR, Login.ADMIN)
    def partial_update(self, request, pk=None):
        login = login_utils.get_login(request.user)
        delete_restore_mode = (login.role == Login.ADMIN) \
            and (('delete' in request.data) or ('restore' in request.data))

        entity: DeviceGroup = get_object_or_404(
            self._get_queryset(request, with_dropped=delete_restore_mode), pk=pk)

        result = None
        if delete_restore_mode:
            result = self._delete_or_restore(request, entity)
        else:
            serializer_class = self.get_serializer_class()
            result = None

            valid_result = self._validate_on_update(
                pk, serializer_class, DeviceGroup, request.data)
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
                    message=self._get_validation_error_msg(serializer.errors, DeviceGroup))

        return result

    def _alternative_valid(self, pk, data, errors, extra):
        return (len(errors.keys()) == 1) and errors.keys().__contains__('name') and (errors.get('name')[0].code == 'unique') and not DeviceGroup.objects.filter(name=data.get('name')).filter(~Q(id=pk)).exists()


@api_view(['GET'])
def get_current_user(request):
    user = request.user

    response = None
    if (user.is_authenticated):
        response = LoginSerializer.FullSerializer(
            Login.objects.get(user=user)).data
    else:
        response = None

    return Response({'data': response})


@api_view(['GET'])
@login_utils.login_check_decorator(Login.ADMIN)
def get_counts(request):
    return Response({'organizations': Organization.objects.filter(dropped_at=None).count(),
                     'devices': Device.objects.filter(dropped_at=None).count(),
                     'deviceGroups': DeviceGroup.objects.filter(dropped_at=None).count(),
                     'employees': Employee.objects.filter(dropped_at=None).count()})


@api_view(['GET'])
@login_utils.login_check_decorator(Login.CONTROLLER, Login.ADMIN)
def get_report_file(request):
    """report file"""
    return report_utils.get_report_file(request)


@api_view(['GET'])
@login_utils.login_check_decorator(Login.CONTROLLER, Login.ADMIN)
def get_report(request):
    """return report"""
    return Response(vars(report_utils.get_report(request)))


@api_view(['POST'])
@login_utils.login_check_decorator(Login.REGISTRATOR, Login.ADMIN)
def add_relation(request, master_name, master_id, slave_name):
    """add relations"""
    return Response({'data': vars(relation_utils.add_relation(request,
                                                              master_name,
                                                              master_id,
                                                              slave_name))})


@api_view(['POST'])
@login_utils.login_check_decorator(Login.REGISTRATOR, Login.ADMIN)
def remove_relation(request, master_name, master_id, slave_name):
    """remove relations"""
    return Response({'data': vars(relation_utils.remove_relation(request,
                                                                 master_name,
                                                                 master_id,
                                                                 slave_name))})


@api_view(['GET'])
@login_utils.login_check_decorator(Login.REGISTRATOR, Login.ADMIN)
def get_non_related(request, master_name, master_id, slave_name):
    """get non-related entries"""
    return Response({'data': relation_utils.get_non_related(request,
                                                            master_name,
                                                            master_id,
                                                            slave_name)})


@api_view(['POST'])
@login_utils.login_check_decorator(Login.REGISTRATOR, Login.ADMIN)
def registrate_biometry(request, employee_id):
    """registrate biometry to employee"""
    employee = get_object_or_404(Employee.objects.all(), pk=employee_id)
    mqtt_id = request.POST.get('mqtt')
    biometry_data = request.POST.get('biometryData')
    biometry_type = BiometryType(request.POST.get('type'))

    result = registrate_biometry_by_device(
        employee, mqtt_id, biometry_data, biometry_type)

    return Response(vars(result))
