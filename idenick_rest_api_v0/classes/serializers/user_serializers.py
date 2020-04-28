"""Serializer for user-model"""
from django.contrib.auth.models import User
from rest_framework import serializers


class ModelSerializer(serializers.ModelSerializer):
    """Serializer for user-model"""
    class Meta:
        model = User
        fields = [
            'id',
            'last_name',
            'first_name',
        ]
