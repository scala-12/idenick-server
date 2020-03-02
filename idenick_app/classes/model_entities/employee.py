"""employee model"""
import uuid
from typing import List, Optional

from django.db import models

from idenick_app.classes.constants.identification import algorithm_constants
from idenick_app.classes.model_entities.abstract_entries import AbstractEntry
from idenick_app.classes.model_entities.indentification_tepmplate import \
    IndentificationTepmplate
from idenick_app.classes.model_entities.organization import Organization
from idenick_app.classes.model_entities.relations.employee2organization import \
    Employee2Organization
from idenick_app.classes.utils.models_utils import get_related_entities_count


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
