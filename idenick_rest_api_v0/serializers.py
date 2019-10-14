"""Serializers for models"""
from django.contrib.auth.models import User
from django.http.request import QueryDict
from rest_framework import serializers

from idenick_app.models import (Department, Device, Device2DeviceGroup,
                                Device2Organization, DeviceGroup,
                                DeviceGroup2Organization, Employee,
                                Employee2Department, Employee2Organization,
                                EmployeeRequest, Login, Organization)


class UserSerializer(serializers.ModelSerializer):
    """Serializer for user-model"""
    class Meta:
        model = User
        fields = [
            'id',
            'last_name',
            'first_name',
        ]


class OrganizationSerializers:
    """Serializers for organization-model"""
    class CreateSerializer(serializers.ModelSerializer):
        """Serializer for create organization-model"""
        class Meta:
            model = Organization
            fields = [
                'name',
                'address',
                'phone',
            ]

    class ModelSerializer(serializers.ModelSerializer):
        """Serializer for show organization-model"""
        departments_count = serializers.SerializerMethodField()
        controllers_count = serializers.SerializerMethodField()
        registrators_count = serializers.SerializerMethodField()
        employees_count = serializers.SerializerMethodField()
        devices_count = serializers.SerializerMethodField()
        device_groups_count = serializers.SerializerMethodField()

        def get_departments_count(self, obj):
            return Department.objects.filter(organization=obj).count()

        def get_controllers_count(self, obj):
            return Login.objects.filter(role=Login.CONTROLLER, organization=obj).count()

        def get_registrators_count(self, obj):
            return Login.objects.filter(role=Login.REGISTRATOR, organization=obj).count()

        def get_employees_count(self, obj):
            return Employee2Organization.objects.filter(organization_id=obj.id).count()

        def get_devices_count(self, obj):
            return Device2Organization.objects.filter(organization_id=obj.id).count()

        def get_device_groups_count(self, obj):
            return DeviceGroup2Organization.objects.filter(organization_id=obj.id).count()

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
                'employees_count',
                'devices_count',
                'device_groups_count',
            ]


class DepartmentSerializers:
    """Serializers for department-model"""
    class CreateSerializer(serializers.ModelSerializer):
        """Serializer for create department-model"""
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
            rights = obj.get('rights', '')
            if not(isinstance(obj.get('rights'), int)):
                represent.__setitem__('rights', 0 if (
                    rights == '') else int(rights))
            if not(isinstance(obj.get('organization'), Organization)):
                represent.__setitem__('organization', Organization.objects.get(
                    pk=int(obj.get('organization'))))

            return represent

    class ModelSerializer(serializers.ModelSerializer):
        """Serializer for show department-model"""

        employees_count = serializers.SerializerMethodField()

        def get_employees_count(self, obj):
            queryset = Employee2Department.objects.filter(department=obj)

            if 'organization' in self.context:
                organization = self.context['organization']
                if organization is not None:
                    queryset = queryset.filter(
                        employee_id__in=Employee2Organization.objects
                        .filter(organization_id=organization).values_list('employee', flat=True))

            return queryset.count()

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


class _OrganizationOfEmployeeSerializers(serializers.ModelSerializer):
    organization = OrganizationSerializers.ModelSerializer()

    class Meta:
        model = Employee2Organization
        fields = ['organization']


class EmployeeSerializers():
    """Serializers for employee-model"""
    class CreateSerializer(serializers.ModelSerializer):
        """Serializer for create employee-model"""
        class Meta:
            model = Employee
            fields = [
                'last_name',
                'first_name',
                'patronymic',
            ]

    class ModelSerializer(serializers.ModelSerializer):
        """Serializer for show employee-model"""

        organizations_count = serializers.SerializerMethodField()
        departments_count = serializers.SerializerMethodField()

        def get_organizations_count(self, obj):
            return Employee2Organization.objects.filter(employee_id=obj.id).count()

        def get_departments_count(self, obj):
            queryset = Employee2Department.objects.filter(employee_id=obj.id)

            if 'organization' in self.context:
                organization = self.context['organization']
                if organization is not None:
                    queryset = queryset.filter(
                        department__organization=organization)

            return queryset.count()

        class Meta:
            model = Employee
            fields = [
                'id',
                'created_at',
                'dropped_at',
                'last_name',
                'first_name',
                'patronymic',
                'organizations_count',
                'departments_count',
            ]


