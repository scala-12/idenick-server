"""Model of relation between employee and department"""

from django.db import models

from idenick_app.classes.model_entities.abstract_entries import AbstractEntry


class Employee2Department(AbstractEntry):
    """Model of relation between employee and department"""
    department = models.ForeignKey(
        'Department', db_column='usergroupid', related_name='employees', on_delete=models.CASCADE)
    employee = models.ForeignKey(
        'Employee', db_column='usersid', related_name='departments', on_delete=models.CASCADE)

    def __str__(self):
        return self._str() + ('[%s] in [%s]' % (self.employee, self.department))

    class Meta:
        db_table = 'users_usergroup'
        unique_together = (('department', 'employee'),)
