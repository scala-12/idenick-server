"""Serializers for device-model"""

from django.http.request import QueryDict
from rest_framework import serializers

from idenick_app.classes.utils import date_utils
from idenick_app.classes.utils.models_utils import get_related_entities_count
from idenick_app.models import (Checkpoint, Device, Device2Organization,
                                Organization)
from idenick_rest_api_v0.classes.utils.serializers_utils import TimeValueField


class CreateSerializer(serializers.ModelSerializer):
    """Serializer for create device-model"""
    timezone = TimeValueField()
    checkpoint = serializers.SerializerMethodField()

    def get_checkpoint(self, obj: QueryDict):
        checkpoint = obj.get('checkpoint', '')
        result = None
        if isinstance(checkpoint, str):
            result = None if (checkpoint == '') \
                else Checkpoint.objects.get(id=int(checkpoint))
        return result

    class Meta:
        model = Device
        fields = [
            'mqtt',
            'name',
            'description',
            'device_type',
            'checkpoint',
            'config',
            'timezone',
        ]


class UpdateSerializer(serializers.ModelSerializer):
    """Serializer for update device-model"""
    timezone = TimeValueField()
    checkpoint = serializers.SerializerMethodField()

    def get_checkpoint(self, obj: QueryDict):
        checkpoint = obj.get('checkpoint', '')
        result = None
        if isinstance(checkpoint, str):
            result = None if (checkpoint == '') \
                else Checkpoint.objects.get(id=int(checkpoint))
        return result

    class Meta:
        model = Device
        fields = [
            'name',
            'description',
            'checkpoint',
            'config',
            'timezone',
        ]


class ModelSerializer(serializers.ModelSerializer):
    """Serializer for show device-model"""

    organizations_count = serializers.SerializerMethodField()
    timezone = serializers.SerializerMethodField()
    checkpoint = serializers.PrimaryKeyRelatedField(read_only=True)

    def get_timezone(self, obj: Device):
        return None if obj.timezone is None else date_utils.duration_to_str(obj.timezone)

    def get_organizations_count(self, obj: Device):
        return get_related_entities_count(Device2Organization,
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
            'checkpoint',
            'config',
            'organizations_count',
            'timezone',
        ]
