import io
from abc import abstractmethod
from datetime import datetime, timedelta
from enum import Enum

import xlsxwriter
from django.contrib.auth.models import User
from django.db.models.expressions import Value
from django.db.models.functions.text import Concat
from django.db.models.query_utils import Q
from django.http import FileResponse
from django.http.request import QueryDict
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import api_view
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


class ErrorMessage(Enum):
    UNIQUE_DEPARTMENT_NAME = 'Подразделение с таким названием уже существует'


# from rest_framework.permissions import IsAuthen
class _AbstractViewSet(viewsets.ViewSet):

    def _response(self, data, status=status.HTTP_200_OK):
        return Response(data, headers={'Access-Control-Allow-Origin': '*', 'Content-Type': 'application/json'}, status=status)

    def _response4update_n_create(self, code=status.HTTP_200_OK, data=None, message=None):
        result = None
        if (data is None):
            result = Response({'message': message, 'success': False}, headers={'Access-Control-Allow-Origin': '*',
                                                                               'Content-Type': 'application/json'}, status=(status.HTTP_400_BAD_REQUEST if (code == status.HTTP_200_OK) else code))
        else:
            result = Response({'data': self._serializer_classes.get('retrieve')(data).data, 'success': True}, headers={
                              'Access-Control-Allow-Origin': '*', 'Content-Type': 'application/json'}, status=code)
        return result

    def get_serializer_class(self):
        return self._serializer_classes[self.action]

    def _list_data(self, request, queryset=None):
        _queryset = self._get_queryset(request) if (
            queryset is None) else queryset
        serializer = self.get_serializer_class()(_queryset, many=True)
        return {'data': serializer.data}

    def _retrieve(self, request, pk=None, queryset=None):
        return self._response(self._retrieve_data(request, pk, queryset))

    def _retrieve_data(self, request, pk=None, queryset=None):
        _queryset = self._get_queryset(request) if (
            queryset is None) else queryset
        entity = get_object_or_404(_queryset, pk=pk)
        serializer = self.get_serializer_class()(entity)
        return {'data': serializer.data}

    def _get_validation_error_msg(self, errors, object_class, update_verbose=True):
        msg_arr = []
        for field in errors.keys():
            sub_err = []
            err_prefix = ''
            for err in errors.get(field):
                sub_msg = None
                if (field == 'non_field_errors'):
                    if (err.code == 'unique') and ((object_class == Department) or (object_class == Device)):
                        err_prefix = 'Название: '
                        sub_msg = ('Подразделение' if (
                            object_class == Department) else 'Прибор') + ' с таким названием уже существует'
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
        if (serializer.is_valid()):
            update = Object_class(**serializer.data)
        elif self._alternative_valid(pk, data, serializer.errors, extra):
            serializer = serializer_class(data)
            update = Object_class(**serializer.data)

        return {'update': update, 'serializer': serializer}

# for admin


class OrganizationViewSet(_AbstractViewSet):
    _serializer_classes = {
        'list': OrganizationSerializers.ModelSerializer,
        'retrieve': OrganizationSerializers.ModelSerializer,
        'create': OrganizationSerializers.CreateSerializer,
        'partial_update': OrganizationSerializers.CreateSerializer,
    }

    def _get_queryset(self, request):
        return Organization.objects.all()

    def list(self, request):
        queryset = self._get_queryset(request)
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

        result = self._list_data(request, queryset)

        return self._response(result)

    def retrieve(self, request, pk=None):
        return self._retrieve(request, pk)

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
        return (len(errors.keys()) == 1) and errors.keys().__contains__('name') and (errors.get('name')[0].code == 'unique') and not Organization.objects.filter(name=data.get('name')).filter(~Q(id=pk)).exists()

    def delete(self, request, pk):
        queryset = Organization.objects.all()
        organization = get_object_or_404(queryset, pk=pk)
        organization.delete()
        return self._response({'message': 'Organization was deleted', 'data': self._serializer_classes.get('retrieve')(organization).data})


