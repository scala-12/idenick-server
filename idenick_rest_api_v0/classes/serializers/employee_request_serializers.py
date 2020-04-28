"""Serializers for employee request model"""

from rest_framework import serializers

from idenick_app.models import EmployeeRequest


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
            'checkpoint_name',
            'request_type',
            'response_type',
            'description',
            'algorithm_type',
            'date_info',
        ]
