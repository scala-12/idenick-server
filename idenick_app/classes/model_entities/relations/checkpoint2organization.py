"""Model of relation between checkpoint and organization"""
from django.db import models

from idenick_app.classes.model_entities.abstract_entries import AbstractEntry
from idenick_app.classes.utils import date_utils


class Checkpoint2Organization(AbstractEntry):
    """Model of relation between checkpoint and organization"""
    checkpoint = models.ForeignKey(
        'Checkpoint', db_column='devicegroupsid', related_name='organizations',
        on_delete=models.CASCADE, db_index=True,)
    organization = models.ForeignKey(
        'Organization', db_column='companyid', related_name='checkpoints',
        on_delete=models.CASCADE, db_index=True,)

    def __str__(self):
        return self._str() + ('[%s] in [%s]' % (self.checkpoint, self.organization))

    class Meta:
        unique_together = (('checkpoint', 'organization'),)