# for controller
# for registrator
class DepartmentViewSet(_AbstractViewSet):

    _serializer_classes = {
        'list': DepartmentSerializers.ModelSerializer,
        'retrieve': DepartmentSerializers.ModelSerializer,
        'create': DepartmentSerializers.CreateSerializer,
        'partial_update': DepartmentSerializers.CreateSerializer,
    }

    def _get_queryset(self, request):
        login = _get_login(request)
        result = None
        role = login.role
        if (role == Login.ADMIN):
            result = Department.objects.all()
        elif (role == Login.CONTROLLER) or (role == Login.REGISTRATOR):
            result = Department.objects.filter(organization=login.organization)
        return result

    def list(self, request):
        queryset = self._get_queryset(request)
        name_filter = _get_request_param(request, 'name')
        if name_filter is not None:
            queryset = queryset.filter(name__icontains=name_filter)

        employee_filter = _get_request_param(request, 'employee', True)
        if employee_filter is not None:
            queryset = queryset.filter(id__in=Employee2Department.objects.filter(
                employee_id=employee_filter).values_list('department_id', flat=True))

        result = self._list_data(request, queryset)

        if 'full' in request.GET:
            organizations_ids = set(
                map(lambda d: d.get('organization'), result.get('data')))
            result.update(
                {'organizations': _get_organizations_by_id(organizations_ids)})

        return self._response(result)

    def retrieve(self, request, pk=None):
        result = self._retrieve_data(request, pk)

        if 'full' in request.GET:
            result.update({'organization': OrganizationSerializers.ModelSerializer(
                Organization.objects.get(id=result.get('data',).get('organization'))).data})

        return self._response(result)

    def create(self, request):
        serializer_class = self.get_serializer_class()

        department_data = QueryDict('', mutable=True)
        department_data.update(request.data)
        department_data.update(
            {'organization': _get_login(request).organization_id})
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
        return (len(errors.keys()) == 1) and errors.keys().__contains__('non_field_errors') and (errors.get('non_field_errors')[0].code == 'unique') and not Department.objects.filter(Q(name=data.get('name')) & Q(organization_id=extra.get('organization'))).filter(~Q(id=pk)).exists()

    def delete(self, request, pk):
        queryset = Department.objects.all()
        department = get_object_or_404(queryset, pk=pk)
        department.delete()
        return self._response({'message': 'Department was deleted', 'data': self._serializer_classes.get('retrieve')(department).data})


