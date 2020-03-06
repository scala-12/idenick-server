"""Model of relation between device and organization"""

from django.db import models

from idenick_app.classes.model_entities.abstract_entries import AbstractEntry


class Device2Organization(AbstractEntry):
    """Model of relation between device and organization"""
    organization = models.ForeignKey(
        'Organization', db_column='companysid', related_name='devices', on_delete=models.CASCADE, db_index=True,)
    device = models.ForeignKey(
        'Device', db_column='devicesid', related_name='organizations', on_delete=models.CASCADE, db_index=True,)

    def __str__(self):
        return self._str() + ('[%s] in [%s]' % (self.device, self.organization))

    class Meta:
        unique_together = (('device', 'organization'),)
