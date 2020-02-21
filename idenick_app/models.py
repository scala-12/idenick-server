"""models"""
import datetime
import uuid
from typing import List, Optional

from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver

from idenick_app.classes.constants.identification import (algorithm_constants,
                                                          request_constants,
                                                          response_constants)
from idenick_app.classes.utils import date_utils
from idenick_app.classes.utils.models_utils import (DELETED_STATUS,
                                                    AbstractEntry,
                                                    AbstractSimpleEntry,
                                                    EntryWithTimesheet,
                                                    EntryWithTimezone)


class Employee(AbstractEntry):
    """Employee model"""
    guid = models.CharField(max_length=50, unique=True,
                            db_column='userid', default=uuid.uuid4)
    last_name = models.CharField(db_column='surname', max_length=64)
    first_name = models.CharField(db_column='firstname', max_length=64)
    patronymic = models.CharField(max_length=64)

    def __str__(self):
        return self._str() + self.full_name

    @property
    def full_name(self):
        """return full employee name"""
        return '%s %s %s' % (self.last_name, self.first_name, self.patronymic)

    def _has_identification_template(self, one_type: Optional[int] = None,
                                     many_types: Optional[List[int]] = None):
        """return true if employee has active identification template by type"""
        result = IndentificationTepmplate.objects.filter(
            employee_id=self.id, dropped_at=None,)
        if one_type is not None:
            result = result.filter(algorithm_type=one_type)
        elif many_types is not None:
            result = result.filter(algorithm_type__in=many_types)
        else:
            result = None

        return result.exists()

    @property
    def has_card(self) -> bool:
        """return true if employee has active card identification"""
        return self._has_identification_template(one_type=algorithm_constants.CARD_ALGORITHM)

    @property
    def has_finger(self) -> bool:
        """return true if employee has active finger identification"""
        return self._has_identification_template(
            many_types=[algorithm_constants.FINGER_ALGORITHM_1,
                        algorithm_constants.FINGER_ALGORITHM_2,
                        algorithm_constants.FINGER_ALGORITHM_3])

    @property
    def has_face(self) -> bool:
        """return true if employee has active face identification"""
        return self._has_identification_template(one_type=algorithm_constants.FACE_ALGORITHM)

    class Meta:
        db_table = 'users'


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


class Department(AbstractEntry):
    """Department model"""
    organization = models.ForeignKey(
        'Organization', db_column='companyid', related_name='departments', on_delete=models.CASCADE)
    name = models.CharField(max_length=64)
    rights = models.IntegerField(default=0)
    address = models.CharField(max_length=500, blank=True, null=True,)
    description = models.CharField(max_length=500, blank=True, null=True,)
    show_in_report = models.BooleanField(default=False)

    def __str__(self):
        return self._str() + ('organization[%s] [%s] with right[%s] address[%s] (%s)'
                              % (self.organization, self.name, self.rights, self.address, self.description))

    class Meta:
        db_table = 'usergroup'
        unique_together = (('organization', 'name'),)


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


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """create user info record"""
    if created:
        Login.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """create user info record"""
    instance.login.save()


class Login(AbstractSimpleEntry):
    """Model of user info"""
    ADMIN = 'adm'
    CONTROLLER = 'ctrl'
    REGISTRATOR = 'reg'
    NOT_SELECTED = 'none'
    USER_ROLE = [
        (ADMIN, 'admin'),
        (CONTROLLER, 'controller'),
        (REGISTRATOR, 'registrator'),
        (NOT_SELECTED, 'not selected'),
    ]

    guid = models.UUIDField(default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=4, choices=USER_ROLE, blank=True)
    organization = models.ForeignKey(
        'Organization', on_delete=models.CASCADE, null=True, blank=True)

    @property
    def created_at(self):
        return self.user.date_joined

    def save(self, *args, **kwargs):
        if not self.organization and not self.role:
            self.role = Login.NOT_SELECTED

        if (self.role != Login.CONTROLLER) and (self.role != Login.REGISTRATOR):
            self.organization = None

        super(Login, self).save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        self.user.delete()
        return super(self.__class__, self).delete(*args, **kwargs)

    def __str__(self):
        return 'id[%s] guid[%s] login[%s] [%s] [%s] with role [%s]' \
            % (self.id, self.guid, self.organization, self.user.username, self.user.first_name
                + ' ' + self.user.last_name, self.get_role_display())