class EmployeeViewSet(_AbstractViewSet):
    _serializer_classes = {
        'list': EmployeeSerializers.ModelSerializer,
        'retrieve': EmployeeSerializers.ModelSerializer,
        'create': EmployeeSerializers.CreateSerializer,
        'partial_update': EmployeeSerializers.CreateSerializer,
    }

    def _get_queryset(self, request):
        login = _get_login(request)
        department_filter = _get_request_param(request, 'department', True)

        result = None
        if (login.role == Login.CONTROLLER):
            filtered_employees = Employee2Department.objects.filter(
                department__organization=login.organization)
            if (department_filter is not None):
                filtered_employees = filtered_employees.filter(
                    department_id=department_filter)
            employees_ids = filtered_employees.values_list(
                'employee_id', flat=True)
            result = Employee.objects.filter(id__in=employees_ids)
        elif (login.role == Login.REGISTRATOR):
            organization_employees = Employee.objects.filter(
                organization=login.organization)
            if (department_filter is not None):
                all_employees_ids = organization_employees.values_list(
                    'id', flat=True)
                employees_ids = Employee2Department.objects.filter(employee_id__in=all_employees_ids).filter(
                    department_id=department_filter).values_list('employee_id', flat=True)
                result = Employee.objects.filter(id__in=employees_ids)
            else:
                result = organization_employees

        return result

    # TODO: check it
    def _withExtra(self, request, department_id=None):
        result = {}
        if 'full' in request.GET:
            login = _get_login(request)
            organization = OrganizationSerializers.ModelSerializer(
                login.organization).data

            result = {'organization': organization}
            if department_id is not None:
                result.update({'department': DepartmentSerializers.ModelSerializer(
                    Department.objects.get(pk=department_id)).data})

        return result

    def list(self, request):
        queryset = self._get_queryset(request)

        name_filter = _get_request_param(request, 'name')
        if name_filter is not None:
            queryset = queryset.annotate(
                full_name=Concat('last_name', Value(
                    ' '), 'first_name', Value(' '), 'patronymic'),
            ).filter(Q(full_name__icontains=name_filter)
                     | Q(last_name__icontains=name_filter)
                     | Q(first_name__icontains=name_filter)
                     | Q(patronymic__icontains=name_filter))

        result = self._list_data(request, queryset)

        department_filter = _get_request_param(request, 'department', True)
        result.update(self._withExtra(request, department_filter))

        return self._response(result)

    def retrieve(self, request, pk):
        result = self._retrieve_data(
            request, pk, self._get_queryset(request))
        department_filter = _get_request_param(request, 'department', True)
        result.update(self._withExtra(request, department_filter))

        employee_full = EmployeeSerializers.FullModelSerializer(
            Employee.objects.get(pk=result.get('data').get('id'))).data
        if 'full' in request.GET:
            result.update({'departments': map(lambda i: i.get(
                'department'), employee_full.get('departments'))})

        return self._response(result)

    def partial_update(self, request, pk=None):
        queryset = Employee.objects.all()
        employee = get_object_or_404(queryset, pk=pk)

        serializer_class = self.get_serializer_class()
        serializer = serializer_class(data=request.data)
        result = None
        login = _get_login(request)
        if serializer.is_valid() and (login.organization.id == employee.organization_id):
            data = serializer.data
            employee.last_name = data.get('last_name', employee.last_name)
            employee.first_name = data.get(
                'first_name', employee.first_name)
            employee.patronymic = data.get(
                'patronymic', employee.patronymic)
            employee.save()

            departments_ids = request.data.getlist('departments', [])
            departments = Department.objects.filter(
                organization_id=employee.organization_id).filter(id__in=departments_ids)
            for department in departments:
                Employee2Department.objects.create(
                    employee=employee, department=department)

            result = self._response4update_n_create(data=employee)

        return result

    def create(self, request):
        serializer_class = self.get_serializer_class()
        serializer = serializer_class(data=request.data)
        result = None

        login = _get_login(request)
        if serializer.is_valid() and (login.role == Login.REGISTRATOR):
            employee = Employee(**serializer.data)
            employee.organization = login.organization
            employee.save()

            departments_ids = request.data.getlist('departments', [])
            departments = Department.objects.filter(
                organization_id=employee.organization_id).filter(id__in=departments_ids)
            for department in departments:
                Employee2Department.objects.create(
                    employee=employee, department=department)

            result = self._response4update_n_create(
                data=employee, code=status.HTTP_201_CREATED)
        else:
            result = self._response4update_n_create(
                message=self._get_validation_error_msg(serializer.errors, Employee))

        return result

    def delete(self, request, pk):
        queryset = Employee.objects.all()
        employee = get_object_or_404(queryset, pk=pk)
        employee.delete()
        return self._response({'message': 'Employee was deleted', 'data': self._serializer_classes.get('retrieve')(employee).data})


class _UserViewSet(_AbstractViewSet):
    _serializer_classes = {
        'list': LoginSerializer.FullSerializer,
        'retrieve': LoginSerializer.FullSerializer,
        'create': LoginSerializer.CreateSerializer,
        'partial_update': LoginSerializer.UpdateSerializer,
    }

    def _user_role(self, request):
        return Login.REGISTRATOR if (_get_login(request).role == Login.ADMIN) \
            else Login.CONTROLLER

    def _get_queryset(self, request):
        result = Login.objects.filter(role=self._user_role(request))
        login = _get_login(request)
        if login.role == Login.REGISTRATOR:
            result = result.filter(organization__id=login.organization_id)

        organization_filter = _get_request_param(
            request, 'organization', True)
        if organization_filter is not None:
            result = result.filter(organization__id=organization_filter)

        return result

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
            current_user = _get_login(request)
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
    def retrieve(self, request, pk=None):
        return self._retrieve_user(request, pk=pk)

# for admin


class RegistratorViewSet(_UserViewSet):
    def create(self, request):
        return self._create(request)

    def retrieve(self, request, pk=None):
        return self._retrieve_user(request, pk=pk)

    def partial_update(self, request, pk=None):
        return self._partial_update(request, pk)


# for registrator
class ControllerViewSet(_UserViewSet):
    def create(self, request):
        return self._create(request)

    def retrieve(self, request, pk=None):
        return self._retrieve_user(request, pk)

    def partial_update(self, request, pk=None):
        return self._partial_update(request, pk)


