"""models"""
import datetime
import uuid
from typing import Optional

from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver

from idenick_app.classes.utils import date_utils

DELETED_STATUS = 'удален'


class AbstractSimpleEntry(models.Model):
    id = models.AutoField(primary_key=True)
    dropped_at = models.DateTimeField(
        db_column='rdropped', null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.dropped_at:
            self.dropped_at = None
        super(AbstractSimpleEntry, self).save(*args, **kwargs)

    class Meta:
        abstract = True

    def _str(self):
        return 'id[%s] ' % (self.id)


class AbstractEntry(AbstractSimpleEntry):
    created_at = models.DateTimeField(db_column='rcreated', auto_now_add=True)

    class Meta:
        abstract = True
        ordering = ["created_at"]


class EntryWithTimezone(models.Model):
    timezone = models.DurationField(default=None, null=True, blank=True,)

    def save_timezone(self, *args, **kwargs):
        if (self.timezone is not None) and ((self.timezone > datetime.timedelta(hours=14))
                                            or (self.timezone < datetime.timedelta(hours=-12))):
            self.timezone = None

    class Meta:
        abstract = True


class EntryWithTimesheet(models.Model):
    timesheet_start = models.CharField(max_length=5,
                                       default=None, null=True, blank=True,)
    timesheet_end = models.CharField(max_length=5,
                                     default=None, null=True, blank=True,)

    def save_timesheet(self, *args, **kwargs):
        do_save = True
        if (self.timesheet_start is None) or (self.timesheet_end is None):
            do_save = False
        else:
            start = date_utils.str_to_duration(self.timesheet_start)
            end = None if start is None else date_utils.str_to_duration(
                self.timesheet_end)
            if (end is None) or (start > end) or (start < datetime.timedelta()) \
                    or (end > datetime.timedelta(hours=23, minutes=59)):
                do_save = False

        if not do_save:
            self.timesheet_start = None
            self.timesheet_end = None

    class Meta:
        abstract = True


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """create user info record"""
    if created:
        Login.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """create user info record"""
    instance.login.save()
