from django.contrib.auth.models import User
from rest_framework import serializers

from idenick_app.models import Organization, Department, Employee, Login, \
    Employee2Department
from django.http.request import QueryDict


class UserSerializer(serializers.ModelSerializer):

    class Meta:
        model = User
        fields = [
            'id',
            'last_name',
            'first_name',
        ]


class OrganizationSerializers:

    class CreateSerializer(serializers.ModelSerializer):

        class Meta:
            model = Organization
            fields = [
                'name',
                'address',
                'phone',
            ]
    
    class ModelSerializer(serializers.ModelSerializer):
        departments_count = serializers.SerializerMethodField()
        controllers_count = serializers.SerializerMethodField()
        registrators_count = serializers.SerializerMethodField()
        
        def get_departments_count(self, obj):
            return Department.objects.filter(organization=obj).count()
        
        def get_controllers_count(self, obj):
            return Login.objects.filter(role=Login.CONTROLLER, organization=obj).count()
        
        def get_registrators_count(self, obj):
            return Login.objects.filter(role=Login.REGISTRATOR, organization=obj).count()

        class Meta:
            model = Organization
            fields = [
                'id',
                'created_at',
                'dropped_at',
                'name',
                'address',
                'phone',
                'departments_count',
                'controllers_count',
                'registrators_count',
            ]


class DepartmentSerializers:
    
    class CreateSerializer(serializers.ModelSerializer):

        class Meta:
            model = Department
            fields = [
                'name',
                'rights',
                'address',
                'description',
                'organization',
            ]
        
        def to_representation(self, obj):
            represent = QueryDict('', mutable=True)
            represent.update(obj)
            rights = obj.get('rights')
            represent.__setitem__('rights', 0 if (rights == '') else int(rights))
            represent.__setitem__('organization', Organization.objects.get(pk=int(obj.get('organization'))))
            
            return represent
    
    class ModelSerializer(serializers.ModelSerializer):
        employees_count = serializers.SerializerMethodField()
        
        def get_employees_count(self, obj):
            return Employee2Department.objects.filter(department=obj).count()

        class Meta:
            model = Department
            fields = [
                'id',
                'created_at',
                'dropped_at',
                'organization',
                'name',
                'rights',
                'address',
                'description',
                'employees_count',
             ]


class _DepartmentOfEmployeeSerializers(serializers.ModelSerializer):
    department = DepartmentSerializers.ModelSerializer()

    class Meta:
        model = Employee2Department
        fields = ['department']


class EmployeeSerializers():

    class CreateSerializer(serializers.ModelSerializer):

        class Meta:
            model = Employee
            fields = [
                'last_name',
                'first_name',
                'patronymic',
            ]
    
    class ModelSerializer(serializers.ModelSerializer):

        class Meta:
            model = Employee
            fields = [
                'id',
                'created_at',
                'dropped_at',
                'last_name',
                'first_name',
                'patronymic',
                'organization',
            ]
    
    class FullModelSerializer(serializers.ModelSerializer):
        departments = _DepartmentOfEmployeeSerializers(many=True)
#         departments = serializers.SerializerMethodField()
#         def get_departments(self, obj):
#             return DepartmentSerializers.ModelSerializer(Department.objects.filter(id__in=set(Employee2Department.objects.filter(employee_id=obj.id).values_list('department', flat=True))), many=True).data
        
        class Meta:
            model = Employee
            fields = [
                'id',
                'created_at',
                'dropped_at',
                'last_name',
                'first_name',
                'patronymic',
                'departments',
                'organization',
            ]


class LoginSerializer():

    class CreateSerializer(serializers.ModelSerializer):

        class Meta:
            model = User
            fields = [
                'username',
                'first_name',
                'last_name',
                'password',
                'email',
            ]

    class UpdateSerializer(serializers.ModelSerializer):

        class Meta:
            model = User
            fields = [
                'first_name',
                'last_name',
            ]
    
    class FullSerializer(serializers.ModelSerializer):
        username = serializers.ReadOnlyField(source='user.username')
        first_name = serializers.ReadOnlyField(source='user.first_name')
        last_name = serializers.ReadOnlyField(source='user.last_name')
        is_active = serializers.ReadOnlyField(source='user.is_active')
        role = serializers.ReadOnlyField(source='get_role_display')
        date_joined = serializers.ReadOnlyField(source='user.date_joined')
        
        class Meta:
            model = Login
            fields = [
                'id',
                'date_joined',
                'organization',
                'role',
                'username',
                'first_name',
                'last_name',
                'is_active',
            ]
