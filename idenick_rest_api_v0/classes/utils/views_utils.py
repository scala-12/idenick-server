"""utils for views"""
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional

from idenick_app.models import (AbstractEntry, Checkpoint, Device, Employee,
                                Login, Organization)
from idenick_rest_api_v0.classes.utils import request_utils
from idenick_rest_api_v0.serializers import LoginSerializer


class ErrorMessage(Enum):
    UNIQUE_DEPARTMENT_NAME = 'Подразделение с таким названием уже существует'


class DeleteRestoreCheckStatus(Enum):
    """result of  delete/restore entity"""
    DELETABLE = 'DELETABLE'
    ALREADY_DELETED = 'ALREADY_DELETED'
    RESTORABLE = 'RESTORABLE'
    ALREADY_RESTORED = 'ALREADY_RESTORED'
    EXPIRED_TIME = 'EXPIRED_TIME'


@dataclass
class DeleteRestoreStatusChecker:
    """info about delete/restore entity"""

    def __init__(self, entity: AbstractEntry,
                 delete_mode: Optional[bool] = True,
                 anyTimeRestore: Optional[bool] = False):
        status = None
        if delete_mode:
            if entity.dropped_at is None:
                entity.dropped_at = datetime.now()
                status = DeleteRestoreCheckStatus.DELETABLE
            else:
                status = DeleteRestoreCheckStatus.ALREADY_DELETED
        elif entity.dropped_at is not None:
            if (anyTimeRestore or
                    (datetime.now() - entity.dropped_at.replace(tzinfo=None))
                    < timedelta(minutes=5)):
                entity.dropped_at = None
                status = DeleteRestoreCheckStatus.RESTORABLE
            else:
                status = DeleteRestoreCheckStatus.EXPIRED_TIME
        else:
            status = DeleteRestoreCheckStatus.ALREADY_RESTORED

        self.status = status
        self.entity = entity


class DeletedFilter(Enum):
    NON_DELETED = 'not deleted'
    DELETED_ONLY = 'deleted only'
    ALL = 'deleted and exists'


def get_deleted_filter(request, base_filter: bool, with_dropped: bool) -> DeletedFilter:
    dropped_filter = None
    if base_filter:
        dropped_filter = DeletedFilter.NON_DELETED.value
    elif with_dropped:
        dropped_filter = DeletedFilter.ALL.value
    elif request_utils.get_request_param(request, 'deletedOnly') is not None:
        dropped_filter = DeletedFilter.DELETED_ONLY.value
    else:
        dropped_filter = DeletedFilter.NON_DELETED.value

    return dropped_filter


def get_authentification(user):
    result = None
    if (user.is_authenticated):
        result = LoginSerializer.FullSerializer(
            Login.objects.get(user=user)).data

    return result


def get_counts():
    return {'organizations': Organization.objects.filter(dropped_at=None).count(),
            'devices': Device.objects.filter(dropped_at=None).count(),
            'checkpoints': Checkpoint.objects.filter(dropped_at=None).count(),
            'employees': Employee.objects.filter(dropped_at=None).count()}
