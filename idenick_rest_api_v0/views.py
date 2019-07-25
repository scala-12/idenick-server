from abc import abstractmethod
from enum import Enum

from django.http import FileResponse

from django.contrib.auth.models import User
from django.db.models.expressions import Value
from django.db.models.functions.text import Concat
from django.db.models.query_utils import Q
from django.shortcuts import get_object_or_404
from rest_framework import viewsets, status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from idenick_app.models import Organization, Department, Employee, Employee2Department, \
    Login, EmployeeRequest
import idenick_rest_api_v0
from idenick_rest_api_v0.serializers import OrganizationSerializers, DepartmentSerializers, \
     LoginSerializer, UserSerializer, EmployeeSerializers, EmployeeRequestSerializer
from django.http.request import QueryDict
from datetime import datetime, timedelta
import xlsxwriter
import io


class ErrorMessage(Enum):
    UNIQUE_DEPARTMENT_NAME = 'Подразделение с таким названием уже существует'


# from rest_framework.permissions import IsAuthen
class _AbstractViewSet(viewsets.ViewSet):
        
    def _response(self, data, status=status.HTTP_200_OK):
        return Response(data, headers={'Access-Control-Allow-Origin': '*', 'Content-Type': 'application/json'}, status=status)
    
    def _response4update_n_create(self, code=status.HTTP_200_OK, data=None, message=None):
        result = None
        if (data == None):
            result = Response({'message': message, 'success': False}, headers={'Access-Control-Allow-Origin': '*', 'Content-Type': 'application/json'}, status=(status.HTTP_400_BAD_REQUEST if (code == status.HTTP_200_OK) else code))
        else:
            result = Response({'data': self._serializer_classes.get('retrieve')(data).data, 'success': True}, headers={'Access-Control-Allow-Origin': '*', 'Content-Type': 'application/json'}, status=code)
        return result

    def get_serializer_class(self):
        return self._serializer_classes[self.action]
    
    def _list_data(self, request, queryset=None):
        _queryset = self._get_queryset(request) if (queryset == None) else queryset
        serializer = self.get_serializer_class()(_queryset, many=True) 
        return {'data': serializer.data}
    
    def _retrieve(self, request, pk=None, queryset=None):
        return self._response(self._retrieve_data(request, pk, queryset))
    
    def _retrieve_data(self, request, pk=None, queryset=None):
        _queryset = self._get_queryset(request) if (queryset == None) else queryset
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
                    if (err.code == 'unique') and (object_class == Department):
                        err_prefix = 'Название: '
                        sub_msg = 'Подразделение с таким названием уже существует'
                    else:
                        sub_msg = err.capitalize()
                else:
                    sub_msg = err.capitalize()

                sub_err.append(sub_msg)
            
            sub_err_str = ', '.join(sub_err)
            if (field != 'non_field_errors'):
                err_prefix = None
                if (update_verbose):
                    verbose_name = str(object_class._meta.get_field(field).verbose_name)
                    verbose_end = ''
                    if (verbose_name.endswith('е')):
                        verbose_end = 'м'
                        
                    sub_err_str = sub_err_str.replace(verbose_name, verbose_name + verbose_end)
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
        
        return {'update':update, 'serializer':serializer}

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
        name_filter = request.GET.get('name', None)
        if (name_filter != None) and (name_filter != ''):
            queryset = queryset.filter(name__icontains=name_filter)
        
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
            result = self._response4update_n_create(data=organization, code=status.HTTP_201_CREATED)
        else:   
            result = self._response4update_n_create(message=self._get_validation_error_msg(serializer.errors, Organization))
            
        return result
    
    def partial_update(self, request, pk=None):
        organization = get_object_or_404(Organization.objects.all(), pk=pk)
        
        serializer_class = self.get_serializer_class()
        result = None
        
        valid_result = self._validate_on_update(pk, serializer_class, Organization, request.data)
        serializer = valid_result.get('serializer')
        update = valid_result.get('update')
        if update != None:
            organization.name = update.name
            organization.address = update.address
            organization.phone = update.phone
            organization.save()
            result = self._response4update_n_create(data=organization)
        else:
            result = self._response4update_n_create(message=self._get_validation_error_msg(serializer.errors, Organization))
        
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
        login = Login.objects.get(user=request.user)
        result = None
        role = login.role
        if (role == Login.ADMIN):
            result = Department.objects.all()
        elif (role == Login.CONTROLLER) or (role == Login.REGISTRATOR):
            result = Department.objects.filter(organization=login.organization)
        return result

    def list(self, request):
        queryset = self._get_queryset(request)
        name_filter = request.GET.get('name', None)
        if (name_filter != None) and (name_filter != ''):
            queryset = queryset.filter(name__icontains=name_filter)
        
        employee_filter = request.GET.get('employee', None)
        if (employee_filter != None) and (employee_filter != ''):
            queryset = queryset.filter(id__in=Employee2Department.objects.filter(employee_id=int(employee_filter)).values_list('department_id', flat=True))
        
        result = self._list_data(request, queryset)
        
        if (request.GET.__contains__('showorganization')):
            organizations_ids = set(map(lambda d: d.get('organization'), result.get('data')))
            organizations_queryset = Organization.objects.filter(id__in=organizations_ids)
            organizations = map(lambda i: OrganizationSerializers.ModelSerializer(i).data, organizations_queryset)
            organizations_by_id = {}
            for o in organizations:
                organizations_by_id.update({o.get('id'): o})
            
            result.update({'organizations': organizations_by_id})

        return self._response(result)
    
    def retrieve(self, request, pk=None):
        result = self._retrieve_data(request, pk)
        
        if (request.GET.__contains__('showorganization')):
            result.update({'organization': OrganizationSerializers.ModelSerializer(Organization.objects.get(id=result.get('data',).get('organization'))).data})
        
        return self._response(result)
    
    def create(self, request):
        serializer_class = self.get_serializer_class()
        
        department_data = QueryDict('', mutable=True)
        department_data.update(request.data)
        department_data.update({'organization': Login.objects.get(user=request.user).organization_id})
        serializer = serializer_class(data=department_data)
        result = None
        
        if serializer.is_valid():
            department = Department(**serializer.data)
            if Department.objects.filter(name=department.name).exists():
                result = self._response4update_n_create(message=ErrorMessage.UNIQUE_DEPARTMENT_NAME.value)
            else:
                department.save()
                result = self._response4update_n_create(data=department, code=status.HTTP_201_CREATED)
        else:   
            result = self._response4update_n_create(message=self._get_validation_error_msg(serializer.errors, Department))
            
        return result
    
    def partial_update(self, request, pk=None):
        department = get_object_or_404(self._get_queryset(request), pk=pk)
        
        serializer_class = self.get_serializer_class()
        result = None
        
        department_data = QueryDict('', mutable=True)
        department_data.update(request.data)
        organization_id = {'organization': Login.objects.get(user=request.user).organization_id}
        department_data.update(organization_id)
        
        valid_result = self._validate_on_update(pk, serializer_class, Department, department_data, organization_id)
        serializer = valid_result.get('serializer')
        update = valid_result.get('update')
        if update != None:
            department.name = update.name
            department.rights = update.rights
            department.address = update.address
            department.description = update.description
            department.save()
            result = self._response4update_n_create(data=department)
        else:
            result = self._response4update_n_create(message=self._get_validation_error_msg(serializer.errors, Department))
        
        return result
    
    def _alternative_valid(self, pk, data, errors, extra):
        return (len(errors.keys()) == 1) and errors.keys().__contains__('non_field_errors') and (errors.get('non_field_errors')[0].code == 'unique') and not Department.objects.filter(Q(name=data.get('name')) & Q(organization_id=extra.get('organization'))).filter(~Q(id=pk)).exists()
    
    def delete(self, request, pk):
        queryset = Department.objects.all()
        department = get_object_or_404(queryset, pk=pk)
        department.delete()
        return self._response({'message': 'Department was deleted', 'data': self._serializer_classes.get('retrieve')(department).data})


