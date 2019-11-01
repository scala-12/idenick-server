import base64
import io
import json
import socket
import struct
from abc import abstractmethod
from datetime import datetime, timedelta
from enum import Enum
from functools import wraps
from threading import Thread
from time import sleep

import paho.mqtt.client as mqtt
import xlsxwriter
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.models import User
from django.db.models.expressions import Value
from django.db.models.functions.text import Concat
from django.db.models.query_utils import Q
from django.http import FileResponse
from django.http.request import QueryDict
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from rest_framework import status, viewsets
from rest_framework.decorators import api_view
from rest_framework.request import Request
from rest_framework.response import Response

import idenick_rest_api_v0
from idenick_app.models import (Department, Device, Device2DeviceGroup,
                                Device2Organization, DeviceGroup,
                                DeviceGroup2Organization, Employee,
                                Employee2Department, Employee2Organization,
                                EmployeeRequest, Login, Organization)
from idenick_rest_api_v0.serializers import (DepartmentSerializers,
                                             DeviceGroupSerializers,
                                             DeviceSerializers,
                                             EmployeeRequestSerializer,
                                             EmployeeSerializers,
                                             LoginSerializer,
                                             OrganizationSerializers,
                                             UserSerializer)


class _LoginMethods:
    @staticmethod
    def login_check_decorator(*roles):
        def decorator(view_func):
            @wraps(view_func)
            def wrapped(*args, **kwargs):
                args_list = list(args)
                request = None
                if isinstance(args_list[0], Request):
                    request = args_list[0]
                elif isinstance(args_list[1], Request):
                    request = args_list[1]

                if _LoginMethods._check_role(request, roles):
                    return view_func(*args, **kwargs)
                else:
                    return _LoginMethods._login_error_response()

            return wrapped

        return decorator

    @staticmethod
    def _login_error_response():
        return _AbstractViewSet._response(None, {'redirect2Login': True},
                                          status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @staticmethod
    def _check_role(request, roles):
        has_role = False
        if request.user.is_authenticated:
            login = _LoginMethods.get_login(request.user)
            if login is not None:
                roles_list = list(roles)
                if len(roles_list) == 0:
                    has_role = True
                else:
                    i = 0
                    while ((i < len(roles_list)) and not(has_role)):
                        if roles_list[i] == login.role:
                            has_role = True
                        else:
                            i += 1
        return has_role

    @staticmethod
    def get_login(user):
        result = None
        if user.is_authenticated:
            login = Login.objects.filter(user=user)
            if login.exists():
                result = login.first()

        return result

    @staticmethod
    def has_login_check(user):
        login = _LoginMethods.get_login(user)
        return login is not None


def _get_request_param(request, name, is_int=False, default=None, base_filter=False):
    param = request.GET.get(('_' if base_filter else '') + name, default)

    result = None
    if param is not None:
        if param != '':
            if is_int:
                try:
                    result = int(param)
                except ValueError:
                    pass
            else:
                result = param
    elif not base_filter:
        result = _get_request_param(
            request, name, is_int=is_int, default=default, base_filter=True)

    return result


class ErrorMessage(Enum):
    UNIQUE_DEPARTMENT_NAME = 'Подразделение с таким названием уже существует'


class _AbstractViewSet(viewsets.ViewSet):
    _serializer_classes = None

    def _get_queryset(self, request, base_filter=False):
        pass

    def _response(self, data, status_value=status.HTTP_200_OK):
        return Response(
            data,
            headers={'Access-Control-Allow-Origin': '*',
                     'Content-Type': 'application/json'},
            status=status_value)

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
        return self._serializer_classes[self.action]

    def _list_data(self, request, queryset=None):
        _queryset = self._get_queryset(request) if (
            queryset is None) else queryset

        page = _get_request_param(request, 'page', True)
        per_page = _get_request_param(request, 'perPage', True)

        if (page is not None) and (per_page is not None):
            offset = page * per_page
            limit = offset + per_page
            _queryset = _queryset[offset:limit]

        organization = None
        login = _LoginMethods.get_login(request.user)
        if ((login.role == Login.CONTROLLER) or (login.role == Login.REGISTRATOR)):
            organization = login.organization_id

        serializer = self.get_serializer_class()(_queryset, many=True, context={
            'organization': organization})

        return {'data': serializer.data, 'count': self._get_queryset(request, True).count()}

    def _retrieve(self, request, pk=None, queryset=None):
        return self._response(self._retrieve_data(request, pk, queryset))

    def _retrieve_data(self, request, pk, queryset=None):
        _queryset = self._get_queryset(request) if (
            queryset is None) else queryset
        entity = get_object_or_404(_queryset, pk=pk)

        organization = None
        login = _LoginMethods.get_login(request.user)
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


class OrganizationViewSet(_AbstractViewSet):
    _serializer_classes = {
        'list': OrganizationSerializers.ModelSerializer,
        'retrieve': OrganizationSerializers.ModelSerializer,
        'create': OrganizationSerializers.CreateSerializer,
        'partial_update': OrganizationSerializers.CreateSerializer,
    }

    def _get_queryset(self, request, base_filter=False):
        queryset = Organization.objects.filter(dropped_at=None)

        if not base_filter:
            name_filter = _get_request_param(request, 'name')
            if name_filter is not None:
                queryset = queryset.filter(name__icontains=name_filter)

        device_group_filter = _get_request_param(
            request, 'deviceGroup', True, base_filter=base_filter)
        if device_group_filter is not None:
            organization_id_list = queryset.values_list('id', flat=True)
            queryset = queryset.filter(id__in=DeviceGroup2Organization.objects.filter(
                organization_id__in=organization_id_list).filter(
                device_group_id=device_group_filter).values_list('organization', flat=True))
        device_filter = _get_request_param(
            request, 'device', True, base_filter=base_filter)
        if device_filter is not None:
            organization_id_list = queryset.values_list('id', flat=True)
            queryset = queryset.filter(id__in=Device2Organization.objects.filter(
                organization_id__in=organization_id_list).filter(
                device_id=device_filter).values_list('organization', flat=True))
        employee_filter = _get_request_param(
            request, 'employee', True, base_filter=base_filter)
        if employee_filter is not None:
            organization_id_list = queryset.values_list('id', flat=True)
            queryset = queryset.filter(id__in=Employee2Organization.objects.filter(
                organization_id__in=organization_id_list).filter(
                employee_id=employee_filter).values_list('organization', flat=True))

        return queryset

    @_LoginMethods.login_check_decorator(Login.ADMIN)
    def list(self, request):
        result = self._list_data(request)

        return self._response(result)

    @_LoginMethods.login_check_decorator()
    def retrieve(self, request, pk=None):
        return self._retrieve(request, pk)

    @_LoginMethods.login_check_decorator(Login.ADMIN)
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

    @_LoginMethods.login_check_decorator(Login.ADMIN)
    def partial_update(self, request, pk=None):
        organization = get_object_or_404(Organization.objects.all(), pk=pk)

        serializer_class = self.get_serializer_class()
        result = None

        valid_result = self._validate_on_update(
            pk, serializer_class, Organization, request.data)
        serializer = valid_result.get('serializer')
        update = valid_result.get('update')
        if update is not None:
            organization.name = update.name
            organization.address = update.address
            organization.phone = update.phone
            organization.save()
            result = self._response4update_n_create(data=organization)
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

    def _get_queryset(self, request, base_filter=False):
        login = _LoginMethods.get_login(request.user)
        queryset = Department.objects.filter(dropped_at=None)
        role = login.role
        if (role == Login.CONTROLLER) or (role == Login.REGISTRATOR):
            queryset = queryset.filter(
                organization_id=login.organization_id)

        if not base_filter:
            name_filter = _get_request_param(request, 'name')
            if name_filter is not None:
                queryset = queryset.filter(name__icontains=name_filter)

        employee_filter = _get_request_param(
            request, 'employee', True, base_filter=base_filter)
        if employee_filter is not None:
            queryset = queryset.filter(id__in=Employee2Department.objects.filter(
                employee_id=employee_filter).values_list('department_id', flat=True))

        return queryset

    @_LoginMethods.login_check_decorator(Login.REGISTRATOR, Login.CONTROLLER)
    def list(self, request):
        queryset = self._get_queryset(request)

        result = self._list_data(request, queryset)

        if 'full' in request.GET:
            organizations_ids = set(
                map(lambda d: d.get('organization'), result.get('data')))
            result.update(
                {'organizations': _get_organizations_by_id(organizations_ids)})

        return self._response(result)

    @_LoginMethods.login_check_decorator(Login.REGISTRATOR, Login.CONTROLLER)
    def retrieve(self, request, pk=None):
        result = self._retrieve_data(request, pk)

        if 'full' in request.GET:
            result.update({'organization': OrganizationSerializers.ModelSerializer(
                Organization.objects.get(id=result.get('data',).get('organization'))).data})

        return self._response(result)

    @_LoginMethods.login_check_decorator(Login.REGISTRATOR)
    def create(self, request):
        serializer_class = self.get_serializer_class()

        department_data = QueryDict('', mutable=True)
        department_data.update(request.data)
        department_data.update(
            {'organization': _LoginMethods.get_login(request.user).organization_id})
        serializer = serializer_class(data=department_data)
        result = None

        if serializer.is_valid():
            department = Department(**serializer.data)
            if Department.objects.filter(name=department.name).exists():
                result = self._response4update_n_create(
                    message=ErrorMessage.UNIQUE_DEPARTMENT_NAME.value)
            else:
                department.save()
                result = self._response4update_n_create(
                    data=department, code=status.HTTP_201_CREATED)
        else:
            result = self._response4update_n_create(
                message=self._get_validation_error_msg(serializer.errors, Department))

        return result

    @_LoginMethods.login_check_decorator(Login.REGISTRATOR)
    def partial_update(self, request, pk=None):
        department = get_object_or_404(self._get_queryset(request), pk=pk)

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
            department.name = update.name
            department.rights = update.rights
            department.address = update.address
            department.description = update.description
            department.save()
            result = self._response4update_n_create(data=department)
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

    def _get_queryset(self, request, base_filter=False):
        queryset = Employee.objects.filter(dropped_at=None)

        login = _LoginMethods.get_login(request.user)
        if not base_filter:
            name_filter = _get_request_param(request, 'name')
            if name_filter is not None:
                queryset = queryset.annotate(
                    full_name=Concat('last_name', Value(
                        ' '), 'first_name', Value(' '), 'patronymic'),
                ).filter(Q(full_name__icontains=name_filter)
                         | Q(last_name__icontains=name_filter)
                         | Q(first_name__icontains=name_filter)
                         | Q(patronymic__icontains=name_filter))

        department_filter = _get_request_param(
            request, 'department', True, base_filter=base_filter)
        if (department_filter is not None):
            queryset = queryset.filter(
                id__in=Employee2Department.objects.filter(
                    department_id=department_filter).values_list('employee', flat=True))

        organization_filter = None
        if (login.role == Login.CONTROLLER) or (login.role == Login.REGISTRATOR):
            organization_filter = login.organization_id
        elif login.role == Login.ADMIN:
            organization_filter = _get_request_param(
                request, 'organization', True, base_filter=base_filter)

        if organization_filter is not None:
            employee_id_list = queryset.values_list('id', flat=True)
            queryset = queryset.filter(id__in=Employee2Organization.objects.filter(
                organization_id=organization_filter).filter(
                employee_id__in=employee_id_list).values_list('employee', flat=True))

        return queryset

    @_LoginMethods.login_check_decorator()
    def list(self, request):
        queryset = self._get_queryset(request)

        result = self._list_data(request, queryset)

        return self._response(result)

    @_LoginMethods.login_check_decorator()
    def retrieve(self, request, pk):
        result = self._retrieve_data(
            request, pk, self._get_queryset(request))

        login = _LoginMethods.get_login(request.user)
        if (login.role == Login.CONTROLLER) or (login.role == Login.REGISTRATOR):
            result.update({'departments_count': Employee2Department.objects.filter(
                employee_id=pk).filter(department__organization_id=login.organization_id).count()})
            if 'full' in request.GET:
                organization = OrganizationSerializers.ModelSerializer(
                    login.organization).data

                result.update({'organization': organization})

        if 'photo' in request.GET:
            pass

        return self._response(result)

    @_LoginMethods.login_check_decorator(Login.REGISTRATOR, Login.ADMIN)
    def partial_update(self, request, pk=None):
        queryset = self._get_queryset(request)
        employee = get_object_or_404(queryset, pk=pk)

        serializer_class = self.get_serializer_class()
        serializer = serializer_class(data=request.data)
        result = None
        login = _LoginMethods.get_login(request.user)
        if serializer.is_valid():
            data = serializer.data
            employee.last_name = data.get('last_name', employee.last_name)
            employee.first_name = data.get(
                'first_name', employee.first_name)
            employee.patronymic = data.get(
                'patronymic', employee.patronymic)
            employee.save()

            result = self._response4update_n_create(data=employee)

        return result

    @_LoginMethods.login_check_decorator(Login.REGISTRATOR, Login.ADMIN)
    def create(self, request):
        serializer_class = self.get_serializer_class()
        serializer = serializer_class(data=request.data)
        result = None

        login = _LoginMethods.get_login(request.user)
        if serializer.is_valid():
            employee = Employee(**serializer.data)
            employee.save()

            organization = None
            if login.role == Login.REGISTRATOR:
                organization = login.organization_id
            elif login.role == Login.ADMIN:
                organization = _get_request_param(
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
        return Login.REGISTRATOR if (_LoginMethods.get_login(request.user).role == Login.ADMIN) \
            else Login.CONTROLLER

    def _get_queryset(self, request, base_filter=False):
        queryset = Login.objects.filter(
            role=self._user_role(request))

        if not base_filter:
            name_filter = _get_request_param(request, 'name')
            if name_filter is not None:
                users_ids = set(map(lambda i: UserSerializer(i).data.get('id'), User.objects.annotate(
                    full_name_1=Concat('last_name', Value(' '), 'first_name'),
                    full_name_2=Concat('first_name', Value(' '), 'last_name'),
                ).filter(Q(full_name_1__icontains=name_filter) | Q(full_name_2__icontains=name_filter)
                         | Q(last_name__icontains=name_filter) | Q(first_name__icontains=name_filter))))
                queryset = queryset.filter(user_id__in=users_ids)

        login = _LoginMethods.get_login(request.user)
        if login.role == Login.REGISTRATOR:
            queryset = queryset.filter(organization__id=login.organization_id)

        organization_filter = _get_request_param(
            request, 'organization', True, base_filter=base_filter)
        if organization_filter is not None:
            queryset = queryset.filter(organization__id=organization_filter)

        return queryset

    @_LoginMethods.login_check_decorator(Login.REGISTRATOR, Login.ADMIN)
    def list(self, request):
        queryset = self._get_queryset(request)

        result = self._list_data(request, queryset)

        if 'full' in request.GET:
            organizations_ids = set(
                map(lambda d: d.get('organization'), result.get('data')))

            result.update(
                {'organizations': _get_organizations_by_id(organizations_ids)})

        return self._response(result)

    def _retrieve_user(self, request, pk=None):
        result = self._retrieve_data(
            request=request, pk=pk, queryset=self._get_queryset(request))
        if 'full' in request.GET:
            result.update({'organization': OrganizationSerializers.ModelSerializer(
                Organization.objects.get(id=result.get('data').get('organization'))).data})

        return self._response(result)

    def _create(self, request):
        serializer_class = self.get_serializer_class()
        serializer = serializer_class(data=request.data)
        result = None

        if serializer.is_valid():
            current_user = _LoginMethods.get_login(request.user)
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
    @_LoginMethods.login_check_decorator(Login.REGISTRATOR, Login.ADMIN)
    def retrieve(self, request, pk=None):
        return self._retrieve_user(request, pk=pk)


class RegistratorViewSet(_UserViewSet):
    @_LoginMethods.login_check_decorator(Login.ADMIN)
    def create(self, request):
        return self._create(request)

    @_LoginMethods.login_check_decorator(Login.ADMIN)
    def retrieve(self, request, pk=None):
        return self._retrieve_user(request, pk=pk)

    @_LoginMethods.login_check_decorator(Login.ADMIN)
    def partial_update(self, request, pk=None):
        return self._partial_update(request, pk)


class ControllerViewSet(_UserViewSet):
    @_LoginMethods.login_check_decorator(Login.REGISTRATOR)
    def create(self, request):
        return self._create(request)

    @_LoginMethods.login_check_decorator(Login.REGISTRATOR)
    def retrieve(self, request, pk=None):
        return self._retrieve_user(request, pk)

    @_LoginMethods.login_check_decorator(Login.REGISTRATOR)
    def partial_update(self, request, pk=None):
        return self._partial_update(request, pk)


class DeviceViewSet(_AbstractViewSet):
    _serializer_classes = {
        'list': DeviceSerializers.ModelSerializer,
        'retrieve': DeviceSerializers.ModelSerializer,
        'create': DeviceSerializers.CreateSerializer,
        'partial_update': DeviceSerializers.UpdateSerializer,
    }

    def _get_queryset(self, request, base_filter=False):
        login = _LoginMethods.get_login(request.user)

        queryset = Device.objects.filter(dropped_at=None)
        if login.role != Login.ADMIN:
            queryset = queryset.filter(id__in=Device2Organization.objects.filter(
                organization_id=login.organization_id).values_list('device_id', flat=True))

        login = _LoginMethods.get_login(request.user)

        if not base_filter:
            name_filter = _get_request_param(request, 'name')
            if name_filter is not None:
                queryset = queryset.filter(
                    Q(name__icontains=name_filter) | Q(mqtt__icontains=name_filter))
        device_group_filter = _get_request_param(
            request, 'deviceGroup', True, base_filter=base_filter)
        if device_group_filter is not None:
            queryset = queryset \
                .filter(id__in=RelationsUtils.get_relates(Device, 'device_id', Device2DeviceGroup,
                                                          'device_group_id', device_group_filter,
                                                          login).values_list('id', flat=True))
        organization_filter = _get_request_param(
            request, 'organization', True, base_filter=base_filter)
        if organization_filter is not None:
            device_id_list = queryset.values_list('id', flat=True)
            queryset = queryset.filter(id__in=Device2Organization.objects.filter(
                device_id__in=device_id_list).filter(
                organization_id=organization_filter).values_list('device_id', flat=True))

        return queryset

    @_LoginMethods.login_check_decorator()
    def list(self, request):
        queryset = self._get_queryset(request)

        result = self._list_data(request, queryset)

        return self._response(result)

    @_LoginMethods.login_check_decorator()
    def retrieve(self, request, pk=None):
        result = self._retrieve_data(request, pk)

        login = _LoginMethods.get_login(request.user)

        if ('full' in request.GET) and ((login.role == Login.CONTROLLER) or (login.role == Login.REGISTRATOR)):
            result.update({'organization': OrganizationSerializers.ModelSerializer(
                Organization.objects.get(id=login.organization_id)).data})

        return self._response(result)

    @_LoginMethods.login_check_decorator(Login.REGISTRATOR, Login.ADMIN)
    def create(self, request):
        login = _LoginMethods.get_login(request.user)
        serializer_class = self.get_serializer_class()
        serializer = serializer_class(data=request.data)
        result = None
        if serializer.is_valid():
            device = Device(**serializer.data)
            device.save()

            organization = None
            if login.role == Login.REGISTRATOR:
                organization = login.organization_id
            elif login.role == Login.ADMIN:
                organization = _get_request_param(
                    request, 'organization', is_int=True)

            if organization is not None:
                Device2Organization.objects.create(
                    **{'organization_id': organization, 'device_id': device.id})

            device_group = _get_request_param(
                request, 'deviceGroup', is_int=True)
            if device_group is not None:
                Device2DeviceGroup.objects.create(
                    **{'device_group_id': device_group, 'device_id': device.id})

            result = self._response4update_n_create(
                data=device, code=status.HTTP_201_CREATED)
        else:
            result = self._response4update_n_create(
                message=self._get_validation_error_msg(serializer.errors, Device))

        return result

    @_LoginMethods.login_check_decorator(Login.REGISTRATOR, Login.ADMIN)
    def partial_update(self, request, pk=None):
        device = get_object_or_404(self._get_queryset(request), pk=pk)

        serializer_class = self.get_serializer_class()
        result = None

        device_data = QueryDict('', mutable=True)
        device_data.update(request.data)
        device_data.update({'mqtt': device.mqtt})
        device.device_type = 0 if device.device_type is None else device.device_type
        device_data.update({'device_type': device.device_type})

        valid_result = self._validate_on_update(
            pk, serializer_class, Device, device_data)
        serializer = valid_result.get('serializer')
        update = valid_result.get('update')
        if update is not None:
            device.name = update.name
            device.description = update.description
            device.config = update.config
            device.save()
            result = self._response4update_n_create(data=device)
        else:
            result = self._response4update_n_create(
                message=self._get_validation_error_msg(serializer.errors, Device))

        return result

    def _alternative_valid(self, pk, data, errors, extra):
        return (len(errors.keys()) == 1) and errors.keys().__contains__('mqtt') \
            and (errors.get('mqtt')[0].code == 'unique') \
            and not Device.objects.filter(mqtt=data.get('mqtt')).filter(~Q(id=pk)).exists()


class DeviceGroupViewSet(_AbstractViewSet):
    _serializer_classes = {
        'list': DeviceGroupSerializers.ModelSerializer,
        'retrieve': DeviceGroupSerializers.ModelSerializer,
        'create': DeviceGroupSerializers.CreateSerializer,
        'partial_update': DeviceGroupSerializers.CreateSerializer,
    }

    def _get_queryset(self, request, base_filter=False):
        queryset = DeviceGroup.objects.filter(dropped_at=None)

        login = _LoginMethods.get_login(request.user)

        if not base_filter:
            name_filter = _get_request_param(request, 'name')
            if name_filter is not None:
                queryset = queryset.filter(name__icontains=name_filter)

        organization_filter = None
        if (login.role == Login.CONTROLLER) or (login.role == Login.REGISTRATOR):
            organization_filter = login.organization_id
        elif login.role == Login.ADMIN:
            organization_filter = _get_request_param(
                request, 'organization', True, base_filter=base_filter)
        if organization_filter is not None:
            group_id_list = queryset.values_list('id', flat=True)
            queryset = queryset.filter(id__in=DeviceGroup2Organization.objects.filter(
                device_group_id__in=group_id_list).filter(
                organization_id=organization_filter).values_list('device_group_id', flat=True))
        device_filter = _get_request_param(
            request, 'device', True, base_filter=base_filter)
        if device_filter is not None:
            group_id_list = queryset.values_list('id', flat=True)
            queryset = queryset.filter(id__in=Device2DeviceGroup.objects.filter(
                device_group_id__in=group_id_list).filter(
                device_id=device_filter).values_list('device_group_id', flat=True))

        return queryset

    @_LoginMethods.login_check_decorator()
    def list(self, request):
        queryset = self._get_queryset(request)

        result = self._list_data(request, queryset)

        return self._response(result)

    @_LoginMethods.login_check_decorator()
    def retrieve(self, request, pk=None):
        result = self._retrieve_data(request, pk)

        return self._response(result)

    @_LoginMethods.login_check_decorator(Login.REGISTRATOR, Login.ADMIN)
    def create(self, request):
        serializer_class = self.get_serializer_class()
        serializer = serializer_class(data=request.data)
        result = None
        if serializer.is_valid():
            group = DeviceGroup(**serializer.data)
            group.save()

            login = _LoginMethods.get_login(request.user)

            organization = None
            if login.role == Login.REGISTRATOR:
                organization = login.organization_id
            elif login.role == Login.ADMIN:
                organization = _get_request_param(
                    request, 'organization', is_int=True)

            if organization is not None:
                DeviceGroup2Organization.objects.create(
                    **{'organization_id': organization,
                       'device_group_id': group.id})

            device = _get_request_param(
                request, 'device', is_int=True)
            if device is not None:
                Device2DeviceGroup.objects.create(
                    **{'device_id': device,
                       'device_group_id': group.id})

            result = self._response4update_n_create(
                data=group, code=status.HTTP_201_CREATED)
        else:
            result = self._response4update_n_create(
                message=self._get_validation_error_msg(serializer.errors, DeviceGroup))

        return result

    @_LoginMethods.login_check_decorator(Login.REGISTRATOR, Login.ADMIN)
    def partial_update(self, request, pk=None):
        group = get_object_or_404(self._get_queryset(request), pk=pk)

        serializer_class = self.get_serializer_class()
        result = None

        valid_result = self._validate_on_update(
            pk, serializer_class, DeviceGroup, request.data)
        serializer = valid_result.get('serializer')
        update = valid_result.get('update')
        if update is not None:
            group.name = update.name
            group.description = update.description
            group.rights = update.rights
            group.save()
            result = self._response4update_n_create(data=group)
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
@_LoginMethods.login_check_decorator(Login.ADMIN)
def get_counts(request):
    return Response({'organizations': Organization.objects.count(),
                     'devices': Device.objects.count(),
                     'deviceGroups': DeviceGroup.objects.count(),
                     'employees': Employee.objects.count()})


class ReportTools:
    class _ReportType(Enum):
        EMPLOYEE = 'EMPLOYEE'
        DEPARTMENT = 'DEPARTMENT'
        ORGANIZATION = 'ORGANIZATION'
        DEVICE = 'DEVICE'
        DEVICE_GROUP = 'DEVICE_GROUP'
        ALL = 'ALL'

    @staticmethod
    def _get_report(request):
        login = _LoginMethods.get_login(request.user)

        entity_id = _get_request_param(request, 'id', True)
        entity_type = ReportTools._ReportType(
            _get_request_param(request, 'type'))

        page = _get_request_param(request, 'from', True)
        page_count = _get_request_param(request, 'count', True, 1)
        perPage = _get_request_param(request, 'perPage', True)

        start_date = None
        start_time = _get_request_param(request, 'start')
        if start_time is not None:
            start_date = datetime.strptime(start_time, "%Y%m%d")

        end_date = None
        end_time = _get_request_param(request, 'end')
        if end_time is not None:
            end_date = datetime.strptime(
                end_time, "%Y%m%d") + timedelta(days=1, microseconds=-1)

        report_queryset = EmployeeRequest.objects.all()
        if login.role == Login.CONTROLLER:
            organization_filter = login.organization.id
        name = None
        if (entity_id is not None):
            if entity_type == ReportTools._ReportType.EMPLOYEE:
                name = 'employee '

                if (organization_filter is None) or Employee2Organization.objects.filter(employee_id=entity_id).filter(organization_id=organization_filter).exists():
                    report_queryset = report_queryset.filter(
                        employee_id=entity_id)
                else:
                    report_queryset = EmployeeRequest.objects.none()
            elif entity_type == ReportTools._ReportType.DEPARTMENT:
                name = 'department '

                employees = Employee.objects.filter(id__in=Employee2Department.objects.filter(
                    department_id=entity_id).values_list('employee_id', flat=True))
                report_queryset = report_queryset.filter(
                    employee__in=employees)
            elif entity_type == ReportTools._ReportType.ORGANIZATION:
                name = 'organization '

                if (organization_filter is None) or (organization_filter == entity_id):
                    employees = Employee2Organization.objects.filter(
                        organization_id=entity_id).values_list('employee_id', flat=True)
                    devices_of_organization = Device2Organization.objects.filter(
                        organization_id=entity_id).values_list('device_id', flat=True)
                    devices_of_device_groups = Device2DeviceGroup.objects.filter(device_group__in=DeviceGroup2Organization.objects.filter(
                        organization_id=entity_id).values_list('device_group_id', flat=True))

                    devices = devices_of_organization.union(
                        devices_of_device_groups)

                    reports = EmployeeRequest.objects.filter(
                        employee_id__in=employees).values_list('id', flat=True).union(
                        EmployeeRequest.objects.filter(
                            device_id__in=devices).values_list('id', flat=True)
                    )

                    report_queryset = report_queryset.filter(id__in=reports)
                else:
                    report_queryset = EmployeeRequest.objects.none()

            elif entity_type == ReportTools._ReportType.DEVICE:
                name = 'device '

                if (organization_filter is None) or Device2Organization.objects.filter(device_id=entity_id).filter(organization_id=organization_filter).exists():
                    report_queryset = report_queryset.filter(
                        device_id=entity_id)
                else:
                    report_queryset = EmployeeRequest.objects.none()
            elif entity_type == ReportTools._ReportType.DEVICE_GROUP:
                name = 'device_groups '

                if (organization_filter is None) or DeviceGroup2Organization.objects.filter(device_group_id=entity_id).filter(organization_id=organization_filter).exists():
                    devices = Device2DeviceGroup.objects.filter(
                        device_group_id=entity_id).values_list('device_id', flat=True)

                    if (organization_filter is not None):
                        devices_of_organization = Device2Organization.objects.filter(
                            organization_id=organization_filter).values_list('device_id', flat=True)

                        devices = set(devices).intersection(
                            set(devices_of_organization))

                    report_queryset = report_queryset.filter(
                        device_id__in=devices)
                else:
                    report_queryset = EmployeeRequest.objects.none()

            name += str(entity_id)
        else:
            name = 'full'

        report_queryset = report_queryset.order_by('-moment')

        if start_date is not None:
            report_queryset = report_queryset.filter(moment__gte=start_date)
        if end_date is not None:
            report_queryset = report_queryset.filter(moment__lte=end_date)

        paginated_report_queryset = None
        if (page is None) or (perPage is None):
            paginated_report_queryset = report_queryset
        else:
            offset = int(page) * int(perPage)
            limit = offset + int(perPage) * int(page_count)
            paginated_report_queryset = report_queryset[offset:limit]

        result = {'queryset': paginated_report_queryset, 'name': name}
        result.update(count=report_queryset.count())

        return result

    @staticmethod
    @api_view(['GET'])
    @_LoginMethods.login_check_decorator(Login.CONTROLLER, Login.ADMIN)
    def get_report_file(request):
        report_data = ReportTools._get_report(request)
        queryset = report_data.get('queryset')

        output_file = io.BytesIO()
        workbook = xlsxwriter.Workbook(output_file, {'in_memory': True})
        worksheet = workbook.add_worksheet()

        NOT_FOUNDED = 'Не определен'
        row = 1
        for rl in queryset:
            fields = [
                NOT_FOUNDED if rl.employee is None else rl.employee.get_full_name(),
                NOT_FOUNDED if rl.device is None else rl.device.name,
                NOT_FOUNDED if rl.device is None else rl.device.mqtt,
                rl.moment.strftime('%Y-%m-%d %H:%M:%S'),
                NOT_FOUNDED if rl.request_type is None else rl.get_request_type_display(),
                NOT_FOUNDED if rl.response_type is None else rl.get_response_type_display(),
                rl.description,
                NOT_FOUNDED if rl.algorithm_type is None else rl.get_algorithm_type_display(),
            ]
            col = 0
            for f in fields:
                worksheet.write(row, col, f)
                col += 1
            row += 1

        def get_max_field_lenght_list(f, caption=None):
            return 4 + max(list(len(str(s)) for s in set(queryset.values_list(f, flat=True)))
                           + [0 if caption is None else len(caption)])
        max_employee_name_lenght = 4 + max(list(map(lambda e: len(e.get_full_name()),
                                                    Employee.objects.filter(
            id__in=set(queryset.values_list('employee', flat=True))))) + [len('Сотрудник')])

        fields = [
            {'name': 'Сотрудник', 'length': max_employee_name_lenght},
            {'name': 'Устройство', 'length': get_max_field_lenght_list(
                'device__name', 'Устройство')},
            {'name': 'ИД устройства', 'length': get_max_field_lenght_list(
                'device__mqtt', 'ИД устройства')},
            {'name': 'Дата', 'length': 23},
            {'name': 'Запрос', 'length': get_max_field_lenght_list(
                'request_type', 'Запрос')},
            {'name': 'Ответ', 'length': get_max_field_lenght_list(
                'response_type', 'Ответ')},
            {'name': 'Описание', 'length': get_max_field_lenght_list(
                'description', 'Описание')},
            {'name': 'Алгоритм', 'length': get_max_field_lenght_list(
                'algorithm_type', 'Алгоритм')},
        ]
        i = 0
        for f in fields:
            worksheet.write(0, i, f.get('name'))
            worksheet.set_column(i, i, f.get('length'))
            i += 1

        workbook.close()

        output_file.seek(0)

        file_name = 'Report ' + \
            report_data.get('name') + ' ' + \
            datetime.now().strftime('%Y_%m_%d') + '.xlsx'

        response = FileResponse(streaming_content=output_file, as_attachment=True, filename=file_name,
                                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Access-Control-Allow-Headers'] = 'Content-Type'

        return response

    @staticmethod
    @api_view(['GET'])
    @_LoginMethods.login_check_decorator(Login.CONTROLLER, Login.ADMIN)
    def get_report(request):
        login = _LoginMethods.get_login(request.user)

        show_organization = 'showorganization' in request.GET
        entity_id = _get_request_param(request, 'id', True)
        entity_type = ReportTools._ReportType(
            _get_request_param(request, 'type'))
        show_department = (entity_type == ReportTools._ReportType.DEPARTMENT) and (
            entity_id is not None)
        show_device = 'showdevice' in request.GET

        report_data = ReportTools._get_report(request)
        report_queryset = report_data.get('queryset')

        result = {}

        extra = {}

        employees_ids = set(
            report_queryset.values_list('employee_id', flat=True))
        employees_queryset = Employee.objects.filter(
            id__in=employees_ids)

        extra.update(employees=_get_objects_by_id(
            EmployeeSerializers.ModelSerializer, queryset=employees_queryset))

        if show_organization:
            if login.role == Login.CONTROLLER:
                extra.update(organizations={
                    login.organization_id: OrganizationSerializers.ModelSerializer(
                        Organization.objects.get(pk=login.organization_id)).data})

        if show_department:
            extra.update({'department': DepartmentSerializers.ModelSerializer(
                Department.objects.get(id=entity_id)).data})

        if show_device:
            devices_ids = set(
                report_queryset.values_list('device_id', flat=True))
            extra.update(devices=_get_objects_by_id(
                DeviceSerializers.ModelSerializer, clazz=Device, ids=devices_ids))

        result.update(count=report_data.get('count'))
        result.update(extra=extra)

        result.update(data=EmployeeRequestSerializer(
            report_queryset, many=True).data)

        return Response(result)


def _get_objects_by_id(serializer, queryset=None, ids=None, clazz=None):
    if (clazz is not None) and (ids is not None):
        queryset = clazz.objects.filter(id__in=ids)
    result = None
    if queryset is not None:
        data = map(lambda i: serializer(i).data, queryset)
        result = {}
        for o in data:
            result.update({o.get('id'): o})

    return result


def _get_organizations_by_id(ids):
    return _get_objects_by_id(OrganizationSerializers.ModelSerializer, clazz=Organization, ids=ids)


class RelationsUtils:
    @staticmethod
    def get_relates(slave_clazz,
                    slave_key,
                    relation_clazz,
                    master_key,
                    master_id,
                    login,
                    intersections=True,):
        result = {}

        related_object_ids = relation_clazz.objects.filter(
            Q(**{master_key: master_id})).values_list(slave_key, flat=True)

        queryset = None
        if intersections:
            queryset = slave_clazz.objects.filter(id__in=related_object_ids)
        else:
            queryset = slave_clazz.objects.exclude(id__in=related_object_ids)

        role = login.role
        if (role == Login.CONTROLLER) or (role == Login.REGISTRATOR):
            organization = login.organization_id
            if relation_clazz is Employee2Department:
                if slave_clazz is Employee:
                    queryset = queryset.filter(id__in=Employee2Organization.objects.filter(
                        organization_id=organization).values_list('employee', flat=True))
                elif slave_clazz is Department:
                    queryset = queryset.filter(organization_id=organization)
            elif relation_clazz is Device2DeviceGroup:
                if slave_clazz is Device:
                    queryset = queryset.filter(id__in=Device2Organization.objects.filter(
                        organization_id=organization).values_list('device', flat=True))
                elif slave_clazz is DeviceGroup:
                    queryset = queryset.filter(id__in=DeviceGroup2Organization.objects.filter(
                        organization_id=organization).values_list('device_group', flat=True))

        return queryset

    @staticmethod
    def _get_relation_clazz(clazz1, clazz2, swap_if_undefined=True):
        result = None
        if clazz1 is DeviceGroup:
            if clazz2 is Organization:
                result = DeviceGroup2Organization
            elif clazz2 is Device:
                result = Device2DeviceGroup
        elif clazz1 is Device:
            if clazz2 is Organization:
                result = Device2Organization
        elif clazz1 is Employee:
            if clazz2 is Organization:
                result = Employee2Organization
            if clazz2 is Department:
                result = Employee2Department

        return result if result is not None else (RelationsUtils._get_relation_clazz(clazz2, clazz1, False) if swap_if_undefined else result)

    _ENTRY2CLAZZ_N_SERIALIZER = {
        'devices': {'clazz': Device, 'serializer': DeviceSerializers.ModelSerializer, 'key': 'device_id'},
        'deviceGroups': {'clazz': DeviceGroup, 'serializer': DeviceGroupSerializers.ModelSerializer, 'key': 'device_group_id'},
        'organizations': {'clazz': Organization, 'serializer': OrganizationSerializers.ModelSerializer, 'key': 'organization_id'},
        'employees': {'clazz': Employee, 'serializer': EmployeeSerializers.ModelSerializer, 'key': 'employee_id'},
        'departments': {'clazz': Department, 'serializer': DepartmentSerializers.ModelSerializer, 'key': 'department_id'},
    }

    @staticmethod
    def _get_clazz_n_serializer_by_entry_name(name, is_many=False):
        name = name[:1].lower() + name[1:] if name else ''
        return RelationsUtils._ENTRY2CLAZZ_N_SERIALIZER.get(name + ('' if is_many else 's'), None)

    @staticmethod
    def _add_or_remove_relations(request, master_name, master_id, slave_name, adding_mode=True):
        master_info = RelationsUtils._get_clazz_n_serializer_by_entry_name(
            master_name, True)
        slave_info = RelationsUtils._get_clazz_n_serializer_by_entry_name(
            slave_name)

        master_clazz = master_info.get('clazz')
        slave_clazz = slave_info.get('clazz')

        login = _LoginMethods.get_login(request.user)
        success = []
        failure = []

        master_key = master_info.get('key')
        slave_key = slave_info.get('key')
        relation_clazz = RelationsUtils._get_relation_clazz(
            master_clazz, slave_clazz)

        exists_ids = RelationsUtils.get_relates(slave_clazz, slave_key, relation_clazz,
                                                master_key, master_id, login).values_list('id', flat=True)

        getted_ids = set(map(lambda i: int(i), set(
            request.POST.get('ids').split(','))))

        if adding_mode:
            success = getted_ids.difference(exists_ids)
            for added_id in success:
                relation_clazz.objects.create(
                    **{slave_key: added_id, master_key: master_id})
        else:
            success = getted_ids.intersection(exists_ids)
            relation_clazz.objects.filter(**{master_key: master_id}).filter(
                **{(slave_key + '__in'): success}).delete()

        failure = getted_ids.difference(success)

        return Response({'data': {'success': success, 'failure': failure}})

    @staticmethod
    @api_view(['POST'])
    @_LoginMethods.login_check_decorator(Login.REGISTRATOR, Login.ADMIN)
    def add_relation(request, master_name, master_id, slave_name):
        return RelationsUtils._add_or_remove_relations(request, master_name, master_id, slave_name, True)

    @staticmethod
    @api_view(['POST'])
    @_LoginMethods.login_check_decorator(Login.REGISTRATOR, Login.ADMIN)
    def remove_relation(request, master_name, master_id, slave_name):
        return RelationsUtils._add_or_remove_relations(request, master_name, master_id, slave_name, False)

    @staticmethod
    @api_view(['GET'])
    @_LoginMethods.login_check_decorator(Login.REGISTRATOR, Login.ADMIN)
    def get_non_related(request, master_name, master_id, slave_name):
        result = {}

        master_info = RelationsUtils._get_clazz_n_serializer_by_entry_name(
            master_name, True)
        slave_info = RelationsUtils._get_clazz_n_serializer_by_entry_name(
            slave_name)

        master_key = master_info.get('key')
        slave_key = slave_info.get('key')
        relation_clazz = RelationsUtils._get_relation_clazz(
            master_info.get('clazz'), slave_info.get('clazz'))

        login = _LoginMethods.get_login(request.user)
        queryset = RelationsUtils.get_relates(slave_info.get('clazz'), slave_key,
                                              relation_clazz, master_key, master_id, login, intersections=False,)

        result.update(data=slave_info.get('serializer')
                      (queryset, many=True).data)

        return Response(result)


class MqttUtils:
    USE_SSL = False
    USERNAME = None
    PASSWORD = None
    CLEAN_SESSION = True
    HOST = 'tgu.idenick.ru'
    PORT = 1883
    SUBSCRIBE_TOPIC_THREAD = '/BIOID/CLOUD/'
    PUBLISH_TOPIC_THREAD = '/BIOID/CLIENT/'
    PATH = '/mqtt'

    @staticmethod
    def _on_connect(client, userdata, flags, rc):
        print(client._client_id.decode('utf-8') + " Connected to %s:%s%s with result code %s" % (
            MqttUtils.HOST, MqttUtils.PORT, MqttUtils.PATH, str(rc)))

    @staticmethod
    def _on_subscribe(client, userdata, mid, granted_qos):
        print(client._client_id.decode('utf-8') + ' subscribed')

    @staticmethod
    def _on_disconnect(client, userdata, rc):
        print(client._client_id.decode('utf-8') + " disconnected")

    @staticmethod
    def _on_message(client, userdata, msg, payloads_info=None):
        payload_str = str(msg.payload)
        print(msg.topic + " " + payload_str)

        if payloads_info is not None:
            payloads_info.update(count=(payloads_info.get('count') + 1))
            payloads_info.update(msg_list=payloads_info.get(
                'msg_list') + [payload_str])

    @staticmethod
    @api_view(['POST'])
    def registrate(request, employee_id):
        employee = get_object_or_404(Employee.objects.all(), pk=employee_id)
        biometry_data = request.POST.get('biometryData')
        mqtt_id = request.POST.get('mqtt')

        publish_topic = MqttUtils.PUBLISH_TOPIC_THREAD + mqtt_id
        subscribe_topic = MqttUtils.SUBSCRIBE_TOPIC_THREAD + mqtt_id

        user_info = ('%s,%s,%s'
                     % (employee.last_name, employee.first_name, employee.patronymic,))

        mqtt_command = None
        if mqtt_id.startswith('05'):
            biometry_data = base64.b64decode(biometry_data)
            mqtt_command = ('!FACE_ENROLL,0,' + user_info +
                            '\r\n').encode('utf-8') + biometry_data
        elif mqtt_id.startswith('07'):
            mqtt_command = ('!IDENROLL,0,' + user_info + ',' +
                            biometry_data + '\r\n').encode('utf-8')
        else:
            biometry_data = base64.b64decode(biometry_data)
            mqtt_command = ('!ENROLL,0,' + user_info +
                            '\r\n').encode('utf-8') + biometry_data

        def on_connect(client, userdata, flags, rc, topic):
            MqttUtils._on_connect(client, userdata, flags, rc)
            client.subscribe(topic, qos=0)

        def on_subscribe(client, userdata, mid, granted_qos, topic, client_info, mqtt_command):
            MqttUtils._on_subscribe(client, userdata, mid, granted_qos)
            client.publish(topic, mqtt_command)
            client_info.update(subscribed=True)

        def on_message(client, userdata, msg, payloads_info, client_info):
            MqttUtils._on_message(client, userdata, msg, payloads_info)

            payload_str = str(msg.payload)
            employee_name = None
            if '!DUPLICATE,' in payload_str:
                client_info.update(biometry_status=False)
                employee_name = msg.payload[13:].decode(
                    'utf-8').strip().split(',')[0:3]
            elif '!ENROLL_OK,' in payload_str:
                client_info.update(biometry_status=True)
                employee_name = msg.payload[13:].decode(
                    'utf-8').strip().split(',')[0:3]

            if employee_name is not None:
                employee = Employee.objects.filter(
                    last_name=employee_name[0], first_name=employee_name[1],
                    patronymic=employee_name[2])

                if employee.exists():
                    client_info.update(
                        employee={employee.first().id: ' '.join(employee_name)})

                client.disconnect()

        payloads_info = {'msg_list': [], 'count': 0}
        client_info = {'biometry_status': None,
                       'subscribed': False, 'employee': None, }

        client = mqtt.Client(
            client_id=(mqtt_id + ' biometry_endroll'), clean_session=True, transport="tcp")
        client.on_disconnect = MqttUtils._on_disconnect
        client.on_connect = lambda client, userdata, flags, rc: on_connect(
            client, userdata, flags, rc, subscribe_topic)
        client.on_message = lambda client, userdata, msg: \
            on_message(client, userdata, msg,
                       payloads_info, client_info)
        client.on_subscribe = lambda client, userdata, mid, granted_qos: \
            on_subscribe(client, userdata, mid,
                         granted_qos, publish_topic, client_info, mqtt_command)

        MqttUtils.connect(client)

        waiting = 0
        while (waiting < 20) and client_info.get('biometry_status') is None:
            client.loop(timeout=4.0)
            waiting += 1

        result = {'success': None, 'msg': None, 'employee': None}
        if client_info.get('biometry_status') is None:
            search_client.disconnect()
            result.update(success=False)
        else:
            result.update(success=client_info.get('biometry_status'))
            result.update(employee=client_info.get('employee'))
            if not client_info.get('biometry_status'):
                result.update(msg='Дубликат')

        return Response(result)

    @staticmethod
    @api_view(['GET'])
    def create_biometry(request, device_id):
        device = get_object_or_404(Device.objects.all(), pk=device_id)
        biometry_info = {
            'success': None,
            'msg': None,
            'employee': None,
            'data': None,
            'mqtt': device.mqtt,
            'isFace': False,
            'isFinger': False,
            'isCard': False
        }

        if device.mqtt.startswith('05'):
            biometry_info.update(MqttUtils._make_photo(device))
            biometry_info.update(isFace=True)
        elif device.mqtt.startswith('07'):
            biometry_info.update(MqttUtils._read_card(device))
            biometry_info.update(isCard=True)
        else:
            biometry_info.update(MqttUtils._read_finger(device))
            biometry_info.update(isFinger=not device.mqtt.startswith('07'))

        return Response(biometry_info)

    @staticmethod
    def _read_card(device):
        def on_connect(client, userdata, flags, rc, topic):
            MqttUtils._on_connect(client, userdata, flags, rc)
            client.subscribe(topic, qos=0)

        def l_on_subscribe(client, userdata, mid, granted_qos, client_info):
            MqttUtils._on_subscribe(client, userdata, mid, granted_qos)
            client_info.update(subscribed=True)

        def l_on_message(client, userdata, msg, payloads_info, client_info):
            MqttUtils._on_message(client, userdata, msg, payloads_info)

            if '!IDSEARCH,' in str(msg.payload[:20]):
                payload_str = msg.payload[10:].decode('utf-8').strip()
                client_info.update(
                    biometry_data=payload_str[1 + payload_str.index(','):])
                client.disconnect()

        payloads_info = {'msg_list': [], 'count': 0}
        client_info = {'is_dublicate': None,
                       'subscribed': False, 'biometry_data': None, 'employee': None, }

        subscribe_topic = MqttUtils.SUBSCRIBE_TOPIC_THREAD + device.mqtt

        listener = mqtt.Client(
            client_id=(device.mqtt + ' card_listener'), clean_session=True, transport="tcp")
        listener.on_disconnect = MqttUtils._on_disconnect
        listener.on_connect = lambda client, userdata, flags, rc: on_connect(
            client, userdata, flags, rc, subscribe_topic)
        listener.on_message = lambda client, userdata, msg: \
            l_on_message(client, userdata, msg, payloads_info, client_info)
        listener.on_subscribe = lambda client, userdata, mid, granted_qos: \
            l_on_subscribe(client, userdata, mid, granted_qos, client_info)

        MqttUtils.connect(listener)

        waiting = 0
        while (waiting < 20) and client_info.get('biometry_data') is None:
            listener.loop(timeout=4.0)
            waiting += 1
        if client_info.get('biometry_data') is None:
            listener.disconnect()
        else:
            def s_on_subscribe(client, userdata, mid, granted_qos, client_info):
                MqttUtils._on_subscribe(client, userdata, mid, granted_qos)

                def p_on_connect(client, userdata, flags, rc, topic, card):
                    MqttUtils._on_connect(client, userdata, flags, rc)
                    client.publish(topic, '!IDSEARCH,0,' + card + '\r\n')

                publish_topic = MqttUtils.PUBLISH_TOPIC_THREAD + device.mqtt
                p_client = mqtt.Client(
                    client_id=(publish_topic + ' card_search_publisher'),
                    clean_session=True, transport="tcp")
                p_client.on_disconnect = MqttUtils._on_disconnect
                p_client.on_connect = lambda client, userdata, flags, rc: \
                    p_on_connect(client, userdata, flags,
                                 rc, publish_topic, client_info.get('biometry_data'))
                p_client.on_publish = lambda client, userdata, result: client.disconnect()

                MqttUtils.connect(p_client)
                p_client.loop_forever()

            def s_on_message(client, userdata, msg, payloads_info, client_info):
                MqttUtils._on_message(client, userdata, msg, payloads_info)
                payload_prefix = str(msg.payload[:20])
                if '!SEARCH_OK,' in payload_prefix:
                    search_ok_msg = msg.payload.decode(
                        'utf-8').strip().split(',')

                    employee = Employee.objects.filter(
                        last_name=search_ok_msg[2], first_name=search_ok_msg[3],
                        patronymic=search_ok_msg[4])

                    if employee.exists():
                        client_info.update(
                            employee={employee.first().id: ' '.join(search_ok_msg[0:3])})
                    client_info.update(is_dublicate=True)
                elif '!NOMATCH,' in payload_prefix:
                    client_info.update(is_dublicate=False)

                if client_info.get('is_dublicate') is not None:
                    client.disconnect()

            searcher = mqtt.Client(
                client_id=(device.mqtt + ' card_searcher'), clean_session=True, transport="tcp")
            searcher.on_disconnect = MqttUtils._on_disconnect
            searcher.on_connect = lambda client, userdata, flags, rc: on_connect(
                client, userdata, flags, rc, subscribe_topic)
            searcher.on_message = lambda client, userdata, msg: \
                s_on_message(client, userdata, msg, payloads_info, client_info)
            searcher.on_subscribe = lambda client, userdata, mid, granted_qos: \
                s_on_subscribe(client, userdata, mid, granted_qos, client_info)

            MqttUtils.connect(searcher)

            waiting = 0
            while (waiting < 20) and client_info.get('is_dublicate') is None:
                searcher.loop(timeout=4.0)
                waiting += 1
            if client_info.get('is_dublicate') is None:
                searcher.disconnect()

        result = {'data': None, 'success': None, 'msg': None}

        if client_info.get('biometry_data') is None:
            result.update(success=False)
            if not client_info.get('subscribed'):
                result.update(msg='Устройство не отвечает')
        else:
            result.update(success=(not client_info.get('is_dublicate')))
            result.update(data=client_info.get('biometry_data'))
            result.update(employee=client_info.get('employee'))
            if client_info.get('is_dublicate'):
                result.update(msg='Дубликат')

        return result

    @staticmethod
    def connect(client):
        count = 0
        connected = False
        while (not connected) and (count < 3):
            try:
                client.connect(MqttUtils.HOST, MqttUtils.PORT, 60)
                connected = True
            except:
                pass
            count += 1

    @staticmethod
    def _make_photo(device):
        publish_topic = MqttUtils.PUBLISH_TOPIC_THREAD + device.mqtt
        subscribe_topic = MqttUtils.SUBSCRIBE_TOPIC_THREAD + device.mqtt
        subscribe_info = {'one': False, 'two': False}

        def publish_command():
            def p_connect_callback(p_client, p_userdata, p_flags, p_rc):
                MqttUtils._on_connect(p_client, p_userdata, p_flags, p_rc)
                p_client.publish(subscribe_topic, "!MakePhoto")

            p_client = mqtt.Client(
                client_id=(publish_topic + ' publisher'), clean_session=True, transport="tcp")
            p_client.on_disconnect = MqttUtils._on_disconnect
            p_client.on_connect = p_connect_callback
            p_client.on_publish = lambda client, userdata, result: client.disconnect()

            MqttUtils.connect(p_client)
            p_client.loop_forever()

        def s1_subscribe_callback(client, userdata, mid, granted_qos, subscribe_info):
            MqttUtils._on_subscribe(client, userdata, mid, granted_qos)
            subscribe_info.update(one=True)
            if subscribe_info.get('two'):
                publish_command()

        def s2_subscribe_callback(client, userdata, mid, granted_qos, subscribe_info):
            MqttUtils._on_subscribe(client, userdata, mid, granted_qos)
            subscribe_info.update(two=True)
            if subscribe_info.get('one'):
                publish_command()

        def s_disconnect_callback(client, userdata, rc, payloads_info):
            MqttUtils._on_disconnect(client, userdata, rc)
            payloads_info.update(subscribed=None)

        def s1_connect_callback(s_client, s_userdata, s_flags, s_rc):
            MqttUtils._on_connect(s_client, s_userdata, s_flags, s_rc)
            s_client.subscribe(subscribe_topic, qos=0)

        def s2_connect_callback(s_client, s_userdata, s_flags, s_rc):
            MqttUtils._on_connect(s_client, s_userdata, s_flags, s_rc)
            s_client.subscribe(publish_topic, qos=0)

        def s_message_callback(client, userdata, msg, payloads_info, photo_payload):
            MqttUtils._on_message(client, userdata, msg, payloads_info)

            payload_str = str(msg.payload)
            if '!FACE_SEARCH,' in payload_str:
                photo_payload.update(data=msg.payload[16:])
                client.disconnect()
            elif '!ERROR,' in payload_str:
                photo_payload.update(success=False)
                if 'System.NullReferenceException' in payload_str:
                    photo_payload.update(
                        msg=msg.payload[9:-2].decode('utf-8').strip())
            elif '!NOMATCH,' in payload_str:
                photo_payload.update(success=True)
            elif '!SEARCH_OK,' in payload_str:
                photo_payload.update(success=False)
                search_ok_msg = msg.payload.decode('utf-8').strip().split(',')

                employee = Employee.objects.filter(
                    last_name=search_ok_msg[2], first_name=search_ok_msg[3],
                    patronymic=search_ok_msg[4])

                if employee.exists():
                    photo_payload.update(msg='Пользователь существует')
                    photo_payload.update(
                        employee={employee.first().id: ' '.join(search_ok_msg[2:5])})
                else:
                    photo_payload.update(
                        msg='Пользователь существует, но не найден (' + ' '.join(search_ok_msg[2:5]) + ')')

            if photo_payload.get('success') is not None:
                client.disconnect()

        payloads_info = {'msg_list': [], 'count': 0, 'subscribed': None}
        photo_payload = {'data': None, 'success': None,
                         'msg': None, 'employee': None}

        s1_client = mqtt.Client(
            client_id=(subscribe_topic + ' listener1'), clean_session=True, transport="tcp")
        s1_client.on_connect = s1_connect_callback
        s1_client.on_subscribe = lambda client, userdata, mid, granted_qos: \
            s1_subscribe_callback(client, userdata, mid,
                                  granted_qos, subscribe_info)
        s1_client.on_disconnect = lambda client, userdata, rc: \
            s_disconnect_callback(client, userdata, rc, payloads_info)
        s1_client.on_message = lambda client, userdata, msg: \
            s_message_callback(client, userdata, msg,
                               payloads_info, photo_payload)

        s2_client = mqtt.Client(
            client_id=(publish_topic + ' listener2'), clean_session=True, transport="tcp")
        s2_client.on_connect = s2_connect_callback
        s2_client.on_subscribe = lambda client, userdata, mid, granted_qos: \
            s2_subscribe_callback(client, userdata, mid,
                                  granted_qos, subscribe_info)
        s2_client.on_disconnect = lambda client, userdata, rc: \
            s_disconnect_callback(client, userdata, rc, payloads_info)
        s2_client.on_message = lambda client, userdata, msg: \
            s_message_callback(client, userdata, msg,
                               payloads_info, photo_payload)

        MqttUtils.connect(s1_client)
        MqttUtils.connect(s2_client)

        subscribe_waiting = 0
        while (subscribe_waiting < 25) and not (subscribe_info.get('one') and subscribe_info.get('two')):
            if not subscribe_info.get('one'):
                s1_client.loop(timeout=5.0)
            if not subscribe_info.get('two'):
                s2_client.loop(timeout=5.0)

            subscribe_waiting += 1

        equals_counts = 0
        prev_loop_count = 0
        with_error = False
        try:
            while (equals_counts < 5) and (payloads_info.get('count') < 8) and (photo_payload.get('success') is None):
                s1_client.loop(timeout=4.0)
                s2_client.loop(timeout=4.0)
                if prev_loop_count == payloads_info.get('count'):
                    equals_counts += 1
                else:
                    prev_loop_count = payloads_info.get('count')
        except Exception as err:
            with_error = True

        s1_client.disconnect()
        s2_client.disconnect()

        result = {'data': None, 'success': None, 'msg': None}
        if photo_payload.get('data') is not None:
            photo_data = photo_payload.get('data')
            result.update(data=base64.b64encode(photo_data))

        result.update(success=(not with_error) and (
            photo_payload.get('success') is True))
        if photo_payload.get('employee') is not None:
            result.update(employee=photo_payload.get('employee'))

        if with_error:
            result.update(msg='Ошибка подключения к устройству')
        if photo_payload.get('msg') is not None:
            result.update(msg=photo_payload.get('msg'))

        return result

    @staticmethod
    def _read_finger(device):
        publish_topic = MqttUtils.PUBLISH_TOPIC_THREAD + device.mqtt
        subscribe_topic = MqttUtils.SUBSCRIBE_TOPIC_THREAD + device.mqtt

        def s_subscribe_callback(client, userdata, mid, granted_qos, client_info, topic):
            MqttUtils._on_subscribe(client, userdata, mid, granted_qos)
            client_info.update({topic: True})

        def s_disconnect_callback(client, userdata, rc, client_info, topic):
            MqttUtils._on_disconnect(client, userdata, rc)
            client_info.update({topic: False})

        def s_connect_callback(s_client, s_userdata, s_flags, s_rc, topic):
            MqttUtils._on_connect(s_client, s_userdata, s_flags, s_rc)
            s_client.subscribe(topic, qos=0)

        def s_message_callback(client, userdata, msg, payloads_info, client_info):
            MqttUtils._on_message(client, userdata, msg, payloads_info)

            payload_str = str(msg.payload[0:20])[2:]
            if '!SEARCH,' in payload_str:
                client_info.update(
                    biometry_data=msg.payload[11 + payload_str[8:].index(','):])
                client.disconnect()
            elif '!NOMATCH,' in payload_str:
                client_info.update(is_dublicate=False)
            elif '!SEARCH_OK,' in payload_str:
                client_info.update(is_dublicate=True)
                search_ok_msg = msg.payload.decode('utf-8').strip().split(',')

                employee = Employee.objects.filter(
                    last_name=search_ok_msg[2], first_name=search_ok_msg[3],
                    patronymic=search_ok_msg[4])

                if employee.exists():
                    client_info.update(
                        employee={employee.first().id: ' '.join(search_ok_msg[2:5])})

            if client_info.get('is_dublicate') is not None:
                client.disconnect()

        def init_listener(topic, client_info, payloads_info):
            s_client = mqtt.Client(
                client_id=(topic + ' finger_listener'), clean_session=True, transport="tcp")
            s_client.on_connect = lambda client, userdata, flags, rc: s_connect_callback(
                client, userdata, flags, rc, topic)
            s_client.on_subscribe = lambda client, userdata, mid, granted_qos: \
                s_subscribe_callback(client, userdata, mid,
                                     granted_qos, client_info, topic)
            s_client.on_disconnect = lambda client, userdata, rc: \
                s_disconnect_callback(client, userdata, rc,
                                      client_info, topic)
            s_client.on_message = lambda client, userdata, msg: \
                s_message_callback(client, userdata, msg,
                                   payloads_info, client_info)

            MqttUtils.connect(s_client)

            return s_client

        payloads_info = {'msg_list': [], 'count': 0, }
        client_info = {'is_dublicate': None, publish_topic: False, subscribe_topic: False,
                       'biometry_data': None, 'employee': None, }

        s1_client = init_listener(subscribe_topic, client_info, payloads_info)
        s2_client = init_listener(publish_topic, client_info, payloads_info)

        waiting = 0
        while (waiting < 25) \
                and not (client_info.get(subscribe_topic) and client_info.get(publish_topic)):
            if not client_info.get(subscribe_topic):
                s1_client.loop(timeout=5.0)
            if not client_info.get(publish_topic):
                s2_client.loop(timeout=5.0)

            waiting += 1

        waiting = 0
        while (waiting < 20) \
                and ((client_info.get('biometry_data') is None)
                     or (client_info.get('is_dublicate') is None)):
            if client_info.get('is_dublicate') is None:
                s1_client.loop(timeout=4.0)
            if client_info.get('biometry_data') is None:
                s2_client.loop(timeout=4.0)
            waiting += 1
        if (client_info.get('biometry_data') is None) or (client_info.get('is_dublicate') is None):
            s1_client.disconnect()
            s2_client.disconnect()

        result = {'data': None, 'success': None, 'msg': None}

        if client_info.get('biometry_data') is None:
            result.update(success=False)
            if not client_info.get('subscribed'):
                result.update(msg='Устройство не отвечает')
        else:
            result.update(success=(not client_info.get('is_dublicate')))

            photo_data = client_info.get('biometry_data')
            result.update(data=base64.b64encode(photo_data))
            result.update(employee=client_info.get('employee'))
            if client_info.get('is_dublicate'):
                result.update(msg='Дубликат')

        return result
