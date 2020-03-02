"""Device group model"""
from django.db import models

from idenick_app.classes.model_entities.abstract_entries import (
    AbstractEntry, EntryWithTimezone)


class DeviceGroup(AbstractEntry):
    """Device group model"""
    name = models.CharField(max_length=64, unique=True,
                            verbose_name='название проходной', )
    rights = models.IntegerField(default=0)
    description = models.CharField(max_length=500, blank=True, null=True,)

    def __str__(self):
        return self._str() + ('[%s] [%s] with rigth [%s]' % (self.name, self.description,
                                                             self.rights))

    class Meta:
        db_table = 'devicegroup'
        verbose_name_plural = 'Проходные'
        verbose_name = 'Проходная'