# for controller
class EmployeeSets:

    class _AbstractEmployeeViewSet(_AbstractViewSet):
        _serializer_classes = {
            'list': EmployeeSerializers.ModelSerializer,
            'retrieve': EmployeeSerializers.ModelSerializer,
            'create': EmployeeSerializers.CreateSerializer,
            'partial_update': EmployeeSerializers.CreateSerializer,
        }
        
        def _get_queryset(self, request, department_id=None, not_in=False):
            login = Login.objects.get(user=request.user)
    
            result = None
            if (login.role == Login.CONTROLLER):
                filtered_employees = Employee2Department.objects.filter(department__organization=login.organization)
                if (department_id != None):
                    filtered_employees = filtered_employees.filter(department_id=department_id)
                employees_ids = filtered_employees.values_list('employee_id', flat=True)
                result = Employee.objects.filter(id__in=employees_ids)
            elif (login.role == Login.REGISTRATOR):
                organization_employees = Employee.objects.filter(organization=login.organization)
                if (department_id != None):
                    all_employees_ids = organization_employees.values_list('id', flat=True)
                    employees_ids = Employee2Department.objects.filter(employee_id__in=all_employees_ids).filter(department_id=department_id).values_list('employee_id', flat=True)
                    if (not_in):
                        result = Employee.objects.filter(~Q(id__in=employees_ids))
                    else:
                        result = Employee.objects.filter(id__in=employees_ids)
                else:
                    result = organization_employees
            
            return result
        
        def _withExtra(self, request, department_id=None):
            result = {}
            if (request.GET.__contains__('showorganization')):
                login = Login.objects.get(user=request.user)
                organization = OrganizationSerializers.ModelSerializer(login.organization).data
                
                result = {'organization': organization}
                if department_id != None:
                    result.update({'department': DepartmentSerializers.ModelSerializer(Department.objects.get(pk=department_id)).data})
            
            return result
        
        def _list_employees(self, request, queryset, department_id=None):
            name_filter = request.GET.get('name', None)
            if (name_filter != None) and (name_filter != ''):
                queryset = queryset.annotate(
                full_name=Concat('last_name', Value(' '), 'first_name', Value(' '), 'patronymic'),
            ).filter(Q(full_name__icontains=name_filter) | Q(last_name__icontains=name_filter) | Q(first_name__icontains=name_filter) | Q(patronymic__icontains=name_filter))
            
            result = self._list_data(request, queryset)
            result.update(self._withExtra(request, department_id))
            
            return self._response(result)
        
        def _retrieve_employee(self, request, pk, department_id=None):
            result = self._retrieve_data(request, pk, self._get_queryset(request, department_id))
            result.update(self._withExtra(request, department_id))
            
            employee_full = EmployeeSerializers.FullModelSerializer(Employee.objects.get(pk=result.get('data').get('id'))).data
            if (request.GET.__contains__('showdepartments')):
                result.update({'departments': map(lambda i: i.get('department'), employee_full.get('departments'))})
            
            return self._response(result)
    
    class SimpleViewSet(_AbstractEmployeeViewSet):
        
        def partial_update(self, request, pk=None):
            queryset = Employee.objects.all()
            employee = get_object_or_404(queryset, pk=pk)
            
            serializer_class = self.get_serializer_class()
            serializer = serializer_class(data=request.data)
            result = None
            login = Login.objects.get(user=request.user)
            if serializer.is_valid() and (login.organization.id == employee.organization_id):
                data = serializer.data
                employee.last_name = data.get('last_name', employee.last_name)
                employee.first_name = data.get('first_name', employee.first_name)
                employee.patronymic = data.get('patronymic', employee.patronymic)
                employee.save()

                departments_ids = request.data.getlist('departments', [])
                departments = Department.objects.filter(organization_id=employee.organization_id).filter(id__in=departments_ids)
                for department in departments:
                    Employee2Department.objects.create(employee=employee, department=department)
                    
                result = self._response4update_n_create(data=employee)
            
            return result

        def list(self, request):
            return self._list_employees(request, self._get_queryset(request))

        def retrieve(self, request, pk):
            return self._retrieve_employee(request, pk)
        
        def create(self, request):
            serializer_class = self.get_serializer_class()
            serializer = serializer_class(data=request.data)
            result = None
            
            login = Login.objects.get(user=request.user)
            if serializer.is_valid() and (login.role == Login.REGISTRATOR):
                employee = Employee(**serializer.data)
                employee.organization = login.organization
                employee.save()
                    
                departments_ids = request.data.getlist('departments', [])
                departments = Department.objects.filter(organization_id=employee.organization_id).filter(id__in=departments_ids)
                for department in departments:
                    Employee2Department.objects.create(employee=employee, department=department)
                    
                result = self._response4update_n_create(data=employee, code=status.HTTP_201_CREATED)
            else:   
                result = self._response4update_n_create(message=self._get_validation_error_msg(serializer.errors, Employee))
                
            return result
        
        def delete(self, request, pk):
            queryset = Employee.objects.all()
            employee = get_object_or_404(queryset, pk=pk)
            employee.delete()
            return self._response({'message': 'Employee was deleted', 'data': self._serializer_classes.get('retrieve')(employee).data})
        
    class ByDepartmentViewSet(_AbstractEmployeeViewSet):

        def list(self, request, department_id):
            queryset = None
            if (request.path_info.endswith(idenick_rest_api_v0.urls.OTHER_EMPLOYEES) or
                request.path_info.endswith(idenick_rest_api_v0.urls.OTHER_EMPLOYEES + '/')):
                queryset = self._get_queryset(request, department_id, True)
            else:
                queryset = self._get_queryset(request, department_id)
                
            return self._list_employees(request, queryset, department_id)

        def retrieve(self, request, department_id, pk):
            return self._retrieve_employee(request, pk, department_id)


