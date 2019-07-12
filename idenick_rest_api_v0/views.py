from abc import abstractmethod

from django.contrib.auth.models import User
from django.db.models.query_utils import Q
from django.shortcuts import get_object_or_404
from rest_framework import viewsets, status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from idenick_app.models import Organization, Department, Employee, Employee2Department, \
    Login
from idenick_rest_api_v0.serializers import OrganizationSerializers, DepartmentSerializers, EmployeeSerializer, LoginSerializer, UserSerializer
from enum import Enum


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
            for err in errors.get(field):
                sub_msg = err.capitalize()
                verbose_name = object_class._meta.get_field(field).verbose_name
                if (update_verbose):
                    verbose_end = ''
                    if (verbose_name.endswith('е')):
                        verbose_end = 'м'
                        
                    sub_msg = sub_msg.replace(verbose_name, verbose_name + verbose_end)
                sub_err.append(sub_msg)
            msg_arr.append(verbose_name.capitalize() + ': ' + ', '.join(sub_err))
        
        return '\n'.join(msg_arr).replace('.,', ',')


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
        
        valid_result = self._validate_on_update(pk, serializer_class, request.data)
        
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
    
    def _validate_on_update(self, pk, serializer_class, data):
        update = None
        serializer = serializer_class(data=data)
        if (serializer.is_valid()):
            update = Organization(**serializer.data)
        elif (len(serializer.errors.keys()) == 1) and serializer.errors.keys().__contains__('name') and (serializer.errors.get('name')[0].code == 'unique') and not Organization.objects.filter(name=data.get('name')).filter(~Q(id=pk)).exists():
            serializer = serializer_class(data)
            update = Organization(**serializer.data)
        
        return {'update':update, 'serializer':serializer}
        
    
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
        'partial_update': DepartmentSerializers.UpdateSerializer,
    }
    
    def _get_queryset(self, request):
        login = Login.objects.get(user=request.user)
        result = None
        role = login.role
        if (role == Login.SUPERUSER) or (role == Login.ADMIN):
            result = Department.objects.all()
        elif (role == Login.CONTROLLER) or (role == Login.REGISTRATOR):
            result = Department.objects.filter(organization=login.organization)
        return result

    def list(self, request):
        queryset = self._get_queryset(request)
        name_filter = request.GET.get('name', None)
        if (name_filter != None) and (name_filter != ''):
            queryset = queryset.filter(name__icontains=name_filter)
        
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
        serializer = serializer_class(data=request.data)
        result = None
        
        if serializer.is_valid():
            department = Department(**serializer.data, organization=Login.objects.get(user=request.user).organization)
            if Department.objects.filter(name=department.name).exists():
                result = self._response4update_n_create(message=ErrorMessage.UNIQUE_DEPARTMENT_NAME)
            else:
                department.save()
                result = self._response4update_n_create(data=department, code=status.HTTP_201_CREATED)
        else:   
            result = self._response4update_n_create(message=self._get_validation_error_msg(serializer.errors, Department))
            
        return result
    
    def partial_update(self, request, pk=None):
        department = get_object_or_404(self._get_queryset(request), pk=pk)
        
        serializer_class = self.get_serializer_class()
        serializer = serializer_class(data=request.data)
        result = None
        if serializer.is_valid():
            update = Department(**serializer.data)
            if update.name:
                exists = Department.objects.filter(organization__id=department.organization_id).filter(name=update.name).filter(~Q(id=department.id))
                if not exists.exists():
                    department.name = update.name
                    department.rights = update.rights
                    department.address = update.address
                    department.description = update.description
                    department.save()
                    result = self._response4update_n_create(data=department)
                else:
                    result = self._response4update_n_create(message='Name is not unique')
            else:
                result = self._response4update_n_create(message='Name is empty')
        
        return result
    
    def delete(self, request, pk):
        queryset = Department.objects.all()
        department = get_object_or_404(queryset, pk=pk)
        department.delete()
        return self._response({'message': 'Department was deleted', 'data': self._serializer_classes.get('retrieve')(department).data})