class DeviceViewSet(_AbstractViewSet):
    _serializer_classes = {
        'list': DeviceSerializers.ModelSerializer,
        'retrieve': DeviceSerializers.ModelSerializer,
        'create': DeviceSerializers.CreateSerializer,
        'partial_update': DeviceSerializers.CreateSerializer,
    }

    def _get_queryset(self, request):
        login = _get_login(request)

        result = Device.objects.all()
        if login.role != Login.ADMIN:
            result = result.filter(id__in=Device2Organization.objects.filter(
                organization_id=login.organization_id).values_list('device_id', flat=True))

        return result

    def list(self, request):
        queryset = self._get_queryset(request)
        name_filter = _get_request_param(request, 'name')
        if name_filter is not None:
            queryset = queryset.filter(
                Q(name__icontains=name_filter) | Q(mqtt__icontains=name_filter))
        device_group_filter = _get_request_param(request, 'deviceGroup', True)
        if device_group_filter is not None:
            queryset = queryset.filter(id__in=_get_relates(Device, 'device_id', Device2DeviceGroup,
                                                           'device_group_id', device_group_filter).values_list('id', flat=True))
        organization_filter = _get_request_param(request, 'organization', True)
        if organization_filter is not None:
            device_id_list = queryset.values_list('id', flat=True)
            queryset = queryset.filter(id__in=Device2Organization.objects.filter(
                device_id__in=device_id_list).filter(
                organization_id=organization_filter).values_list('device_id', flat=True))

        result = self._list_data(request, queryset)

        return self._response(result)

    def retrieve(self, request, pk=None):
        result = self._retrieve_data(request, pk)

        login = _get_login(request)

        if ('full' in request.GET) and ((login.role == Login.CONTROLLER) or (login.role == Login.REGISTRATOR)):
            result.update({'organization': OrganizationSerializers.ModelSerializer(
                Organization.objects.get(id=login.organization_id)).data})

        return self._response(result)

    def create(self, request):
        login = _get_login(request)
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

    def partial_update(self, request, pk=None):
        device = get_object_or_404(self._get_queryset(request), pk=pk)

        serializer_class = self.get_serializer_class()
        result = None

        device_data = QueryDict('', mutable=True)
        device_data.update(request.data)
        device_data.update({'mqtt': device.mqtt})

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

    def delete(self, request, pk):
        queryset = self._get_queryset(request)
        device = get_object_or_404(queryset, pk=pk)
        device.delete()
        return self._response({'message': 'Device was deleted',
                               'data': self._serializer_classes.get('retrieve')(device).data})


def _get_request_param(request, name, is_int=False, default=None):
    param = request.GET.get(name, default)

    result = None
    if (param is not None) and (param != ''):
        if is_int:
            try:
                result = int(param)
            except ValueError:
                pass
        else:
            result = param

    return result


class DeviceGroupViewSet(_AbstractViewSet):
    _serializer_classes = {
        'list': DeviceGroupSerializers.ModelSerializer,
        'retrieve': DeviceGroupSerializers.ModelSerializer,
        'create': DeviceGroupSerializers.CreateSerializer,
        'partial_update': DeviceGroupSerializers.CreateSerializer,
    }

    def _get_queryset(self, request):
        return DeviceGroup.objects.all()

    def list(self, request):
        queryset = self._get_queryset(request)
        name_filter = _get_request_param(request, 'name')
        if name_filter is not None:
            queryset = queryset.filter(name__icontains=name_filter)
        organization_filter = _get_request_param(request, 'organization', True)
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

        result = self._list_data(request, queryset)

        return self._response(result)

    def retrieve(self, request, pk=None):
        result = self._retrieve_data(request, pk)

        return self._response(result)

    def create(self, request):
        serializer_class = self.get_serializer_class()
        serializer = serializer_class(data=request.data)
        result = None
        if serializer.is_valid():
            group = DeviceGroup(**serializer.data)
            group.save()
            result = self._response4update_n_create(
                data=group, code=status.HTTP_201_CREATED)
        else:
            result = self._response4update_n_create(
                message=self._get_validation_error_msg(serializer.errors, DeviceGroup))

        return result

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

    def delete(self, request, pk):
        queryset = self._get_queryset(request)
        group = get_object_or_404(queryset, pk=pk)
        group.delete()
        return self._response({'message': 'Device group was deleted',
                               'data': self._serializer_classes.get('retrieve')(group).data})


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
def get_counts(request):
    return Response({'organizations': Organization.objects.count(),
                     'devices': Device.objects.count(),
                     'deviceGroups': DeviceGroup.objects.count(),
                     'employees': Employee.objects.count()})


