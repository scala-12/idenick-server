"""models"""
import uuid

from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver


class _AbstractEntry(models.Model):
    id = models.AutoField(primary_key=True)
    created_at = models.DateTimeField(auto_now_add=True)
    dropped_at = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.dropped_at:
            self.dropped_at = None
        super(_AbstractEntry, self).save(*args, **kwargs)

    class Meta:
        abstract = True
        ordering = ["created_at"]


class _AbstractEntry4Old(models.Model):
    id = models.AutoField(primary_key=True)
    created_at = models.DateTimeField(db_column='rcreated', auto_now_add=True)
    dropped_at = models.DateTimeField(
        db_column='rdropped', null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.dropped_at:
            self.dropped_at = None
        super(_AbstractEntry4Old, self).save(*args, **kwargs)

    class Meta:
        abstract = True
        ordering = ["created_at"]

    def _str(self):
        return 'id[%s] ' % (self.id)


class Employee(_AbstractEntry4Old):
    """Employee model"""
    organization = models.ForeignKey(
        'Organization', related_name='employees', null=True, default=None,
        on_delete=models.SET_NULL)
    guid = models.UUIDField(
        db_column='userid', default=uuid.uuid4, editable=False)
    last_name = models.CharField(db_column='surname', max_length=64)
    first_name = models.CharField(db_column='firstname', max_length=64)
    patronymic = models.CharField(max_length=64)

    def __str__(self):
        return self._str() + self.get_full_name()

    def get_full_name(self):
        """return full employee name"""
        return '%s %s %s' % (self.last_name, self.first_name, self.patronymic)

    class Meta:
        db_table = 'users'


class Organization(_AbstractEntry4Old):
    """Organization model"""
    guid = models.UUIDField(db_column='companyid',
                            default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=250, unique=True,
                            verbose_name='название')
    address = models.CharField(max_length=500, blank=True)
    phone = models.CharField(max_length=50, blank=True)

    def __str__(self):
        return self._str() + ('[%s] address[%s] phone[%s]' % (self.name, self.address, self.phone))

    class Meta:
        db_table = 'company'
        verbose_name_plural = 'Организации'
        verbose_name = 'Организация'


class Department(_AbstractEntry4Old):
    """Department model"""
    organization = models.ForeignKey(
        'Organization', db_column='companyid', related_name='departments', on_delete=models.CASCADE)
    name = models.CharField(max_length=64)
    rights = models.IntegerField(default=0)
    address = models.CharField(max_length=500, blank=True)
    description = models.CharField(max_length=500, blank=True)

    def __str__(self):
        return self._str() + ('organization[%s] [%s] with right[%s] address[%s] (%s)'
                              % (self.organization, self.name, self.rights, self.address, self.description))

    class Meta:
        db_table = 'usergroup'
        unique_together = (('organization', 'name'),)


class Employee2Department(_AbstractEntry4Old):
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


class Login(models.Model):
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

    id = models.AutoField(primary_key=True)
    guid = models.UUIDField(default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=4, choices=USER_ROLE, blank=True)
    organization = models.ForeignKey(
        'Organization', on_delete=models.CASCADE, null=True, blank=True)

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


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """create user info record"""
    if created:
        Login.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """create user info record"""
    instance.login.save()


class Device(_AbstractEntry4Old):
    """Device model"""
    mqtt = models.CharField(
        max_length=500, db_column='mqttid', default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=64, verbose_name='название')
    description = models.CharField(max_length=500, blank=True)
    device_type = models.IntegerField(db_column='type', default=0)
    config = models.CharField(max_length=2000, blank=True)
    organization = models.ForeignKey(
        'Organization', on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        return self._str() + ('mqtt[%s] [%s] [%s] [%s] with config [%s]' % (self.mqtt, self.name,
                                                                            self.device_type, self.description, self.config))

    class Meta:
        db_table = 'devices'
        unique_together = (('organization', 'name'),)


class DeviceGroup(_AbstractEntry4Old):
    """Device group model"""
    name = models.CharField(max_length=64)
    rights = models.IntegerField(default=0)
    description = models.CharField(max_length=500, blank=True)

    def __str__(self):
        return self._str() + ('[%s] [%s] with rigth [%s]' % (self.name, self.description,
                                                             self.rights))

    class Meta:
        db_table = 'devicegroup'


class EmployeeRequest(_AbstractEntry4Old):
    """Employee request model"""
    moment = models.DateTimeField(db_column='stamp', auto_now_add=True)
    request_type = models.IntegerField(db_column='request', default=0)
    response_type = models.IntegerField(db_column='result', default=0)
    description = models.CharField(max_length=500, blank=True)
    algorithm_type = models.IntegerField(db_column='algorithm', default=0)
    employee = models.ForeignKey(
        'Employee', db_column='userid', on_delete=models.CASCADE)
    device = models.ForeignKey(
        'Device', db_column='deviceid', on_delete=models.CASCADE)

    def __str__(self):
        return self._str() + ('[%s] with [%s] in [%s] do [%s] with result [%s] (%s)'
                              % (self.employee, self.device, self.moment, self.request_type,
                                 self.response_type, self.description))

    class Meta:
        db_table = 'querylog'