class LoginSerializer():
    """Serializers for user-model"""
    class CreateSerializer(serializers.ModelSerializer):
        """Serializer for create user-model"""
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
        """Serializer for update user-model"""
        class Meta:
            model = User
            fields = [
                'first_name',
                'last_name',
            ]

    class FullSerializer(serializers.ModelSerializer):
        """Serializer for show user-model"""
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


class EmployeeRequestSerializer(serializers.ModelSerializer):
    """Serializer for employee-request-model"""
    employee = serializers.PrimaryKeyRelatedField(read_only=True)
    device = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = EmployeeRequest
        fields = [
            'id',
            'employee',
            'device',
            'moment',
            'request_type',
            'response_type',
            'description',
            'algorithm_type',
        ]


class DeviceGroupSerializers:
    """Serializers for device-model"""
    class CreateSerializer(serializers.ModelSerializer):
        """Serializer for create device-model"""
        class Meta:
            model = DeviceGroup
            fields = [
                'name',
                'rights',
                'description',
            ]

        def to_representation(self, obj):
            represent = QueryDict('', mutable=True)
            represent.update(obj)
            rights = obj.get('rights', '')
            if not(isinstance(obj.get('rights'), int)):
                represent.__setitem__('rights', 0 if (
                    rights == '') else int(rights))

            return represent

    class ModelSerializer(serializers.ModelSerializer):
        """Serializer for show device-model"""

        devices_count = serializers.SerializerMethodField()
        organizations_count = serializers.SerializerMethodField()

        def get_devices_count(self, obj):
            queryset = Device2DeviceGroup.objects.filter(
                device_group_id=obj.id)

            if 'organization' in self.context:
                organization = self.context['organization']
                if organization is not None:
                    queryset = queryset.filter(
                        device_id__in=Device2Organization.objects
                        .filter(organization_id=organization).values_list('device', flat=True))

            return queryset.count()

        def get_organizations_count(self, obj):
            return DeviceGroup2Organization.objects.filter(device_group_id=obj.id).count()

        class Meta:
            model = DeviceGroup
            fields = [
                'id',
                'created_at',
                'dropped_at',
                'name',
                'rights',
                'description',
                'devices_count',
                'organizations_count',
            ]


class DeviceSerializers:
    """Serializers for device-model"""
    class CreateSerializer(serializers.ModelSerializer):
        """Serializer for create device-model"""
        class Meta:
            model = Device
            fields = [
                'mqtt',
                'name',
                'description',
                'device_type',
                'config',
            ]

    class UpdateSerializer(serializers.ModelSerializer):
        """Serializer for update device-model"""
        class Meta:
            model = Device
            fields = [
                'mqtt',
                'name',
                'description',
                'config',
            ]

    class ModelSerializer(serializers.ModelSerializer):
        """Serializer for show device-model"""

        device_groups_count = serializers.SerializerMethodField()
        organizations_count = serializers.SerializerMethodField()

        def get_device_groups_count(self, obj):
            queryset = Device2DeviceGroup.objects.filter(device_id=obj.id)

            if 'organization' in self.context:
                organization = self.context['organization']
                if organization is not None:
                    queryset = queryset.filter(
                        device_group_id__in=DeviceGroup2Organization.objects
                        .filter(organization_id=organization).values_list('device_group', flat=True))

            return queryset.count()

        def get_organizations_count(self, obj):
            return Device2Organization.objects.filter(device_id=obj.id).count()

        class Meta:
            model = Device
            fields = [
                'id',
                'created_at',
                'dropped_at',
                'mqtt',
                'name',
                'description',
                'device_type',
                'config',
                'device_groups_count',
                'organizations_count',
            ]