class ReportType(Enum):
    EMPLOYEE = 'EMPLOYEE'
    DEPARTMENT = 'DEPARTMENT'
    ORGANIZATION = 'ORGANIZATION'
    DEVICE = 'DEVICE'
    DEVICE_GROUP = 'DEVICE_GROUP'
    ALL = 'ALL'


def __get_report(request):
    login = _get_login(request)

    entity_id = _get_request_param(request, 'id', True)
    entity_type = ReportType(_get_request_param(request, 'type'))

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

    employees_queryset = Employee.objects.all()
    if login.role == Login.CONTROLLER:
        employees_queryset = employees_queryset.filter(
            organization_id=login.organization_id)

    name = None
    employees_ids = None
    if (entity_id is not None):
        if entity_type == ReportType.EMPLOYEE:
            employees_ids = {entity_id}
            name = 'employee '
        elif entity_type == ReportType.DEPARTMENT:
            employees_ids = Employee.objects.filter(id__in=Employee2Department.objects.filter(
                department_id=entity_id).values_list('employee_id', flat=True))
            name = 'department '
        elif entity_type == ReportType.ORGANIZATION:
            employees_queryset = employees_queryset.filter(
                organization_id=entity_id)
            name = 'organization '
        elif entity_type == ReportType.DEVICE:
            employees_ids = EmployeeRequest.objects.filter(
                device_id=entity_id).values_list('employee_id', flat=True)
            device = Device.objects.get(id=entity_id)
            name = 'device '

        name += entity_id
    else:
        name = 'full'

    if employees_ids is None:
        employees_ids = set(employees_queryset.values_list('id', flat=True))

    result = {}
    report_queryset = EmployeeRequest.objects.filter(
        employee_id__in=set(employees_ids)).order_by('-moment')

    if start_date is not None:
        report_queryset = report_queryset.filter(moment__gte=start_date)
    if end_date is not None:
        report_queryset = report_queryset.filter(moment__lte=end_date)
    if entity_type == 'device':
        report_queryset = report_queryset.filter(device_id=entity_id)

    paginated_report_queryset = None
    if (page is None) or (perPage is None):
        paginated_report_queryset = report_queryset
    else:
        offset = int(page) * int(perPage)
        limit = offset + int(perPage) * int(page_count)
        paginated_report_queryset = report_queryset[offset:limit]

    result.update(
        {'queryset': paginated_report_queryset, 'name': name})
    result.update(count=report_queryset.count())

    return result


@api_view(['GET'])
def get_report_file(request):
    report_data = __get_report(request)
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


@api_view(['GET'])
def get_report(request):
    login = _get_login(request)

    show_organization = 'showorganization' in request.GET
    entity_id = _get_request_param(request, 'id', True)
    entity_type = ReportType(_get_request_param(request, 'type'))
    show_department = (entity_type == ReportType.DEPARTMENT) and (
        entity_id is not None)
    show_device = 'showdevice' in request.GET

    report_data = __get_report(request)
    report_queryset = report_data.get('queryset')

    result = {}

    employees_ids = set(report_queryset.values_list('employee_id', flat=True))
    employees_queryset = Employee.objects.filter(
        id__in=employees_ids)

    result.update(employees=__get_objects_by_id(
        EmployeeSerializers.ModelSerializer, queryset=employees_queryset))

    if show_organization:
        if login.role == Login.CONTROLLER:
            result.update(organizations={
                login.organization_id: OrganizationSerializers.ModelSerializer(
                    Organization.objects.get(pk=login.organization_id)).data})
        elif login.role == Login.ADMIN:
            organizations_ids = set(
                employees_queryset.values_list('organization_id', flat=True))
            result.update({
                'organizations': _get_organizations_by_id(organizations_ids)})

    if show_department:
        result.update({'department': DepartmentSerializers.ModelSerializer(
            Department.objects.get(id=entity_id)).data})

    if show_device:
        devices_ids = set(report_queryset.values_list('device_id', flat=True))
        result.update(devices=__get_objects_by_id(
            DeviceSerializers.ModelSerializer, clazz=Device, ids=devices_ids))

    result.update(count=report_data.get('count'))

    result.update(data=EmployeeRequestSerializer(
        report_queryset, many=True).data)

    return Response(result)


