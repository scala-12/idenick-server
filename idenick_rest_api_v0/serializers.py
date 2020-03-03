"""Serializers for models"""
from datetime import timedelta

from django.contrib.auth.models import User
from django.http.request import QueryDict
from rest_framework import serializers

from idenick_app.classes.utils import date_utils
from idenick_app.models import (AbstractEntry, Department, Device,
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


class _TimeValueField(serializers.Field):
    def to_representation(self, value):
        return value if isinstance(value, timedelta) else date_utils.str_to_duration(value)

    def to_internal_value(self, data):
        return data if isinstance(data, timedelta) else date_utils.str_to_duration(data)


class _DateInfoSerializer(serializers.ModelSerializer):
    """Serializer for date info container"""
    class Meta:
        model = date_utils.DateInfo
        fields = [
            'week_day',
            'day',
            'month',
            'time',
            'utc',
        ]


def _get_related_entities_count(Relation_class: AbstractEntry,
                                relation_filter: dict,
                                Object_class: AbstractEntry,
                                relation_field: str):
    relation_filter.update(dropped_at=None)
    ids = Relation_class.objects.filter(
        **relation_filter).values_list(relation_field, flat=True)

    return Object_class.objects.filter(id__in=ids, dropped_at=None).count()


class OrganizationSerializers:
    """Serializers for organization-model"""
    class CreateSerializer(serializers.ModelSerializer):
        """Serializer for create organization-model"""
        timezone = _TimeValueField()

        class Meta:
            model = Organization
            fields = [
                'name',
                'timezone',
                'timesheet_start',
                'timesheet_end',
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
        timezone = serializers.SerializerMethodField()

        def get_timezone(self, obj):
            return None if obj.timezone is None else date_utils.duration_to_str(obj.timezone)

        def get_departments_count(self, obj):
            return Department.objects.filter(organization=obj, dropped_at=None).count()

        def get_controllers_count(self, obj):
            return Login.objects.filter(role=Login.CONTROLLER, organization=obj,
                                        dropped_at=None).count()

        def get_registrators_count(self, obj):
            return Login.objects.filter(role=Login.REGISTRATOR, organization=obj,
                                        dropped_at=None).count()

        def get_employees_count(self, obj):
            return _get_related_entities_count(Employee2Organization, {'organization_id': obj.id},
                                               Employee, 'employee')

        def get_devices_count(self, obj):
            return _get_related_entities_count(Device2Organization, {'organization_id': obj.id},
                                               Device, 'device')

        def get_device_groups_count(self, obj):
            return _get_related_entities_count(DeviceGroup2Organization,
                                               {'organization_id': obj.id}, DeviceGroup,
                                               'device_group')

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
                'timezone',
                'timesheet_start',
                'timesheet_end',
            ]


class DepartmentSerializers:
    """Serializers for department-model"""
    class CreateSerializer(serializers.ModelSerializer):
        """Serializer for create department-model"""
        rights = serializers.SerializerMethodField()
        organization = serializers.SerializerMethodField()

        def get_rights(self, obj):
            name = 'rights'
            return int(obj.get(name)) if name in obj else 0

        def get_organization(self, obj):
            return Organization.objects.get(id=self.context['organization'])

        class Meta:
            model = Department
            fields = [
                'name',
                'rights',
                'address',
                'description',
                'organization',
                'show_in_report',
            ]

    class UpdateSerializer(serializers.ModelSerializer):
        """Serializer for update department-model"""
        rights = serializers.SerializerMethodField()

        def get_rights(self, obj):
            name = 'rights'
            return int(obj.get(name)) if name in obj else 0

        class Meta:
            model = Department
            fields = [
                'name',
                'rights',
                'address',
                'description',
                'show_in_report',
            ]

    class ModelSerializer(serializers.ModelSerializer):
        """Serializer for show department-model"""

        employees_count = serializers.SerializerMethodField()

        def get_employees_count(self, obj):
            queryset = Employee2Department.objects.filter(
                department=obj, employee__dropped_at=None, dropped_at=None)

            if 'organization' in self.context:
                organization = self.context['organization']
                if organization is not None:
                    queryset = queryset.filter(
                        employee_id__in=Employee2Organization.objects
                        .filter(organization_id=organization, dropped_at=None)
                        .values_list('employee', flat=True))

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
                'show_in_report',
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
        departments_count = serializers.SerializerMethodField()
        timesheet_start = serializers.SerializerMethodField()
        timesheet_end = serializers.SerializerMethodField()

        def get_timesheet_start(self, obj: Employee):
            result = None
            if 'organization' in self.context:
                organization_id = self.context['organization']
                result = obj.get_timesheet_start(
                    organization_id=organization_id)

            return result

        def get_timesheet_end(self, obj: Employee):
            result = None
            if 'organization' in self.context:
                organization_id = self.context['organization']
                result = obj.get_timesheet_end(
                    organization_id=organization_id)

            return result

        def get_departments_count(self, obj: Employee):
            organization = None
            if 'organization' in self.context:
                organization = self.context['organization']

            return obj.get_departments_count(organization_id=organization)

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
                'timesheet_start',
                'timesheet_end',
                'has_face',
                'has_finger',
                'has_card',
                'has_photo',
            ]

    class FullModelSerializer(ModelSerializer):
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
                'timesheet_start',
                'timesheet_end',
                'has_face',
                'has_finger',
                'has_card',
                'has_photo',
                'photo',
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
        created_at = serializers.ReadOnlyField(source='user.date_joined')

        class Meta:
            model = Login
            fields = [
                'id',
                'created_at',
                'dropped_at',
                'organization',
                'role',
                'username',
                'first_name',
                'last_name',
                'is_active',
            ]


