"""utils for serializers"""
from datetime import timedelta

from rest_framework import serializers

from idenick_app.classes.utils import date_utils


class TimeValueField(serializers.Field):
    def to_representation(self, value):
        return value if isinstance(value, timedelta) else date_utils.str_to_duration(value)

    def to_internal_value(self, data):
        return data if isinstance(data, timedelta) else date_utils.str_to_duration(data)