def __get_objects_by_id(serializer, queryset=None, ids=None, clazz=None):
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
    return __get_objects_by_id(OrganizationSerializers.ModelSerializer, clazz=Organization, ids=ids)


def _get_relates(slave_clazz,
                 slave_key,
                 relation_clazz,
                 master_key,
                 master_id,
                 intersections=True):
    result = {}

    related_object_ids = relation_clazz.objects.filter(
        Q(**{master_key: master_id})).values_list(slave_key, flat=True)

    queryset = None
    if intersections:
        queryset = slave_clazz.objects.filter(id__in=related_object_ids)
    else:
        queryset = slave_clazz.objects.exclude(id__in=related_object_ids)

    return queryset


def _get_relation_key(clazz):
    result = None
    if clazz is Organization:
        result = 'organization_id'
    elif clazz is Device:
        result = 'device_id'
    elif clazz is DeviceGroup:
        result = 'device_group_id'

    return result


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

    return result if result is not None else (_get_relation_clazz(clazz2, clazz1, False) if swap_if_undefined else result)


def _get_login(request):
    return Login.objects.get(user=request.user)


_ENTRY2CLAZZ_N_SERIALIZER = {
    'devices': {'clazz': Device, 'serializer': DeviceSerializers.ModelSerializer},
    'deviceGroups': {'clazz': DeviceGroup, 'serializer': DeviceGroupSerializers.ModelSerializer},
    'organizations': {'clazz': Organization, 'serializer': OrganizationSerializers.ModelSerializer},
    'employees': {'clazz': Employee, 'serializer': EmployeeSerializers.ModelSerializer},
    'departments': {'clazz': Department, 'serializer': DepartmentSerializers.ModelSerializer},
}


def _get_clazz_n_serializer_by_entry_name(name, is_many=False):
    name = name[:1].lower() + name[1:] if name else ''
    return _ENTRY2CLAZZ_N_SERIALIZER.get(name + ('' if is_many else 's'), None)


def _add_or_remove_relations(request, master_name, master_id, slave_name, adding_mode=True):
    master_clazz = _get_clazz_n_serializer_by_entry_name(
        master_name, True).get('clazz')
    slave_clazz = _get_clazz_n_serializer_by_entry_name(
        slave_name).get('clazz')

    login = _get_login(request)
    success = []
    failure = []

    master_key = _get_relation_key(master_clazz)
    slave_key = _get_relation_key(slave_clazz)
    relation_clazz = _get_relation_clazz(master_clazz, slave_clazz)

    exists_ids = _get_relates(slave_clazz, slave_key, relation_clazz,
                              master_key, master_id).values_list('id', flat=True)

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


@api_view(['POST'])
def add_relation(request, master_name, master_id, slave_name):
    return _add_or_remove_relations(request, master_name, master_id, slave_name, True)


@api_view(['POST'])
def remove_relation(request, master_name, master_id, slave_name):
    return _add_or_remove_relations(request, master_name, master_id, slave_name, False)


@api_view(['GET'])
def get_non_related(request, master_name, master_id, slave_name):
    result = {}

    master_clazz = _get_clazz_n_serializer_by_entry_name(
        master_name, True).get('clazz')
    slave_info = _get_clazz_n_serializer_by_entry_name(slave_name)

    master_key = _get_relation_key(master_clazz)
    slave_key = _get_relation_key(slave_info.get('clazz'))
    relation_clazz = _get_relation_clazz(master_clazz, slave_info.get('clazz'))

    queryset = _get_relates(slave_info.get('clazz'), slave_key,
                            relation_clazz, master_key, master_id, False)

    result.update(data=slave_info.get('serializer')(queryset, many=True).data)

    return Response(result)
