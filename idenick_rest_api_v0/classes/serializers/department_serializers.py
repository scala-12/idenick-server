"""Serializers for department-model"""

from django.http.request import QueryDict
from rest_framework import serializers

from idenick_app.models import (Department, Employee2Department,
                                Employee2Organization, Organization)


class CreateSerializer(serializers.ModelSerializer):
    """Serializer for create department-model"""
    rights = serializers.SerializerMethodField()
    organization = serializers.SerializerMethodField()

    def get_rights(self, obj: QueryDict):
        name = 'rights'
        return int(obj.get(name)) if name in obj else 0

    def get_organization(self, obj: QueryDict):
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

    def get_rights(self, obj: QueryDict):
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

    def get_employees_count(self, obj: Department):
        queryset = Employee2Department.objects.filter(
            department=obj, employee__dropped_at=None, dropped_at=None)

        if 'organization' in self.context:
            organization = self.context['organization']
            if organization is not None:
                organization_employees = Employee2Organization.objects\
                    .filter(organization_id=organization, dropped_at=None)\
                    .values_list('employee', flat=True)
                queryset = queryset.filter(
                    employee_id__in=organization_employees)

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
