"""Employee request model. READ ONLY"""

import datetime
from typing import Optional

from django.db import models

from idenick_app.classes.constants.identification import (algorithm_constants,
                                                          request_constants,
                                                          response_constants)
from idenick_app.classes.utils import date_utils
from idenick_app.classes.utils.models_utils import DELETED_STATUS


class EmployeeRequest(models.Model):
    """Employee request model. READ ONLY"""
    id = models.AutoField(editable=False, primary_key=True, db_index=True,)
    moment = models.DateTimeField(
        editable=False, db_column='stamp', auto_now_add=True, db_index=True,)
    request_type = models.IntegerField(
        editable=False, db_column='request', choices=request_constants.REQUEST_TYPE,)
    response_type = models.IntegerField(
        editable=False, db_column='result', choices=response_constants.RESPONSE_TYPE,)
    description = models.CharField(
        editable=False, max_length=500, blank=True, null=True)
    algorithm_type = models.IntegerField(
        editable=False, db_column='algorithm', choices=algorithm_constants.ALGORITHM_TYPE,)
    employee = models.ForeignKey(
        'Employee', db_column='usersid', on_delete=models.CASCADE, null=True, db_index=True,)
    device = models.ForeignKey(
        'Device', db_column='devicesid', on_delete=models.CASCADE, null=True, db_index=True,)
    templatesid = models.IntegerField(editable=False, null=True)

    @property
    def checkpoint_name(self):
        return self.device.checkpoint.name if (self.device is not None) \
            and (self.device.checkpoint is not None) \
            else None

    @property
    def employee_name(self):
        result = None
        if not (self.employee is None):
            if self.employee.dropped_at is None:
                result = self.employee.full_name
            else:
                result = DELETED_STATUS

        return result

    def get_date_info(self) -> date_utils.DateInfo:
        utc = None
        if (self.device is not None) and (self.device.timezone is not None):
            utc = date_utils.duration_to_str(self.device.timezone)

        return date_utils.DateInfo(self.related_moment, utc)

    @property
    def date_info(self) -> dict:
        return vars(self.get_date_info())

    @property
    def date(self) -> str:
        return self.get_date_info().day

    @property
    def device_name(self) -> Optional[str]:
        result = None
        if not (self.device is None):
            if self.device.dropped_at is None:
                result = self.device.full_name
            else:
                result = DELETED_STATUS

        return result

    @property
    def related_moment(self) -> datetime.datetime:
        result = self.moment
        if (self.device is not None) and (self.device.timezone is not None):
            result = result + self.device.timezone

        return result

    def __str__(self):
        return ('id[%s] [%s] with [%s] in [%s] do [%s] with result [%s] (%s)'
                % (self.id, self.employee, self.device, self.moment, self.request_type,
                   self.response_type, self.description))

    class Meta:
        db_table = 'querylog'