class _UserViewSet(_AbstractViewSet):
    _serializer_classes = {
        'list': LoginSerializer.FullSerializer,
        'retrieve': LoginSerializer.FullSerializer,
        'create': LoginSerializer.CreateSerializer,
        'partial_update': LoginSerializer.UpdateSerializer,
    }
    
    @abstractmethod
    def _user_role(self):
        pass
    
    def _get_queryset(self, request, organization_id=None):
        result = Login.objects.filter(role=self._user_role())
        if (organization_id == None):
            login = Login.objects.get(user=request.user)
            if (login.role == Login.REGISTRATOR):
                result = result.filter(organization__id=login.organization_id)
        else:
            result = result.filter(organization__id=organization_id)

        return result

    def list(self, request, organization_id=None):
        queryset = self._get_queryset(request, organization_id=organization_id)
        name_filter = request.GET.get('name', None)
        users_ids = None
        if (name_filter != None) and (name_filter != ''):
            users_ids = set(map(lambda i: UserSerializer(i).data.get('id'), User.objects.annotate(
                full_name_1=Concat('last_name', Value(' '), 'first_name'),
                full_name_2=Concat('first_name', Value(' '), 'last_name'),
            ).filter(Q(full_name_1__icontains=name_filter) | Q(full_name_2__icontains=name_filter) | Q(last_name__icontains=name_filter) | Q(first_name__icontains=name_filter))))
            queryset = queryset.filter(user_id__in=users_ids)
        
        result = self._list_data(request, queryset)
        
        if (request.GET.__contains__('showorganization')):
            organizations_ids = set(map(lambda d: d.get('organization'), result.get('data')))
            organizations_queryset = Organization.objects.filter(id__in=organizations_ids)
            organizations = map(lambda i: OrganizationSerializers.ModelSerializer(i).data, organizations_queryset)
            organizations_by_id = {}
            for o in organizations:
                organizations_by_id.update({o.get('id'): o})
            
            result.update({'organizations': organizations_by_id})
        
        return self._response(result)
    
    def _retrieve_user(self, request, organization_id=None, pk=None):
        result = self._retrieve_data(request=request, pk=pk, queryset=self._get_queryset(request, organization_id=organization_id))
        if (request.GET.__contains__('showorganization')):
            result.update({'organization': OrganizationSerializers.ModelSerializer(Organization.objects.get(id=result.get('data').get('organization'))).data})
            
        return self._response(result)
    
    def _create(self, request, organization_id):
        serializer_class = self.get_serializer_class()
        serializer = serializer_class(data=request.data)
        result = None
        
        if serializer.is_valid():
            user_data = User(**serializer.data)
            if user_data.username and user_data.password:
                user = User.objects.create_user(username=user_data.username, password=user_data.password)
                if (user_data.last_name):
                    user.last_name = user_data.last_name
                if (user_data.first_name):
                    user.first_name = user_data.first_name
                user.save()
                
                login = Login.objects.get(user=user)
                login.organization = Organization.objects.get(id=organization_id)
                login.role = self._user_role()
                login.save()
                result = self._response4update_n_create(data=login, code=status.HTTP_201_CREATED)
            else:
                result = self._response4update_n_create(message='Name is empty')
        else:   
            result = self._response4update_n_create(message=self._get_validation_error_msg(serializer.errors, User, True))
            
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


