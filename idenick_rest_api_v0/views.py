import io
from abc import abstractmethod
from datetime import datetime, timedelta
from enum import Enum
from functools import wraps

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
    _object_type = None

    def _get_queryset(self, request):
        pass

    def _get_count_all(self, request):
        return self._object_type.objects.all().count()

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

        return {'data': serializer.data, 'count': self._get_count_all(request)}

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

    _object_type = Organization

    def _get_queryset(self, request):
        queryset = self._object_type.objects.all()

        name_filter = _get_request_param(request, 'name')
        if name_filter is not None:
            queryset = queryset.filter(name__icontains=name_filter)
        device_group_filter = _get_request_param(request, 'deviceGroup', True)
        if device_group_filter is not None:
            organization_id_list = queryset.values_list('id', flat=True)
            queryset = queryset.filter(id__in=DeviceGroup2Organization.objects.filter(
                organization_id__in=organization_id_list).filter(
                device_group_id=device_group_filter).values_list('organization', flat=True))
        device_filter = _get_request_param(request, 'device', True)
        if device_filter is not None:
            organization_id_list = queryset.values_list('id', flat=True)
            queryset = queryset.filter(id__in=Device2Organization.objects.filter(
                organization_id__in=organization_id_list).filter(
                device_id=device_filter).values_list('organization', flat=True))
        employee_filter = _get_request_param(request, 'employee', True)
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

    _object_type = Department

    def _get_count_all(self, request):
        queryset = self._object_type.objects.all()

        login = _LoginMethods.get_login(request.user)
        if (login.role == Login.CONTROLLER) or (login.role == Login.REGISTRATOR):
            queryset = queryset.filter(organization=login.organization_id)

        employee_filter = _get_request_param(
            request, 'employee', True, base_filter=True)
        if employee_filter is not None:
            queryset = queryset.filter(
                id__in=Employee2Department.objects.filter(
                    employee_id=employee_filter).values_list('department', flat=True))

        return queryset.count()

    def _get_queryset(self, request):
        login = _LoginMethods.get_login(request.user)
        queryset = None
        role = login.role
        if role == Login.ADMIN:
            queryset = Department.objects.all()
        elif (role == Login.CONTROLLER) or (role == Login.REGISTRATOR):
            queryset = Department.objects.filter(
                organization_id=login.organization_id)

        name_filter = _get_request_param(request, 'name')
        if name_filter is not None:
            queryset = queryset.filter(name__icontains=name_filter)

        employee_filter = _get_request_param(request, 'employee', True)
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

    _object_type = Employee

    def _get_count_all(self, request):
        queryset = self._object_type.objects.all()

        organization_filter = _get_request_param(
            request, 'organization', True, base_filter=True)

        login = _LoginMethods.get_login(request.user)
        if (organization_filter is None) \
                and ((login.role == Login.CONTROLLER) or (login.role == Login.REGISTRATOR)):
            organization_filter = login.organization_id

        department_filter = _get_request_param(
            request, 'department', True, base_filter=True)
        if department_filter is not None:
            queryset = queryset.filter(
                id__in=Employee2Department.objects.filter(
                    department_id=department_filter).values_list('employee', flat=True))

        if organization_filter is not None:
            queryset = queryset.filter(id__in=Employee2Organization.objects.filter(
                organization=organization_filter).values_list('employee', flat=True))

        return queryset.count()

    def _get_queryset(self, request):
        login = _LoginMethods.get_login(request.user)

        queryset = Employee.objects.all()

        name_filter = _get_request_param(request, 'name')
        if name_filter is not None:
            queryset = queryset.annotate(
                full_name=Concat('last_name', Value(
                    ' '), 'first_name', Value(' '), 'patronymic'),
            ).filter(Q(full_name__icontains=name_filter)
                     | Q(last_name__icontains=name_filter)
                     | Q(first_name__icontains=name_filter)
                     | Q(patronymic__icontains=name_filter))

        department_filter = _get_request_param(request, 'department', True)
        if (department_filter is not None):
            queryset = queryset.filter(
                id__in=Employee2Department.objects.filter(
                    department_id=department_filter).values_list('employee', flat=True))

        organization_filter = None
        if (login.role == Login.CONTROLLER) or (login.role == Login.REGISTRATOR):
            organization_filter = login.organization_id
        elif login.role == Login.ADMIN:
            organization_filter = _get_request_param(
                request, 'organization', True)

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

            if login.role == Login.REGISTRATOR:
                Employee2Organization.objects.create(
                    **{'organization_id': login.organization_id, 'employee_id': employee.id})

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

    _object_type = Login

    def _get_count_all(self, request):
        queryset = Login.objects.filter(role=self._user_role(request))

        organization_filter = _get_request_param(
            request, 'organization', True, base_filter=True)

        login = _LoginMethods.get_login(request.user)
        if (organization_filter is None) and (login.role == Login.REGISTRATOR):
            organization_filter = login.organization_id

        if organization_filter is not None:
            queryset = queryset.filter(organization=organization_filter)

        return queryset.count()

    def _user_role(self, request):
        return Login.REGISTRATOR if (_LoginMethods.get_login(request.user).role == Login.ADMIN) \
            else Login.CONTROLLER

    def _get_queryset(self, request):
        result = Login.objects.filter(role=self._user_role(request))
        login = _LoginMethods.get_login(request.user)
        if login.role == Login.REGISTRATOR:
            result = result.filter(organization__id=login.organization_id)

        organization_filter = _get_request_param(
            request, 'organization', True)
        if organization_filter is not None:
            result = result.filter(organization__id=organization_filter)

        return result

    @_LoginMethods.login_check_decorator(Login.REGISTRATOR, Login.ADMIN)
    def list(self, request):
        queryset = self._get_queryset(
            request)
        name_filter = _get_request_param(request, 'name')
        users_ids = None
        if name_filter is not None:
            users_ids = set(map(lambda i: UserSerializer(i).data.get('id'), User.objects.annotate(
                full_name_1=Concat('last_name', Value(' '), 'first_name'),
                full_name_2=Concat('first_name', Value(' '), 'last_name'),
            ).filter(Q(full_name_1__icontains=name_filter) | Q(full_name_2__icontains=name_filter)
                     | Q(last_name__icontains=name_filter) | Q(first_name__icontains=name_filter))))
            queryset = queryset.filter(user_id__in=users_ids)

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

    _object_type = Device

    def _get_count_all(self, request):
        queryset = self._object_type.objects.all()

        organization_filter = _get_request_param(
            request, 'organization', True, base_filter=True)

        login = _LoginMethods.get_login(request.user)
        if (organization_filter is None) \
                and ((login.role == Login.CONTROLLER) or (login.role == Login.REGISTRATOR)):
            organization_filter = login.organization_id

        device_group_filter = _get_request_param(
            request, 'deviceGroup', True, base_filter=True)
        if device_group_filter is not None:
            queryset = queryset.filter(id__in=Device2DeviceGroup.objects.filter(
                device_group_id=device_group_filter).values_list('device', flat=True))

        if organization_filter is not None:
            queryset = queryset.filter(id__in=Device2Organization.objects.filter(
                organization=organization_filter).values_list('device', flat=True))

        return queryset.count()

    def _get_queryset(self, request):
        login = _LoginMethods.get_login(request.user)

        result = Device.objects.all()
        if login.role != Login.ADMIN:
            result = result.filter(id__in=Device2Organization.objects.filter(
                organization_id=login.organization_id).values_list('device_id', flat=True))

        return result

    @_LoginMethods.login_check_decorator()
    def list(self, request):
        queryset = self._get_queryset(request)
        login = _LoginMethods.get_login(request.user)

        name_filter = _get_request_param(request, 'name')
        if name_filter is not None:
            queryset = queryset.filter(
                Q(name__icontains=name_filter) | Q(mqtt__icontains=name_filter))
        device_group_filter = _get_request_param(request, 'deviceGroup', True)
        if device_group_filter is not None:
            queryset = queryset.filter(id__in=RelationsUtils.get_relates(Device, 'device_id', Device2DeviceGroup,
                                                                         'device_group_id', device_group_filter,
                                                                         login).values_list('id', flat=True))
        organization_filter = _get_request_param(request, 'organization', True)
        if organization_filter is not None:
            device_id_list = queryset.values_list('id', flat=True)
            queryset = queryset.filter(id__in=Device2Organization.objects.filter(
                device_id__in=device_id_list).filter(
                organization_id=organization_filter).values_list('device_id', flat=True))

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

            if login.role == Login.REGISTRATOR:
                Device2Organization.objects.create(
                    **{'organization_id': login.organization_id, 'device_id': device.id})

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

    _object_type = DeviceGroup

    def _get_count_all(self, request):
        queryset = DeviceGroup.objects.all()

        device_filter = _get_request_param(
            request, 'device', True, base_filter=True)
        if device_filter is not None:
            queryset = queryset.filter(id__in=Device2DeviceGroup.objects.
                                       filter(device_id=device_filter)
                                       .values_list('device_group', flat=True))

        organization_filter = _get_request_param(
            request, 'organization', True, base_filter=True)

        login = _LoginMethods.get_login(request.user)
        if (organization_filter is None) \
                and ((login.role == Login.CONTROLLER) or (login.role == Login.REGISTRATOR)):
            organization_filter = login.organization_id

        if organization_filter is not None:
            queryset = queryset.filter(id__in=DeviceGroup2Organization.objects.filter(
                organization=organization_filter).values_list('device_group', flat=True))

        return queryset.count()

    def _get_queryset(self, request):
        queryset = DeviceGroup.objects.all()

        login = _LoginMethods.get_login(request.user)

        name_filter = _get_request_param(request, 'name')
        if name_filter is not None:
            queryset = queryset.filter(name__icontains=name_filter)

        organization_filter = None
        if (login.role == Login.CONTROLLER) or (login.role == Login.REGISTRATOR):
            organization_filter = login.organization_id
        elif login.role == Login.ADMIN:
            organization_filter = _get_request_param(
                request, 'organization', True)
        if organization_filter is not None:
            group_id_list = queryset.values_list('id', flat=True)
            queryset = queryset.filter(id__in=DeviceGroup2Organization.objects.filter(
                device_group_id__in=group_id_list).filter(
                organization_id=organization_filter).values_list('device_group_id', flat=True))
        device_filter = _get_request_param(request, 'device', True)
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
            if login.role == Login.REGISTRATOR:
                DeviceGroup2Organization.objects.create(
                    **{'organization_id': login.organization_id,
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

        row = 1
        for rl in queryset:
            fields = [
                rl.employee.organization.name,
                rl.employee.get_full_name(),
                rl.device.name,
                rl.device.mqtt,
                rl.moment.strftime('%Y-%m-%d %H:%M:%S'),
                0 if rl.request_type is None else rl.request_type,
                0 if rl.response_type is None else rl.response_type,
                rl.description,
                0 if rl.algorithm_type is None else rl.algorithm_type,
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
            {'name': 'Организация', 'length': get_max_field_lenght_list(
                'employee__organization__name', 'Организация')},
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

        employees_ids = set(
            report_queryset.values_list('employee_id', flat=True))
        employees_queryset = Employee.objects.filter(
            id__in=employees_ids)

        result.update(employees=_get_objects_by_id(
            EmployeeSerializers.ModelSerializer, queryset=employees_queryset))

        if show_organization:
            if login.role == Login.CONTROLLER:
                result.update(organizations={
                    login.organization_id: OrganizationSerializers.ModelSerializer(
                        Organization.objects.get(pk=login.organization_id)).data})

        if show_department:
            result.update({'department': DepartmentSerializers.ModelSerializer(
                Department.objects.get(id=entity_id)).data})

        if show_device:
            devices_ids = set(
                report_queryset.values_list('device_id', flat=True))
            result.update(devices=_get_objects_by_id(
                DeviceSerializers.ModelSerializer, clazz=Device, ids=devices_ids))

        result.update(count=report_data.get('count'))

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
