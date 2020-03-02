"""organization model"""
import uuid

from django.db import models

from idenick_app.classes.model_entities.abstract_entries import (
    AbstractEntry, EntryWithTimesheet, EntryWithTimezone)


class Organization(AbstractEntry, EntryWithTimezone, EntryWithTimesheet):
    """Organization model"""
    guid = models.CharField(max_length=50, unique=True, db_column='companyid',
                            default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=250, unique=True,
                            verbose_name='название')
    address = models.CharField(max_length=500, blank=True, null=True,)
    phone = models.CharField(max_length=50, blank=True, null=True,)

    def save(self, *args, **kwargs):
        super().save_timezone()
        super().save_timesheet()
        super(Organization, self).save(*args, **kwargs)

    def __str__(self):
        return self._str() + ('[%s] address[%s] phone[%s]' % (self.name, self.address, self.phone))

    class Meta:
        db_table = 'company'
        verbose_name_plural = 'Организации'
        verbose_name = 'Организация'