# for admin
class RegistratorViews:

    class ByOrganizationViewSet(_UserViewSet):

        def _user_role(self):
            return Login.REGISTRATOR
        
        def create(self, request, organization_id):
            return self._create(request, organization_id)

    class SimpleViewSet(_UserViewSet):

        def _user_role(self):
            return Login.REGISTRATOR
        
        def retrieve(self, request, pk=None):
            return self._retrieve_user(request, organization_id=None, pk=pk)
        
        def partial_update(self, request, pk=None):
            return self._partial_update(request, pk)


# for registrator
class ControllerViews:

    class ByOrganizationViewSet(_UserViewSet):

        def _user_role(self):
            return Login.CONTROLLER

    class SimpleViewSet(_UserViewSet):

        def _user_role(self):
            return Login.CONTROLLER
        
        def create(self, request):
            return self._create(request, Login.objects.get(user=request.user).organization_id)
        
        def retrieve(self, request, pk=None):
            return self._retrieve_user(request, Login.objects.get(user=request.user).organization_id, pk)
        
        def partial_update(self, request, pk=None):
            return self._partial_update(request, pk)


@api_view(['GET'])
def get_current_user(request):
    user = request.user
    
    response = None
    if (user.is_authenticated):
        response = LoginSerializer.FullSerializer(Login.objects.get(user=user)).data
    else:
        response = None
    
    return Response({'data': response})


