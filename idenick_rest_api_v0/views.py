from abc import abstractmethod

from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404
from rest_framework import viewsets, status
from rest_framework.response import Response

from idenick_app.models import Organization, Department, Employee, Employee2Department, \
    Login
from idenick_rest_api_v0.serializers import OrganizationSerializer, DepartmentSerializer, EmployeeSerializer, LoginSerializer


# from rest_framework.permissions import IsAuthen
class __AbstractViewSet(viewsets.ViewSet):

    def get_serializer_class(self):
        return self.serializer_classes[self.action]
    
    def _list(self, queryset):
        serializer = self.get_serializer_class()(queryset, many=True)
        return Response(serializer.data)
    
    def _retrieve(self, queryset, pk=None):
        entity = get_object_or_404(queryset, pk=pk)
        serializer = self.get_serializer_class()(entity)
        return Response(serializer.data)


# for admin
class OrganizationViewSet(__AbstractViewSet):
    serializer_classes = {
        'list': OrganizationSerializer.ShortSerializer,
        'retrieve': OrganizationSerializer.FullSerializer,
        'create': OrganizationSerializer.CreateSerializer,
        'partial_update': OrganizationSerializer.CreateSerializer,
    }

    def list(self, request):
        return self._list(Organization.objects.all())
    
    def retrieve(self, request, pk=None):
        return self._retrieve(Organization.objects.all(), pk)
    
    def create(self, request):
        serializer_class = self.get_serializer_class()
        serializer = serializer_class(data=request.data)
        result = None
        if serializer.is_valid():
            organization = Organization(**serializer.data)
            if organization.name:
                if Organization.objects.filter(name=organization.name).exists():
                    result = Response({'message': 'Name is not unique', 'status': status.HTTP_400_BAD_REQUEST})
                else:
                    organization.save()
                    result = Response({'data': self.serializer_classes.get('retrieve', None)(organization).data})
            else:
                result = Response({'message': 'Name is empty', 'status': status.HTTP_400_BAD_REQUEST})
            
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
                    result = Response({'data': self.serializer_classes.get('retrieve', None)(organization).data})
                else:
                    result = Response({'message': 'Name is not unique', 'status': status.HTTP_400_BAD_REQUEST})
            else:
                result = Response({'message': 'Name is empty', 'status': status.HTTP_400_BAD_REQUEST})
        
        return result
    
    def delete(self, request, pk):
        queryset = Organization.objects.all()
        organization = get_object_or_404(queryset, pk=pk)
        organization.delete()
        return Response({'message': 'Organization was deleted', 'data': self.serializer_classes.get('retrieve', None)(organization).data})


# for controller
# for register
class DepartmentViewSet(__AbstractViewSet):
    serializer_classes = {
        'list': DepartmentSerializer.ShortSerializer,
        'retrieve': DepartmentSerializer.FullSerializer,
        'create': DepartmentSerializer.CreateSerializer,
        'partial_update': DepartmentSerializer.UpdateSerializer,
    }

    def __get_queryset(self, request):
        login = Login.objects.get(user=request.user)
        result = None
        if login.type == Login.SUPERUSER:
            result = Department.objects.all()
        elif (login.type == Login.CONTROLLER) or (login.type == Login.REGISTRATOR):
            result = Department.objects.filter(organization=login.organization)
        return result

    def list(self, request):
        return self._list(self.__get_queryset(request))
    
    def retrieve(self, request, pk=None):
        return self._retrieve(self.__get_queryset(request), pk)
    
    def create(self, request):
        serializer_class = self.get_serializer_class()
        serializer = serializer_class(data=request.data)
        result = None
        
        if serializer.is_valid():
            department = Department(**serializer.data)
            if department.name and department.rights:
                if Department.objects.filter(name=department.name).exists():
                    result = Response({'message': 'Name is not unique', 'status': status.HTTP_400_BAD_REQUEST})
                else:
                    department.save()
                    result = Response({'data': self.serializer_classes.get('retrieve', None)(department).data})
            else:
                result = Response({'message': ('Name' if not department.name else 'Rights') + ' is empty', 'status': status.HTTP_400_BAD_REQUEST})
            
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
                    result = Response({'data': self.serializer_classes.get('retrieve', None)(department).data})
                else:
                    result = Response({'message': 'Name is not unique', 'status': status.HTTP_400_BAD_REQUEST})
            else:
                result = Response({'message': 'Name is empty', 'status': status.HTTP_400_BAD_REQUEST})
        
        return result
    
    def delete(self, request, pk):
        queryset = Department.objects.all()
        department = get_object_or_404(queryset, pk=pk)
        department.delete()
        return Response({'message': 'Department was deleted', 'data': self.serializer_classes.get('retrieve', None)(department).data})


