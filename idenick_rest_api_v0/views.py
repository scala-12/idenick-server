

from abc import abstractmethod

from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404
from rest_framework import viewsets, status
from rest_framework.response import Response

from idenick_app.models import Organization, Department, Employee, Employee2Department, \
    Login
from idenick_rest_api_v0.serializers import OrganizationSerializers, DepartmentSerializers, EmployeeSerializer, LoginSerializer
from rest_framework.decorators import api_view


# from rest_framework.permissions import IsAuthen
class _AbstractViewSet(viewsets.ViewSet):
    
    def _response(self, data, status=status.HTTP_200_OK):
        return Response(data, headers={'Access-Control-Allow-Origin': '*', 'Content-Type': 'application/json'}, status=status)

    def get_serializer_class(self):
        return self._serializer_classes[self.action]
    
    def _list(self, request, queryset=None):
        return self._response(self._list_data(request, queryset))
    
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
        return self._list(request)
    
    def retrieve(self, request, pk=None):
        return self._retrieve(request, pk)
    
    def create(self, request):
        serializer_class = self.get_serializer_class()
        serializer = serializer_class(data=request.data)
        result = None
        if serializer.is_valid():
            organization = Organization(**serializer.data)
            if organization.name:
                if Organization.objects.filter(name=organization.name).exists():
                    result = self._response({'message': 'Name is not unique'}, status=status.HTTP_400_BAD_REQUEST)
                else:
                    organization.save()
                    result = self._response({'data': self._serializer_classes.get('retrieve', None)(organization).data})
            else:
                result = self._response({'message': 'Name is empty'}, status=status.HTTP_400_BAD_REQUEST)
            
        return result
    
    def partial_update(self, request, pk=None):
        queryset = Organization.objects.all()
        organization = get_object_or_404(queryset, pk=pk)
        
        serializer_class = self.get_serializer_class()
        serializer = serializer_class(data=request.data)
        update = Organization(**serializer.data)
        result = None
        if serializer.is_valid():
            if update.name:
                exists = Organization.objects.filter(name=update.name)
                if not exists.exists() or exists.first().id != organization.id:
                    organization.name = update.name
                    organization.address = update.address
                    organization.phone = update.phone
                    organization.save()
                    result = self._response({'data': self._serializer_classes.get('retrieve', None)(organization).data})
                else:
                    result = self._response({'message': 'Name is not unique'}, status=status.HTTP_400_BAD_REQUEST)
            else:
                result = self._response({'message': 'Name is empty'}, status=status.HTTP_400_BAD_REQUEST)
        
        return result
    
    def delete(self, request, pk):
        queryset = Organization.objects.all()
        organization = get_object_or_404(queryset, pk=pk)
        organization.delete()
        return self._response({'message': 'Organization was deleted', 'data': self._serializer_classes.get('retrieve', None)(organization).data})


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
        if login.role == Login.SUPERUSER:
            result = Department.objects.all()
        elif (login.role == Login.CONTROLLER) or (login.role == Login.REGISTRATOR):
            result = Department.objects.filter(organization=login.organization)
        return result

    def list(self, request):
        result = self._list_data(request)
        
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
            department = Department(**serializer.data)
            if department.name and department.rights:
                if Department.objects.filter(name=department.name).exists():
                    result = self._response({'message': 'Name is not unique'}, status=status.HTTP_400_BAD_REQUEST)
                else:
                    department.save()
                    result = self._response({'data': self._serializer_classes.get('retrieve', None)(department).data})
            else:
                result = self._response({'message': ('Name' if not department.name else 'Rights') + ' is empty'}, status=status.HTTP_400_BAD_REQUEST)
            
        return result
    
    def partial_update(self, request, pk=None):
        queryset = Department.objects.all()
        department = get_object_or_404(queryset, pk=pk)
        
        serializer_class = self.get_serializer_class()
        serializer = serializer_class(data=request.data)
        update = Department(**serializer.data)
        result = None
        if serializer.is_valid():
            if update.name:
                exists = Department.objects.filter(name=update.name)
                if not exists.exists() or exists.first().id != department.id:
                    department.name = update.name
                    department.rights = update.rights
                    department.address = update.address
                    department.description = update.description
                    department.save()
                    result = self._response({'data': self._serializer_classes.get('retrieve', None)(department).data})
                else:
                    result = self._response({'message': 'Name is not unique'}, status=status.HTTP_400_BAD_REQUEST)
            else:
                result = self._response({'message': 'Name is empty'}, status=status.HTTP_400_BAD_REQUEST)
        
        return result
    
    def delete(self, request, pk):
        queryset = Department.objects.all()
        department = get_object_or_404(queryset, pk=pk)
        department.delete()
        return self._response({'message': 'Department was deleted', 'data': self._serializer_classes.get('retrieve', None)(department).data})


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
                if employee.first_name and employee.surname and employee.patronymic:
                    employee.save()
                    
                    departments = request.data.getlist('departments', None)
                    if not departments is None:
                        for department_id in departments:
                            if Department.objects.filter(id=department_id).exists():
                                Employee2Department.objects.create(employee=employee, department=Department.objects.get(id=department_id))
                    result = self._response({'data': self._serializer_classes.get('retrieve', None)(employee).data})
                else:
                    result = self._response({'message': 'Name is empty'}, status=status.HTTP_400_BAD_REQUEST)
                
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
                result = self._response({'data': self._serializer_classes.get('retrieve', None)(employee).data})
            
            return result
        
        def delete(self, request, pk):
            queryset = Employee.objects.all()
            employee = get_object_or_404(queryset, pk=pk)
            employee.delete()
            return self._response({'message': 'Employee was deleted', 'data': self._serializer_classes.get('retrieve', None)(employee).data})


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
        if (organization_id == None):
            login = Login.objects.get(user=request.user)
            organization_id = login.organization_id

        return Login.objects.filter(organization__id=organization_id).filter(role=self._user_role())

    def _user_list(self, request, organization_id=None):
        result = self._list_data(request, self._get_queryset(request, organization_id=organization_id))
        
        if (request.GET.__contains__('showorganization')):
            organizations_ids = set(map(lambda d: d.get('organization'), result.get('data')))
            organizations_queryset = Organization.objects.filter(id__in=organizations_ids)
            organizations = map(lambda i: OrganizationSerializers.ModelSerializer(i).data, organizations_queryset)
            organizations_by_id = {}
            for o in organizations:
                organizations_by_id.update({o.get('id'): o})
            
            result.update({'organizations': organizations_by_id})
        
        return self._response(result)
    
    def _retrieve(self, request, organization_id, pk=None):
        return super._retrieve(self._get_queryset(request, organization_id=organization_id), pk)
    
    def _create(self, request, organization_id):
        serializer_class = self.get_serializer_class()
        serializer = serializer_class(data=request.data)
        result = None
        
        if serializer.is_valid():
            user = User(**serializer.data)
            if user.username and user.password:
                user.save()
                login = Login.objects.get(user=user)
                login.organization = Organization.objects.get(id=organization_id)
                login.role = self._user_role()
                login.save()
                result = self._response({'data': self._serializer_classes.get('retrieve', None)(login).data})
            else:
                result = self._response({'message': 'Name is empty'}, status=status.HTTP_400_BAD_REQUEST)
            
        return result


