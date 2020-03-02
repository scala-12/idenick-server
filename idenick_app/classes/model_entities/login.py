"""Login model"""
import uuid

from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver

from idenick_app.classes.model_entities.abstract_entries import \
    AbstractSimpleEntry


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


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """create user info record"""
    if created:
        Login.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """create user info record"""
    instance.login.save()