# for controller
class EmployeeViewSet(__AbstractViewSet):
    serializer_classes = {
        'list': EmployeeSerializer.ShortSerializer,
        'retrieve': EmployeeSerializer.FullSerializer,
        'create': EmployeeSerializer.CreateSerializer,
        'partial_update': EmployeeSerializer.CreateSerializer,
    }
    
    def __get_queryset(self, request):
        login = Login.objects.get(user=request.user)

        result = None
        department = request.query_params.get('department', None)
        if login.type == Login.CONTROLLER:
            filtered_employees = Employee2Department.objects.filter(department__organization=login.organization)
            result = map(lambda e2o : e2o.employee, filtered_employees if (department == None) else filtered_employees.filter(department=department))
        elif login.type == Login.SUPERUSER:
            organization = request.query_params.get('organization', None)
            if not (organization is None):
                result = map(lambda e2o : e2o.employee, Employee2Department.objects.filter(department__organization=organization))
            elif not (department is None):
                result = map(lambda e2d : e2d.employee, Employee2Department.objects.all().filter(department=department))
            else:
                result = Employee.objects.all()
        
        return result

    def list(self, request):
        return self._list(self.__get_queryset(request))
    
    def retrieve(self, request, pk=None):
        return self._retrieve(self.__get_queryset(request), pk)
    
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
                result = Response({'data': self.serializer_classes.get('retrieve', None)(employee).data})
            else:
                result = Response({'message': 'Name is empty', 'status': status.HTTP_400_BAD_REQUEST})
            
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
            result = Response({'data': self.serializer_classes.get('retrieve', None)(employee).data})
        
        return result
    
    def delete(self, request, pk):
        queryset = Employee.objects.all()
        employee = get_object_or_404(queryset, pk=pk)
        employee.delete()
        return Response({'message': 'Employee was deleted', 'data': self.serializer_classes.get('retrieve', None)(employee).data})


class _UserViewSet(__AbstractViewSet):
    serializer_classes = {
        'list': LoginSerializer.ShortSerializer,
        'retrieve': LoginSerializer.ShortSerializer,
        'create': LoginSerializer.CreateSerializer,
        'partial_update': LoginSerializer.UpdateSerializer,
    }
    
    @abstractmethod
    def _user_type(self):
        pass
    
    def __get_queryset(self, organization_id):
        return Login.objects.filter(organization__id=organization_id).filter(type=self._user_type())

    def _list(self, request, organization_id):
        return super._list(self.__get_queryset(organization_id=organization_id))
    
    def _retrieve(self, request, organization_id, pk=None):
        return super._retrieve(self.__get_queryset(organization_id=organization_id), pk)
    
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
                login.type = self._user_type()
                login.save()
                result = Response({'data': self.serializer_classes.get('retrieve', None)(login).data})
            else:
                result = Response({'message': 'Name is empty', 'status': status.HTTP_400_BAD_REQUEST})
            
        return result


# for admin
class RegisterViewSets:
    class OrganizationViewSet(_UserViewSet):

        def _user_type(self):
            return Login.REGISTRATOR
        
        def list(self, request, organization_id):
            return self._list(request, organization_id)
        
        def create(self, request, organization_id):
            return self._create(request, organization_id)
    

    class SimpleViewSet(_UserViewSet):

        def _user_type(self):
            return Login.REGISTRATOR
        
        def retrieve(self, request, organization_id, pk=None):
            return self._retrieve(request, organization_id, pk)


# for register
class ControllerViewSets:
    class OrganizationViewSet(_UserViewSet):

        def _user_type(self):
            return Login.CONTROLLER
        
        def list(self, request, organization_id):
            return self._list(request, organization_id)
        
        def create(self, request, organization_id):
            return self._create(request, organization_id)
    

    class SimpleViewSet(_UserViewSet):

        def _user_type(self):
            return Login.CONTROLLER
        
        def retrieve(self, request, organization_id, pk=None):
            return self._retrieve(request, organization_id, pk)