# for controller
class EmployeeSets:

    class _AbstractEmployeeViewSet(_AbstractViewSet):
        _serializer_classes = {
            'list': EmployeeSerializer.ModelSerializer,
            'retrieve': EmployeeSerializer.ModelSerializer,
            'create': EmployeeSerializer.CreateSerializer,
            'partial_update': EmployeeSerializer.CreateSerializer,
        }
        
        def _get_queryset(self, request):
            login = Login.objects.get(user=request.user)
    
            result = None
            department = request.query_params.get('department', None)
            employees_ids = None
            if login.role == Login.CONTROLLER:
                filtered_employees = Employee2Department.objects.filter(department__organization=login.organization)
                employees_ids = map(lambda e2o : e2o.employee_id, filtered_employees if (department == None) else filtered_employees.filter(department=department))
            elif login.role == Login.SUPERUSER:
                organization = request.query_params.get('organization', None)
                if not (organization is None):
                    employees_ids = map(lambda e2o : e2o.employee, Employee2Department.objects.filter(department__organization=organization))
                elif not (department is None):
                    employees_ids = map(lambda e2d : e2d.employee, Employee2Department.objects.all().filter(department=department))
                else:
                    result = Employee.objects.all()
            
            if result == None:
                result = Employee.objects.filter(id__in=employees_ids)
            
            return result
        
        def _withOrganization(self, request):
            result = {}
            if (request.GET.__contains__('showorganization')):
                login = Login.objects.get(user=request.user)
                department = request.query_params.get('department', None)
                
                organization_id = login.organization_id if (department == None) else department.organization_id
                organizations_queryset = Organization.objects.filter(id=organization_id)
                organizations = map(lambda i: OrganizationSerializers.ModelSerializer(i).data, organizations_queryset)
                organizations_by_id = {}
                for o in organizations:
                    organizations_by_id.update({o.get('id'): o})
                
                result = {'organizations': organizations_by_id}
            
            return result
    
    class SimpleViewSet(_AbstractEmployeeViewSet):

        def list(self, request):
            result = self._list_data(request, self._get_queryset(request))
            result.update(self._withOrganization(request))
            
            return self._response(result)
        
        def retrieve(self, request, pk=None):
            result = self._retrieve_data(request, pk, self._get_queryset(request))
            result.update(self._withOrganization(request))
            
            return self._response(result)
        
        def create(self, request):
            serializer_class = self.get_serializer_class()
            serializer = serializer_class(data=request.data)
            result = None
            
            if serializer.is_valid():
                employee = Employee(**serializer.data)
                employee.save()
                    
                departments = request.data.getlist('departments', None)
                if not departments is None:
                    for department_id in departments:
                        if Department.objects.filter(id=department_id).exists():
                            Employee2Department.objects.create(employee=employee, department=Department.objects.get(id=department_id))
                result = self._response({'data': self._serializer_classes.get('retrieve')(employee).data})
            else:   
                result = self._response4update_n_create(message=self._get_validation_error_msg(serializer.errors, Employee))
                
            return result
        
        def partial_update(self, request, pk=None):
            queryset = Employee.objects.all()
            employee = get_object_or_404(queryset, pk=pk)
            
            serializer_class = self.get_serializer_class()
            serializer = serializer_class(data=request.data)
            result = None
            if serializer.is_valid():
                data = serializer.data
                employee.surname = data.get('surname', employee.surname)
                employee.first_name = data.get('first_name', employee.first_name)
                employee.patronymic = data.get('patronymic', employee.patronymic)
                employee.save()
                departments = request.data.getlist('departments', None)
                Employee2Department.objects.filter(employee=employee).delete()
                if not departments is None:
                    for department_id in departments:
                        if Department.objects.filter(id=department_id).exists():
                            Employee2Department.objects.create(employee=employee, department=Department.objects.get(id=department_id))
                result = self._response({'data': self._serializer_classes.get('retrieve')(employee).data})
            
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
            users_ids = set(map(lambda i: UserSerializer(i).data.get('id'), User.objects.filter(Q(last_name__icontains=name_filter) | Q(first_name__icontains=name_filter))))
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
            result = self._response4update_n_create(message=self._get_validation_error_msg(serializer.errors, User, False))
            
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
