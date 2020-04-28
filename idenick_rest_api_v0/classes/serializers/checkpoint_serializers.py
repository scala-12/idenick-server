"""Serializers for checkpoint-model"""

from django.http.request import QueryDict
from rest_framework import serializers

from idenick_app.classes.utils.models_utils import get_related_entities_count
from idenick_app.models import (Checkpoint, Checkpoint2Organization, Device,
                                Device2Organization, Organization)


class CreateSerializer(serializers.ModelSerializer):
    """Serializer for create device-model"""
    class Meta:
        model = Checkpoint
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
            checkpoint_id=obj.id, dropped_at=None)

        if 'organization' in self.context:
            organization = self.context['organization']
            if organization is not None:
                queryset = queryset.filter(
                    id__in=Device2Organization.objects
                    .filter(organization_id=organization).values_list('device', flat=True))

        return queryset.count()

    def get_organizations_count(self, obj):
        return get_related_entities_count(Checkpoint2Organization,
                                          {'checkpoint_id': obj.id}, Organization,
                                          'organization')

    class Meta:
        model = Checkpoint
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
