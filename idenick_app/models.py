import uuid

from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver


class AbstractEntry4New(models.Model):    
    id = models.AutoField(primary_key=True)
    created_at = models.DateTimeField(auto_now_add=True)
    dropped_at = models.DateTimeField(null=True, blank=True)
    
    def save(self, *args, **kwargs):
        if not self.dropped_at:
            self.dropped_at = None
        super(AbstractEntry4New, self).save(*args, **kwargs)
    
    class Meta:
        abstract = True
        ordering = ["created_at"]


class AbstractEntry4Old(models.Model):    
    id = models.AutoField(primary_key=True)
    created_at = models.DateTimeField(db_column='rcreated', auto_now_add=True)
    dropped_at = models.DateTimeField(db_column='rdropped', null=True, blank=True)
    
    def save(self, *args, **kwargs):
        if not self.dropped_at:
            self.dropped_at = None
        super(AbstractEntry4Old, self).save(*args, **kwargs)
    
    class Meta:
        abstract = True
        ordering = ["created_at"]


class Employee(AbstractEntry4Old):
    guid = models.UUIDField(db_column='userid', default=uuid.uuid4, editable=False)
    surname = models.CharField(max_length=64)
    first_name = models.CharField(db_column='firstname', max_length=64)
    patronymic = models.CharField(max_length=64)
    
    def __str__(self):
        return '%s %s %s' % (self.surname, self.first_name, self.patronymic)
    
    class Meta:
        db_table = 'users'


class Organization(AbstractEntry4Old):
    guid = models.UUIDField(db_column='companyid', default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=250)
    address = models.CharField(max_length=500, blank=True)
    phone = models.CharField(max_length=50, blank=True)
    
    def __str__(self):
        return self.name
    
    class Meta:
        db_table = 'company'


@receiver(post_save, sender=Organization)
def create_organization(sender, instance, created, **kwargs):
    if created:
        Department.objects.create(
            organization=instance,
            name='default',
            address=instance.address,
        )
        user = User.objects.create_user(
            username=instance.guid,
            password=instance.guid,
        )
        user.login.type = Login.ADMIN
        user.login.organization = instance
        user.save()


class Department(AbstractEntry4Old):
    organization = models.ForeignKey('Organization', db_column='companyid', related_name='departments', on_delete=models.CASCADE)
    name = models.CharField(max_length=64)
    rights = models.IntegerField(default=0)
    address = models.CharField(max_length=500, blank=True)
    description = models.CharField(max_length=500, blank=True)
    
    def __str__(self):
        return '%s, %s' % (self.organization, self.name)
    
    class Meta:
        db_table = 'usergroup'


class Employee2Department(AbstractEntry4Old):
    department = models.ForeignKey('Department', db_column='usergroupid', related_name='employees', on_delete=models.CASCADE)
    employee = models.ForeignKey('Employee', db_column='usersid', related_name='departments', on_delete=models.CASCADE)
    
    def __str__(self):
        return 'd %s, e %s' % (self.department, self.employee)
    
    class Meta:
        db_table = 'users_usergroup'


class Login(models.Model):
    SUPERUSER = 'su'
    ADMIN = 'adm'
    CONTROLLER = 'ctrl'
    REGISTER = 'reg'
    NOT_SELECTED = 'none'
    USER_TYPE = [
        (ADMIN, 'admin'),
        (CONTROLLER, 'controller'),
        (REGISTER, 'register'),
        (SUPERUSER, 'superuser'),
        (NOT_SELECTED, 'not selected'),
    ]
    
    id = models.AutoField(primary_key=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    type = models.CharField(max_length=4, choices=USER_TYPE, blank=True)
    organization = models.ForeignKey('Organization', on_delete=models.CASCADE, null=True, blank=True)
    
    def save(self, *args, **kwargs):
        if not self.organization and not self.type:
            self.type = Login.NOT_SELECTED
        super(Login, self).save(*args, **kwargs)
    
    def delete(self, *args, **kwargs):
        self.user.delete()
        return super(self.__class__, self).delete(*args, **kwargs)
    
    def __str__(self):
        return '%s, %s' % (self.user, self.get_type_display())


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Login.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.login.save()

        