class Device(AbstractEntry, EntryWithTimezone):
    """Device model"""
    mqtt = models.CharField(max_length=255, db_column='mqttid', unique=True,)
    name = models.CharField(max_length=64, verbose_name='название')
    description = models.CharField(max_length=500, blank=True, null=True,)
    device_type = models.IntegerField(db_column='type', default=0)
    config = models.CharField(max_length=2000, blank=True, null=True,)
    device_group = models.ForeignKey(
        'DeviceGroup', db_column='devicegroupsid', related_name='devices',
        on_delete=models.CASCADE, blank=True, null=True, default=None,)

    def save(self, *args, **kwargs):
        super().save_timezone()
        super(Device, self).save(*args, **kwargs)

    def __str__(self):
        return self._str() + ('mqtt[%s] [%s] [%s] [%s] [%s] with config [%s]'
                              % (self.mqtt, self.name,
                                 self.device_type,
                                 self.description,
                                 self.device_group,
                                 self.config))

    class Meta:
        db_table = 'devices'

    @property
    def full_name(self):
        """return full device name"""
        return '%s (%s)' % (self.name, self.mqtt)


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


class Device2Organization(AbstractEntry):
    """Model of relation between device and device group"""
    organization = models.ForeignKey(
        'Organization', db_column='companysid', related_name='devices', on_delete=models.CASCADE)
    device = models.ForeignKey(
        'Device', db_column='devicesid', related_name='organizations', on_delete=models.CASCADE)

    def __str__(self):
        return self._str() + ('[%s] in [%s]' % (self.device, self.device_group))

    class Meta:
        unique_together = (('device', 'organization'),)


class EmployeeRequest(models.Model):
    """Employee request model. READ ONLY"""
    id = models.AutoField(editable=False, primary_key=True)
    moment = models.DateTimeField(
        editable=False, db_column='stamp', auto_now_add=True)
    request_type = models.IntegerField(
        editable=False, db_column='request', choices=request_constants.REQUEST_TYPE,)
    response_type = models.IntegerField(
        editable=False, db_column='result', choices=response_constants.RESPONSE_TYPE,)
    description = models.CharField(
        editable=False, max_length=500, blank=True, null=True)
    algorithm_type = models.IntegerField(
        editable=False, db_column='algorithm', choices=algorithm_constants.ALGORITHM_TYPE,)
    employee = models.ForeignKey(
        'Employee', db_column='usersid', on_delete=models.CASCADE, null=True)
    device = models.ForeignKey(
        'Device', db_column='devicesid', on_delete=models.CASCADE, null=True)
    templatesid = models.IntegerField(editable=False, null=True)

    @property
    def device_group_name(self):
        return self.device.device_group.name if (self.device is not None) \
            and (self.device.device_group is not None) \
            else None

    @property
    def employee_name(self):
        result = None
        if not (self.employee is None):
            if self.employee.dropped_at is None:
                result = self.employee.full_name
            else:
                result = DELETED_STATUS

        return result

    def get_date_info(self) -> date_utils.DateInfo:
        utc = None
        if (self.device is not None) and (self.device.timezone is not None):
            utc = date_utils.duration_to_str(self.device.timezone)

        return date_utils.DateInfo(self.related_moment, utc)

    @property
    def date_info(self) -> dict:
        return vars(self.get_date_info())

    @property
    def device_name(self) -> Optional[str]:
        result = None
        if not (self.device is None):
            if self.device.dropped_at is None:
                result = self.device.full_name
            else:
                result = DELETED_STATUS

        return result

    @property
    def related_moment(self) -> datetime.datetime:
        result = self.moment
        if (self.device is not None) and (self.device.timezone is not None):
            result = result + self.device.timezone

        return result

    def __str__(self):
        return ('id[%s] [%s] with [%s] in [%s] do [%s] with result [%s] (%s)'
                % (self.id, self.employee, self.device, self.moment, self.request_type,
                   self.response_type, self.description))

    class Meta:
        db_table = 'querylog'


class IndentificationTepmplate(models.Model):
    """Employee templates model. READ ONLY"""
    id = models.AutoField(primary_key=True, editable=False,)
    employee = models.ForeignKey(
        'Employee', db_column='usersid', on_delete=models.CASCADE, editable=False,)
    algorithm_type = models.IntegerField(
        db_column='algorithm', choices=algorithm_constants.ALGORITHM_TYPE, editable=False,)
    algorithm_version = models.SmallIntegerField(
        db_column='algorithmVersion', editable=False,)
    template = models.BinaryField(max_length=8000, editable=False,)
    quality = models.SmallIntegerField(editable=False, null=True, blank=True,)
    config = models.CharField(
        max_length=2000, editable=False, null=True, blank=True,)
    created_at = models.DateTimeField(
        db_column='rcreated', auto_now_add=True, editable=False,)
    dropped_at = models.DateTimeField(
        db_column='rdropped', null=True, blank=True, editable=False,)

    class Meta:
        db_table = 'templates'
