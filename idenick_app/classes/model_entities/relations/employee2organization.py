"""Model of relation between employee and organization"""
from django.db import models

from idenick_app.classes.model_entities.abstract_entries import (
    AbstractEntry, EntryWithTimesheet)
from idenick_app.classes.utils import date_utils


class Employee2Organization(AbstractEntry, EntryWithTimesheet):
    """Model of relation between employee and organization"""
    employee = models.ForeignKey(
        'Employee', db_column='usersid', related_name='organizations', on_delete=models.CASCADE)
    organization = models.ForeignKey(
        'Organization', db_column='companyid', related_name='employees', on_delete=models.CASCADE)

    def save(self, *args, **kwargs):
        super().save_timesheet()
        super(Employee2Organization, self).save(*args, **kwargs)

    def __str__(self):
        return self._str() + ('[%s] in [%s]' % (self.employee, self.organization))

    class Meta:
        unique_together = (('employee', 'organization'),)
