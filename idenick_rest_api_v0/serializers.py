from django.contrib.auth.models import User
from rest_framework import serializers

from idenick_app.models import Organization, Department, Employee, Login


class OrganizationSerializer(serializers.ModelSerializer):
    departments = serializers.PrimaryKeyRelatedField(many=True, read_only=True)

    class CreateSerializer(serializers.ModelSerializer):

        class Meta:
            model = Organization
            fields = [
                'name',
                'address',
                'phone',
            ]

    class Meta:
        model = Organization
        fields = [
            'id',
            'created_at',
            'dropped_at',
            'guid',
            'name',
            'address',
            'phone',
            'departments',
        ]


class DepartmentSerializer(serializers.ModelSerializer):
    employees = serializers.SlugRelatedField(
        many=True,
        read_only=True,
        slug_field='employee_id'
    )

    class CreateSerializer(serializers.ModelSerializer):

        class Meta:
            model = Department
            fields = [
                'name',
                'rights',
                'address',
                'description',
                'organization_id',
            ]

    class UpdateSerializer(serializers.ModelSerializer):

        class Meta:
            model = Department
            fields = [
                'name',
                'rights',
                'address',
                'description',
            ]

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
            'employees',
         ]
        
        
class OrganizationDepartmentIdsSerializer(serializers.ModelSerializer):
    id = serializers.ReadOnlyField(source='department.id')
    organization = serializers.ReadOnlyField(source='department.organization_id')
    
    class Meta:
        model = Department
        fields = [
            'id',
            'organization',
        ]
        
        
class EmployeeSerializer(serializers.ModelSerializer):
    departments = OrganizationDepartmentIdsSerializer(many=True, read_only=True)

    class CreateSerializer(serializers.ModelSerializer):

        class Meta:
            model = Employee
            fields = [
                'surname',
                'first_name',
                'patronymic',
            ]

    class Meta:
        model = Employee
        fields = [
            'id',
            'created_at',
            'dropped_at',
            'guid',
            'surname',
            'first_name',
            'patronymic',
			'departments',
        ]


class LoginSerializer(serializers.ModelSerializer):
    username = serializers.ReadOnlyField(source='user.username')
    first_name = serializers.ReadOnlyField(source='user.first_name')
    last_name = serializers.ReadOnlyField(source='user.last_name')
    is_active = serializers.ReadOnlyField(source='user.is_active')

    class CreateSerializer(serializers.ModelSerializer):

        class Meta:
            model = User
            fields = [
                'username',
                'first_name',
                'last_name',
                'password',
            ]

    class UpdateSerializer(serializers.ModelSerializer):

        class Meta:
            model = User
            fields = [
                'first_name',
                'last_name',
                'password',
            ]
    
    class Meta:
        model = Login
        fields = [
            'id',
            'get_type_display',
            'username',
            'first_name',
            'last_name',
            'is_active',
        ]