class EmployeeRequestSerializers:
    class ModelSerializer(serializers.ModelSerializer):
        """Serializer for employee-request-model"""
        employee = serializers.PrimaryKeyRelatedField(read_only=True)
        device = serializers.PrimaryKeyRelatedField(read_only=True)

        request_type = serializers.ReadOnlyField(
            source='get_request_type_display')
        response_type = serializers.ReadOnlyField(
            source='get_response_type_display')
        algorithm_type = serializers.ReadOnlyField(
            source='get_algorithm_type_display')
        date_info = serializers.DictField(child=serializers.CharField())

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
                'date_info',
            ]

    class HumanReadableSerializer(serializers.ModelSerializer):
        """Serializer for human-readable employee-request-model"""

        request_type = serializers.ReadOnlyField(
            source='get_request_type_display')
        response_type = serializers.ReadOnlyField(
            source='get_response_type_display')
        algorithm_type = serializers.ReadOnlyField(
            source='get_algorithm_type_display')
        date_info = serializers.DictField(child=serializers.CharField())

        class Meta:
            model = EmployeeRequest
            fields = [
                'id',
                'employee',
                'device',
                'employee_name',
                'device_name',
                'device_group_name',
                'request_type',
                'response_type',
                'description',
                'algorithm_type',
                'date_info',
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
            queryset = Device.objects.filter(
                device_group_id=obj.id, dropped_at=None)

            if 'organization' in self.context:
                organization = self.context['organization']
                if organization is not None:
                    queryset = queryset.filter(
                        id__in=Device2Organization.objects
                        .filter(organization_id=organization).values_list('device', flat=True))

            return queryset.count()

        def get_organizations_count(self, obj):
            return _get_related_entities_count(DeviceGroup2Organization,
                                               {'device_group_id': obj.id}, Organization,
                                               'organization')

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
        timezone = _TimeValueField()
        device_group = serializers.SerializerMethodField()

        def get_device_group(self, obj):
            device_group = obj.get('device_group', '')
            result = None
            if isinstance(device_group, str):
                result = None if (device_group == '') \
                    else DeviceGroup.objects.get(id=int(device_group))
            return result

        class Meta:
            model = Device
            fields = [
                'mqtt',
                'name',
                'description',
                'device_type',
                'device_group',
                'config',
                'timezone',
            ]

    class UpdateSerializer(serializers.ModelSerializer):
        """Serializer for update device-model"""
        timezone = _TimeValueField()
        device_group = serializers.SerializerMethodField()

        def get_device_group(self, obj):
            device_group = obj.get('device_group', '')
            result = None
            if isinstance(device_group, str):
                result = None if (device_group == '') \
                    else DeviceGroup.objects.get(id=int(device_group))
            return result

        class Meta:
            model = Device
            fields = [
                'name',
                'description',
                'device_group',
                'config',
                'timezone',
            ]

    class ModelSerializer(serializers.ModelSerializer):
        """Serializer for show device-model"""

        organizations_count = serializers.SerializerMethodField()
        timezone = serializers.SerializerMethodField()
        device_group = serializers.PrimaryKeyRelatedField(read_only=True)

        def get_timezone(self, obj):
            return None if obj.timezone is None else date_utils.duration_to_str(obj.timezone)

        def get_organizations_count(self, obj):
            return _get_related_entities_count(Device2Organization,
                                               {'device_id': obj.id}, Organization,
                                               'organization')

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
                'device_group',
                'config',
                'organizations_count',
                'timezone',
            ]
