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
    dropped_at = models.DateTimeField(db_column='rdropped', null=True, blank=True)
    
    def save(self, *args, **kwargs):
        if not self.dropped_at:
            self.dropped_at = None
        super(_AbstractEntry4Old, self).save(*args, **kwargs)
    
    class Meta:
        abstract = True
        ordering = ["created_at"]


class Employee(_AbstractEntry4Old):
    guid = models.UUIDField(db_column='userid', default=uuid.uuid4, editable=False)
    surname = models.CharField(max_length=64)
    first_name = models.CharField(db_column='firstname', max_length=64)
    patronymic = models.CharField(max_length=64)
    
    def __str__(self):
        return '%s %s %s %s' % (self.id, self.surname, self.first_name, self.patronymic)
    
    class Meta:
        db_table = 'users'


class Organization(_AbstractEntry4Old):
    guid = models.UUIDField(db_column='companyid', default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=250, unique=True, verbose_name='название')
    address = models.CharField(max_length=500, blank=True)
    phone = models.CharField(max_length=50, blank=True)
    
    def __str__(self):
        return '%s %s %s %s' % (self.id, self.name, self.address, self.phone)
    
    class Meta:
        db_table = 'company'
        verbose_name_plural = 'Организации'
        verbose_name = 'Организация'


@receiver(post_save, sender=Organization)
def create_organization(sender, instance, created, **kwargs):
    if created:
        Department.objects.create(
            organization=instance,
            name='default',
            address=instance.address,
        )


class Department(_AbstractEntry4Old):
    organization = models.ForeignKey('Organization', db_column='companyid', related_name='departments', on_delete=models.CASCADE)
    name = models.CharField(max_length=64)
    rights = models.IntegerField(default=0)
    address = models.CharField(max_length=500, blank=True)
    description = models.CharField(max_length=500, blank=True)
    
    def __str__(self):
        return '%s %s %s %s %s %s' % (self.id, self.organization, self.name, self.rights, self.address, self.description)
    
    class Meta:
        db_table = 'usergroup'


class Employee2Department(_AbstractEntry4Old):
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
    REGISTRATOR = 'reg'
    NOT_SELECTED = 'none'
    USER_ROLE = [
        (ADMIN, 'admin'),
        (CONTROLLER, 'controller'),
        (REGISTRATOR, 'registrator'),
        (SUPERUSER, 'superuser'),
        (NOT_SELECTED, 'not selected'),
    ]
    
    id = models.AutoField(primary_key=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=4, choices=USER_ROLE, blank=True)
    organization = models.ForeignKey('Organization', on_delete=models.CASCADE, null=True, blank=True)
    
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
        return '%s %s %s %s %s' % (self.id, self.organization, self.user.username, self.user.first_name + ' ' + self.user.last_name, self.get_role_display())


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Login.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.login.save()
        
