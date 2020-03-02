"""Model of relation between device group and organization"""
from django.db import models

from idenick_app.classes.model_entities.abstract_entries import AbstractEntry
from idenick_app.classes.utils import date_utils


class DeviceGroup2Organization(AbstractEntry):
    """Model of relation between device group and organization"""
    device_group = models.ForeignKey(
        'DeviceGroup', db_column='devicegroupsid', related_name='organizations', on_delete=models.CASCADE)
    organization = models.ForeignKey(
        'Organization', db_column='companyid', related_name='device_groups', on_delete=models.CASCADE)

    def __str__(self):
        return self._str() + ('[%s] in [%s]' % (self.device_group, self.organization))

    class Meta:
        unique_together = (('device_group', 'organization'),)