# for admin
class RegistratorViews:

    class ByOrganizationViewSet(_UserViewSet):

        def _user_role(self):
            return Login.REGISTRATOR
        
        def list(self, request, organization_id):
            return self._user_list(request, organization_id)
        
        def create(self, request, organization_id):
            return self._create(request, organization_id)

    class SimpleViewSet(_UserViewSet):

        def _user_role(self):
            return Login.REGISTRATOR
        
        def list(self, request):
            return self._user_list(request)
        
        def retrieve(self, request, organization_id, pk=None):
            return self._retrieve(request, organization_id, pk)


# for registrator
class ControllerViews:

    class ByOrganizationViewSet(_UserViewSet):

        def _user_role(self):
            return Login.CONTROLLER
        
        def list(self, request, organization_id):
            return self._user_list(request, organization_id)
        
        def create(self, request, organization_id):
            return self._create(request, organization_id)

    class SimpleViewSet(_UserViewSet):

        def _user_role(self):
            return Login.CONTROLLER
        
        def list(self, request):
            return self._user_list(request)
        
        def retrieve(self, request, organization_id, pk=None):
            return self._retrieve(request, organization_id, pk)

@api_view(['GET'])
def get_current_user(request):
    user = request.user
    
    response = None
    if (user.is_authenticated):
        response = LoginSerializer.FullSerializer(Login.objects.get(user=user)).data
    else:
        response = None
    
    return Response({'data': response})