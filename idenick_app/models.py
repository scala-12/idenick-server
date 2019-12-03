"""models"""
import datetime
import uuid

from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver


class _AbstractEntry(models.Model):
    id = models.AutoField(primary_key=True)
    created_at = models.DateTimeField(db_column='rcreated', auto_now_add=True)
    dropped_at = models.DateTimeField(
        db_column='rdropped', null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.dropped_at:
            self.dropped_at = None
        super(_AbstractEntry, self).save(*args, **kwargs)

    class Meta:
        abstract = True
        ordering = ["created_at"]

    def _str(self):
        return 'id[%s] ' % (self.id)


class _AbstractTimezonedEntry(_AbstractEntry):
    timezone = models.DurationField(default=None, null=True, blank=True,)

    def save(self, *args, **kwargs):
        if (not self.timezone) or (self.timezone > datetime.timedelta(hours=14)) \
                or (self.timezone < datetime.timedelta(hours=-12)):
            self.timezone = None
        super(_AbstractTimezonedEntry, self).save(*args, **kwargs)

    class Meta:
        abstract = True


class Employee(_AbstractEntry):
    """Employee model"""
    guid = models.CharField(max_length=50, unique=True,
                            db_column='userid', default=uuid.uuid4)
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


class Organization(_AbstractTimezonedEntry):
    """Organization model"""
    guid = models.CharField(max_length=50, unique=True, db_column='companyid',
                            default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=250, unique=True,
                            verbose_name='название')
    address = models.CharField(max_length=500, blank=True, null=True,)
    phone = models.CharField(max_length=50, blank=True, null=True,)

    def __str__(self):
        return self._str() + ('[%s] address[%s] phone[%s]' % (self.name, self.address, self.phone))

    class Meta:
        db_table = 'company'
        verbose_name_plural = 'Организации'
        verbose_name = 'Организация'


class Department(_AbstractEntry):
    """Department model"""
    organization = models.ForeignKey(
        'Organization', db_column='companyid', related_name='departments', on_delete=models.CASCADE)
    name = models.CharField(max_length=64)
    rights = models.IntegerField(default=0)
    address = models.CharField(max_length=500, blank=True, null=True,)
    description = models.CharField(max_length=500, blank=True, null=True,)

    def __str__(self):
        return self._str() + ('organization[%s] [%s] with right[%s] address[%s] (%s)'
                              % (self.organization, self.name, self.rights, self.address, self.description))

    class Meta:
        db_table = 'usergroup'
        unique_together = (('organization', 'name'),)


class Employee2Department(_AbstractEntry):
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


class Device(_AbstractTimezonedEntry):
    """Device model"""
    mqtt = models.CharField(max_length=255, db_column='mqttid', unique=True,)
    name = models.CharField(max_length=64, verbose_name='название')
    description = models.CharField(max_length=500, blank=True, null=True,)
    device_type = models.IntegerField(db_column='type', default=0)
    config = models.CharField(max_length=2000, blank=True, null=True,)

    def __str__(self):
        return self._str() + ('mqtt[%s] [%s] [%s] [%s] [%s] with config [%s]'
                              % (self.mqtt, self.name,
                                 self.device_type,
                                 self.description,
                                 self.device_group,
                                 self.config))

    class Meta:
        db_table = 'devices'


class DeviceGroup(_AbstractEntry):
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


class DeviceGroup2Organization(_AbstractEntry):
    """Model of relation between device group and organization"""
    device_group = models.ForeignKey(
        'DeviceGroup', db_column='devicegroupsid', related_name='organizations', on_delete=models.CASCADE)
    organization = models.ForeignKey(
        'Organization', db_column='companyid', related_name='device_groups', on_delete=models.CASCADE)

    def __str__(self):
        return self._str() + ('[%s] in [%s]' % (self.device_group, self.organization))

    class Meta:
        unique_together = (('device_group', 'organization'),)


class Employee2Organization(_AbstractEntry):
    """Model of relation between employee and organization"""
    employee = models.ForeignKey(
        'Employee', db_column='usersid', related_name='organizations', on_delete=models.CASCADE)
    organization = models.ForeignKey(
        'Organization', db_column='companyid', related_name='employees', on_delete=models.CASCADE)

    def __str__(self):
        return self._str() + ('[%s] in [%s]' % (self.employee, self.organization))

    class Meta:
        unique_together = (('employee', 'organization'),)


class Device2DeviceGroup(_AbstractEntry):
    """Model of relation between device and device group"""
    device_group = models.ForeignKey(
        'DeviceGroup', db_column='devicegroupid', related_name='devices', on_delete=models.CASCADE)
    device = models.ForeignKey(
        'Device', db_column='devicesid', related_name='device_groups', on_delete=models.CASCADE)

    def __str__(self):
        return self._str() + ('[%s] in [%s]' % (self.device, self.device_group))

    class Meta:
        unique_together = (('device', 'device_group'),)
        db_table = 'devices_devicegroup'


class Device2Organization(_AbstractEntry):
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
    UNKNOWN = 0
    UNSUPPORTED = 1
    GET_VERSION = 2
    PING = 3

    FINGER_DELETE = 10
    FINGER_ENROLL = 11
    FINGER_SEARCH = 12

    CARD_DELETE = 20
    CARD_ENROLL = 21
    CARD_SEARCH = 22

    TEMPLATE_DELETE = 30
    TEMPLATE_ENROLL = 31
    TEMPLATE_SEARCH = 32

    FACE_DELETE = 40
    FACE_ENROLL = 41
    FACE_SEARCH = 42

    REQUEST_TYPE = [
        (UNKNOWN, 'Не существующий тип пакета'),
        (UNSUPPORTED, 'Запрошенная команда не поддерживается'),
        (GET_VERSION, 'Запрос версии протокола'),
        (PING, 'PING сервера'),

        (FINGER_DELETE, 'Запрос на удаление записи по изображению отпечатка'),
        (FINGER_ENROLL, 'Запрос на регистрацию записи по изображению отпечатка'),
        (FINGER_SEARCH, 'Запрос на поиск записи по изображению ранее зарегистрированного отпечатка'),

        (CARD_DELETE, 'Запрос на удаление записи по идентификатору, полученному со считывателя карт'),
        (CARD_ENROLL, 'Запрос на регистрацию записи по идентификатору, полученному со считывателя карт'),
        (CARD_SEARCH, 'Запрос на поиск записи по идентификатору, полученному со считывателя карт'),

        (TEMPLATE_DELETE, 'Запрос на удаление записи по шаблону отпечатка'),
        (TEMPLATE_ENROLL, 'Запрос на регистрацию записи по шаблону отпечатка'),
        (TEMPLATE_SEARCH, 'Запрос на поиск записи по ранее зарегистрированному шаблону отпечатка'),

        (FACE_DELETE, 'Запрос на удаление записи по изображению лица'),
        (FACE_ENROLL, 'Запрос на регистрацию записи по изображению лица'),
        (FACE_SEARCH, 'Запрос на поиск записи по изображению ранее зарегистрированного лица'),
    ]

    ERROR = 2
    VERSION = 3
    DELETE_OK = 10
    ENROLL_OK = 11
    SEARCH_OK = 12
    DUBLICATE = 13
    LOW_QUALITY = 14
    NO_MATCH = 15

    RESPONSE_TYPE = [
        (UNKNOWN, 'Не существующий тип пакета'),
        (UNSUPPORTED, 'Запрошенная команда не поддерживается'),
        (ERROR, 'Ошибка при выполнении запроса'),
        (VERSION, 'Запрос версии или PING сервера'),

        (DELETE_OK, 'Удаление отпечатка выполнено успешно'),
        (ENROLL_OK, 'Регистрация выполнена успешно'),
        (SEARCH_OK, 'Найдено совпадение'),

        (DUBLICATE, 'Регистрация невозможна так как обнаружено совпадение'),
        (LOW_QUALITY,
         'Идентификация невозможна из-за низкого качества идентификационных данных'),
        (NO_MATCH, 'Совпадение не обнаружено среди ранее зарегистрированных шаблонов'),
    ]

    ALGORITHM_FINGER_3 = 1
    ALGORITHM_FINGER_1 = 2
    ALGORITHM_FINGER_2 = 3
    ALGORITHM_FACE = 4
    ALGORITHM_CARD = 5

    ALGORITHM_TYPE = [
        (UNKNOWN, 'Не существующий тип пакета'),

        (ALGORITHM_FINGER_3, 'По отпечатку, возможно в основе его лежит стороний алгоритм'),
        (ALGORITHM_FINGER_1, 'По отпечатку, основной используемый алгоритм идентификации'),
        (ALGORITHM_FINGER_2, 'По отпечатку, не реализован в настоящей сборке'),

        (ALGORITHM_FACE, 'Не распознавание лиц'),

        (ALGORITHM_CARD, 'По номеру карты, дополнительный используемый алгоритм идентификации'),
    ]

    id = models.AutoField(primary_key=True)
    moment = models.DateTimeField(db_column='stamp', auto_now_add=True)
    request_type = models.IntegerField(
        db_column='request', choices=REQUEST_TYPE,)
    response_type = models.IntegerField(
        db_column='result', choices=RESPONSE_TYPE,)
    description = models.CharField(max_length=500, blank=True, null=True)
    algorithm_type = models.IntegerField(
        db_column='algorithm', choices=ALGORITHM_TYPE,)
    employee = models.ForeignKey(
        'Employee', db_column='usersid', on_delete=models.CASCADE, null=True)
    device = models.ForeignKey(
        'Device', db_column='devicesid', on_delete=models.CASCADE, null=True)
    templatesid = models.IntegerField(null=True)

    def __str__(self):
        return ('id[%s] [%s] with [%s] in [%s] do [%s] with result [%s] (%s)'
                % (self.id, self.employee, self.device, self.moment, self.request_type,
                   self.response_type, self.description))

    class Meta:
        db_table = 'querylog'
