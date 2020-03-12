"""employee model"""
import base64
import uuid
from typing import List, Optional

from django.db import models

from idenick_app.classes.constants.identification import algorithm_constants
from idenick_app.classes.model_entities.abstract_entries import AbstractEntry
from idenick_app.classes.model_entities.indentification_tepmplate import \
    IndentificationTepmplate
from idenick_app.classes.model_entities.organization import Organization
from idenick_app.classes.model_entities.relations.employee2department import \
    Employee2Department
from idenick_app.classes.model_entities.relations.employee2organization import \
    Employee2Organization
from idenick_app.classes.utils.models_utils import get_related_entities_count


class Employee(AbstractEntry):
    """Employee model"""
    guid = models.CharField(max_length=50, unique=True,
                            db_column='userid', default=uuid.uuid4)
    last_name = models.CharField(
        db_column='surname', max_length=64, db_index=True,)
    first_name = models.CharField(
        db_column='firstname', max_length=64, db_index=True,)
    patronymic = models.CharField(max_length=64, db_index=True,)

    def __str__(self):
        return self._str() + self.full_name

    @property
    def full_name(self):
        """return full employee name"""
        return '%s %s %s' % (self.last_name, self.first_name, self.patronymic)

    def _get_identification_templates(self, one_type: Optional[int] = None,
                                      many_types: Optional[List[int]] = None):
        """return employee has active identification template by type"""
        result = IndentificationTepmplate.objects.filter(
            employee_id=self.id, dropped_at=None,)
        if one_type is not None:
            result = result.filter(algorithm_type=one_type)
        elif many_types is not None:
            result = result.filter(algorithm_type__in=many_types)
        else:
            result = None

        return result

    def _has_identification_template(self, one_type: Optional[int] = None,
                                     many_types: Optional[List[int]] = None) -> bool:
        """return true if employee has active identification template by type"""
        templates = self._get_identification_templates(
            one_type=one_type, many_types=many_types)
        return False if templates is None else templates.exists()

    @property
    def has_card(self) -> bool:
        """return true if employee has active card identification"""
        return self._has_identification_template(
            one_type=algorithm_constants.CARD_ALGORITHM)

    @property
    def has_photo(self) -> bool:
        """return true if employee has active photo avatar"""
        return self._has_identification_template(
            one_type=algorithm_constants.EMPLOYEE_AVATAR)

    @property
    def photo(self) -> str:
        """return employee photo if exists"""
        templates = self._get_identification_templates(
            one_type=algorithm_constants.EMPLOYEE_AVATAR)
        return None if (templates is None) or (not templates.exists()) \
            else base64.b64encode(templates.first().template.strip()).decode()

    @property
    def organizations_count(self) -> int:
        return get_related_entities_count(Employee2Organization, {'employee_id': self.id},
                                          Organization, 'organization')

    def get_departments_count(self,
                              organization: Optional[Organization] = None,
                              organization_id: Optional[int] = None) -> int:
        org_id = None
        if organization is not None:
            org_id = organization.id
        else:
            org_id = organization_id

        queryset = Employee2Department.objects.filter(
            employee_id=self.id, department__dropped_at=None, dropped_at=None)
        if org_id is not None:
            queryset = queryset.filter(
                department__organization=org_id)

        return queryset.count()

    def _get_timesheet(self,
                       is_start: bool,
                       organization: Optional[Organization] = None,
                       organization_id: Optional[int] = None):
        org_id = None
        if organization is not None:
            org_id = organization.id
        else:
            org_id = organization_id

        result = None
        if org_id is not None:
            relations = Employee2Organization.objects.filter(
                organization=org_id, employee=self.id)

            if relations.exists():
                relation = relations.first()
                result = (relation.timesheet_start) if is_start else (
                    relation.timesheet_end)

            if result is None:
                org = Organization.objects.get(
                    id=org_id)
                result = (org.timesheet_start) if is_start else (
                    org.timesheet_end)

        return result

    def get_timesheet_start(self,
                            organization: Optional[Organization] = None,
                            organization_id: Optional[int] = None):
        return self._get_timesheet(True,
                                   organization=organization,
                                   organization_id=organization_id)

    def get_timesheet_end(self,
                          organization: Optional[Organization] = None,
                          organization_id: Optional[int] = None):
        return self._get_timesheet(False,
                                   organization=organization,
                                   organization_id=organization_id)

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