def __get_report(request):
    login = Login.objects.get(user=request.user)

    start_date = datetime.strptime(request.GET.get('start'), "%Y%m%d")
    end_date = datetime.strptime(request.GET.get('end'), "%Y%m%d") + timedelta(days=1, microseconds=-1)
    employee_id = request.GET.get('employee', None)
    
    report_type = None
    result = {}
    queryset = EmployeeRequest.objects.filter(Q(employee__organization_id=login.organization_id) & Q(moment__range=(start_date, end_date)))
    if employee_id is None:
        department_id = request.GET.get('department', None)
        if department_id is None:
            report_type = 'by organization ' + login.organization.name
        else:
            department_employees = Employee2Department.objects.filter(department_id=department_id)
            queryset = queryset.filter(employee_id__in=department_employees.values_list('department_id', flat=True))
            department = Department.objects.get(pk=department_id)
            result.update({'department': DepartmentSerializers.ModelSerializer(department).data})
            report_type = 'by department' + department.name
    else:
        queryset = queryset.filter(employee_id=employee_id)
        employee = Employee.objects.get(id=employee_id)
        report_type = 'by employee' + employee.get_full_name()
    
    result.update({'queryset': queryset, 'type': report_type})
    
    return result

@api_view(['GET'])
def get_report_file(request):
    report_data = __get_report(request)

    output_file = io.BytesIO()
    workbook = xlsxwriter.Workbook(output_file, {'in_memory': True})
    worksheet = workbook.add_worksheet()

    queryset = report_data.get('queryset')
    row = 1
    for rl in queryset:
        worksheet.write(row, 0, rl.employee.get_full_name())
        worksheet.write(row, 1, rl.device.name)
        worksheet.write(row, 2, rl.moment.strftime('%Y-%m-%d %H:%M:%S'))
        worksheet.write(row, 3, rl.request_type)
        worksheet.write(row, 4, rl.response_type)
        worksheet.write(row, 5, rl.description)
        worksheet.write(row, 6, rl.algorithm_type)
        row += 1

    get_max_field_lenght_list = lambda f, caption=None: 4 + max(list(len(str(s)) for s in queryset.distinct().values_list(f, flat=True)) + [0 if caption == None else len(caption)])

    max_employee_name_lenght = 4 + max(list(map(lambda e: len(e.get_full_name()), Employee.objects.filter(id__in=queryset.distinct().values_list('employee', flat=True)))) + [len('Сотрудник')])
    worksheet.write(0, 0, 'Сотрудник')
    worksheet.set_column(0, 0,  max_employee_name_lenght)
    worksheet.write(0, 1, 'Устройство')
    worksheet.set_column(1, 1,  get_max_field_lenght_list('device__name', 'Устройство'))
    worksheet.write(0, 2, 'Дата')
    worksheet.set_column(2, 2,  23)
    worksheet.write(0, 3, 'Запрос')
    worksheet.set_column(3, 3,  get_max_field_lenght_list('request_type', 'Запрос'))
    worksheet.write(0, 4, 'Ответ')
    worksheet.set_column(4, 4,  get_max_field_lenght_list('response_type', 'Ответ'))
    worksheet.write(0, 5, 'Описание')
    worksheet.set_column(5, 5,  get_max_field_lenght_list('description', 'Описание'))
    worksheet.write(0, 6, 'Алгоритм')
    worksheet.set_column(6, 6,  get_max_field_lenght_list('algorithm_type', 'Алгоритм'))

    workbook.close()

    output_file.seek(0)

    file_name = 'Report ' + report_data.get('type') + ' ' + datetime.now().strftime('%Y_%m_%d') + '.xlsx'

    response = FileResponse(streaming_content=output_file, as_attachment=True, filename=file_name, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Access-Control-Allow-Headers'] = 'Content-Type'

    return response

@api_view(['GET'])
def get_report(request):
    report_data = __get_report(request)
    result = {'data': EmployeeRequestSerializer(report_data.get('queryset'), many=True).data}

    if (request.GET.__contains__('full')):
        report_data.update(organization=OrganizationSerializers.ModelSerializer(Organization.objects.get(pk=login.organization_id)).data)
        
        employees_ids = report_data.get('employees')
        employees_queryset = Employee.objects.filter(id__in=employees_ids)
        employees = map(lambda i: EmployeeSerializers.ModelSerializer(i).data, employees_queryset)
        employees_by_id = {}
        for o in employees:
            employees_by_id.update({o.get('id'): o})
        
        result.update(employees=employees_by_id)
    
    return Response(result)

@api_view(['POST'])
def add_employees(request, department_id):
    return _add_or_remove_employees(request, department_id, True)


@api_view(['POST'])
def remove_employees(request, department_id):
    return _add_or_remove_employees(request, department_id, False)


def _add_or_remove_employees(request, department_id, do_add):
    login = Login.objects.get(user=request.user)
    success = []
    failure = []
    if (login.role == Login.REGISTRATOR):
        exitst_employees = set(Employee2Department.objects.filter(department_id=department_id).values_list('employee_id', flat=True))
        getted_employees = set(map(lambda i: int(i), set(request.POST.get('ids').split(','))))
        
        success = None
        if do_add:
            success = getted_employees.difference(exitst_employees)
            for e_id in success:
                Employee2Department.objects.create(employee_id=e_id, department_id=department_id)
        else:
            success = getted_employees.intersection(exitst_employees)
            Employee2Department.objects.filter(department_id=department_id).filter(employee_id__in=success).delete()
        failure = getted_employees.difference(success)
    
    return Response({'data': {'success': success, 'failure': failure}})
