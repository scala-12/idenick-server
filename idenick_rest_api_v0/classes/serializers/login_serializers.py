"""Serializers for user-model"""

from django.contrib.auth.models import User
from rest_framework import serializers

from idenick_app.models import Login


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
