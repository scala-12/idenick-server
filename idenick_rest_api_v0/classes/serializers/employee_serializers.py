"""Serializers for employee-model"""

from rest_framework import serializers

from idenick_app.models import Employee


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

    def _get_timesheet(self, obj: Employee, is_start: bool):
        result = None
        if 'organization' in self.context:
            organization_filter = {
                'organization_id': self.context['organization']}
            result = obj.get_timesheet_start(**organization_filter) \
                if is_start \
                else obj.get_timesheet_end(**organization_filter)

        return result

    def get_timesheet_start(self, obj: Employee):
        return self._get_timesheet(obj, True)

    def get_timesheet_end(self, obj: Employee):
        return self._get_timesheet(obj, False)

    def get_departments_count(self, obj: Employee):
        organization = None
        if 'organization' in self.context:
            organization = self.context['organization']

        return 0\
            if organization is None else \
            obj.get_departments_count(organization_id=organization)

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
