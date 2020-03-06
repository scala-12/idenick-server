"""department model"""

from django.db import models

from idenick_app.classes.model_entities.abstract_entries import AbstractEntry


class Department(AbstractEntry):
    """Department model"""
    organization = models.ForeignKey(
        'Organization', db_column='companyid', related_name='departments', on_delete=models.CASCADE, db_index=True,)
    name = models.CharField(max_length=64)
    rights = models.IntegerField(default=0)
    address = models.CharField(max_length=500, blank=True, null=True,)
    description = models.CharField(max_length=500, blank=True, null=True,)
    show_in_report = models.BooleanField(default=False, db_index=True,)

    def __str__(self):
        return self._str() + ('organization[%s] [%s] with right[%s] address[%s] (%s)'
                              % (self.organization, self.name, self.rights, self.address, self.description))

    class Meta:
        db_table = 'usergroup'
        unique_together = (('organization', 'name'),)
