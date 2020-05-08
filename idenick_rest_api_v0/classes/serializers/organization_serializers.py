"""Serializers for organization-model"""
from rest_framework import serializers

from idenick_app.classes.utils import date_utils
from idenick_app.classes.utils.models_utils import get_related_entities_count
from idenick_app.models import (Checkpoint, Checkpoint2Organization,
                                Department, Device, Device2Organization,
                                Employee, Employee2Organization, Login,
                                Organization)
from idenick_rest_api_v0.classes.utils.serializers_utils import TimeValueField


class CreateSerializer(serializers.ModelSerializer):
    """Serializer for create organization-model"""
    timezone = TimeValueField()

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
    checkpoints_count = serializers.SerializerMethodField()
    timezone = serializers.SerializerMethodField()

    def get_timezone(self, obj: Organization):
        return None if obj.timezone is None else date_utils.duration_to_str(obj.timezone)

    def get_departments_count(self, obj: Organization):
        return Department.objects.filter(organization=obj, dropped_at=None).count()

    def get_controllers_count(self, obj: Organization):
        return Login.objects.filter(role=Login.CONTROLLER, organization=obj,
                                    dropped_at=None).count()

    def get_registrators_count(self, obj: Organization):
        return Login.objects.filter(role=Login.REGISTRATOR, organization=obj,
                                    dropped_at=None).count()

    def get_employees_count(self, obj: Organization):
        return get_related_entities_count(Employee2Organization, {'organization_id': obj.id},
                                          Employee, 'employee')

    def get_devices_count(self, obj: Organization):
        return get_related_entities_count(Device2Organization, {'organization_id': obj.id},
                                          Device, 'device')

    def get_checkpoints_count(self, obj: Organization):
        return get_related_entities_count(Checkpoint2Organization,
                                          {'organization_id': obj.id}, Checkpoint,
                                          'checkpoint')

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
            'checkpoints_count',
            'timezone',
            'timesheet_start',
            'timesheet_end',
        ]
