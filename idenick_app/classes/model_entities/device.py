"""Device model"""
from django.db import models

from idenick_app.classes.model_entities.abstract_entries import (
    AbstractEntry, EntryWithTimezone)


class Device(AbstractEntry, EntryWithTimezone):
    """Device model"""
    mqtt = models.CharField(max_length=255, db_column='mqttid', unique=True,)
    name = models.CharField(max_length=64, verbose_name='название')
    description = models.CharField(max_length=500, blank=True, null=True,)
    device_type = models.IntegerField(db_column='type', default=0)
    config = models.CharField(max_length=2000, blank=True, null=True,)
    checkpoint = models.ForeignKey(
        'Checkpoint', db_column='devicegroupsid', related_name='devices',
        on_delete=models.CASCADE, blank=True, null=True, default=None, db_index=True,)

    def save(self, *args, **kwargs):
        super().save_timezone()
        super(Device, self).save(*args, **kwargs)

    def __str__(self):
        return self._str() + ('mqtt[%s] [%s] [%s] [%s] [%s] with config [%s]'
                              % (self.mqtt, self.name,
                                 self.device_type,
                                 self.description,
                                 self.checkpoint,
                                 self.config))

    class Meta:
        db_table = 'devices'

    @property
    def full_name(self):
        """return full device name"""
        return '%s (%s)' % (self.name, self.mqtt)
