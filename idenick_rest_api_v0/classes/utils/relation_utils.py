"""report utils"""
from dataclasses import dataclass
from typing import List

from django.db import models
from django.db.models.query_utils import Q

from idenick_app.models import (Department, Device, Device2DeviceGroup,
                                Device2Organization, DeviceGroup,
                                DeviceGroup2Organization, Employee,
                                Employee2Department, Employee2Organization,
                                Login, Organization)
from idenick_rest_api_v0.classes.utils import login_utils
from idenick_rest_api_v0.serializers import (DepartmentSerializers,
                                             DeviceGroupSerializers,
                                             DeviceSerializers,
                                             EmployeeSerializers,
                                             OrganizationSerializers)


def get_relates(slave_clazz: models.Model,
                slave_key: str,
                relation_clazz: models.Model,
                master_key: str,
                master_id: int,
                login: Login,
                intersections: bool = True,):
    """return relates queryset"""
    related_object_ids = relation_clazz.objects.filter(
        Q(**{master_key: master_id})).filter(dropped_at=None).values_list(slave_key, flat=True)

    queryset = None
    if intersections:
        queryset = slave_clazz.objects.filter(id__in=related_object_ids)
    else:
        queryset = slave_clazz.objects.exclude(id__in=related_object_ids)

    queryset = queryset.filter(dropped_at=None)  # remove deleted record

    role = login.role
    if role in (Login.CONTROLLER, Login.REGISTRATOR):
        organization = login.organization_id
        if relation_clazz is Employee2Department:
            if slave_clazz is Employee:
                queryset = queryset.filter(id__in=Employee2Organization.objects.filter(
                    organization_id=organization).values_list('employee', flat=True))
            elif slave_clazz is Department:
                queryset = queryset.filter(organization_id=organization)
        elif relation_clazz is Device2DeviceGroup:
            if slave_clazz is Device:
                queryset = queryset.filter(id__in=Device2Organization.objects.filter(
                    organization_id=organization).values_list('device', flat=True))
            elif slave_clazz is DeviceGroup:
                queryset = queryset.filter(id__in=DeviceGroup2Organization.objects.filter(
                    organization_id=organization).values_list('device_group', flat=True))

    return queryset


def _get_relation_clazz(clazz1: models.Model, clazz2: models.Model,
                        swap_if_undefined: bool = True) -> models.Model:
    result = None
    if clazz1 is DeviceGroup:
        if clazz2 is Organization:
            result = DeviceGroup2Organization
        elif clazz2 is Device:
            result = Device2DeviceGroup
    elif clazz1 is Device:
        if clazz2 is Organization:
            result = Device2Organization
    elif clazz1 is Employee:
        if clazz2 is Organization:
            result = Employee2Organization
        if clazz2 is Department:
            result = Employee2Department

    return result if result is not None \
        else (_get_relation_clazz(clazz2, clazz1, False) if swap_if_undefined else result)


_ENTRY2CLAZZ_N_SERIALIZER = {
    'devices': {
        'clazz': Device,
        'serializer': DeviceSerializers.ModelSerializer,
        'key': 'device_id'},
    'deviceGroups': {
        'clazz': DeviceGroup,
        'serializer': DeviceGroupSerializers.ModelSerializer,
        'key': 'device_group_id'},
    'organizations': {
        'clazz': Organization,
        'serializer': OrganizationSerializers.ModelSerializer,
        'key': 'organization_id'},
    'employees': {
        'clazz': Employee,
        'serializer': EmployeeSerializers.ModelSerializer,
        'key': 'employee_id'},
    'departments': {
        'clazz': Department,
        'serializer': DepartmentSerializers.ModelSerializer,
        'key': 'department_id'},
}


def _get_clazz_n_serializer_by_entry_name(name: str, is_many: bool = False) -> models.Model:
    name = name[:1].lower() + name[1:] if name else ''
    return _ENTRY2CLAZZ_N_SERIALIZER.get(name + ('' if is_many else 's'), None)


@dataclass
class RelationChangeResult:
    def __init__(self, success: List[int], failure: List[int]):
        self.success = success
        self.failure = failure


def _add_or_remove_relations(request, master_name: str, master_id: int, slave_name: str,
                             adding_mode: bool = True) -> RelationChangeResult:
    master_info = _get_clazz_n_serializer_by_entry_name(
        master_name, True)
    slave_info = _get_clazz_n_serializer_by_entry_name(
        slave_name)

    master_clazz = master_info.get('clazz')
    slave_clazz = slave_info.get('clazz')

    login = login_utils.get_login(request.user)
    success = []
    failure = []

    master_key = master_info.get('key')
    slave_key = slave_info.get('key')
    relation_clazz = _get_relation_clazz(
        master_clazz, slave_clazz)

    exists_ids = get_relates(slave_clazz, slave_key, relation_clazz,
                             master_key, master_id, login).values_list('id', flat=True)

    getted_ids = set(map(int, set(
        request.POST.get('ids').split(','))))

    if adding_mode:
        success = getted_ids.difference(exists_ids)
        exists = relation_clazz.objects \
            .filter(**{master_key: master_id, (slave_key + '__in'): success})
        exists.update(dropped_at=None)
        not_exists = success.difference(exists.values_list('id', flat=True))

        for new_id in not_exists:
            relation_clazz.objects.create(
                **{slave_key: new_id, master_key: master_id})
    else:
        success = getted_ids.intersection(exists_ids)
        relation_clazz.objects.filter(**{master_key: master_id, (slave_key + '__in'): success}) \
            .update(dropped_at=datetime.now())

    failure = getted_ids.difference(success)

    return RelationChangeResult(success=success, failure=failure)


def add_relation(request, master_name: str, master_id: int,
                 slave_name: str) -> RelationChangeResult:
    """add relations"""
    return _add_or_remove_relations(request, master_name, master_id, slave_name, True)


def remove_relation(request, master_name: str, master_id: int,
                    slave_name: str) -> RelationChangeResult:
    """remove relations"""
    return _add_or_remove_relations(request, master_name, master_id, slave_name, False)


def get_non_related(request, master_name, master_id, slave_name):
    """get non-related entries"""

    master_info = _get_clazz_n_serializer_by_entry_name(
        master_name, True)
    slave_info = _get_clazz_n_serializer_by_entry_name(
        slave_name)

    master_key = master_info.get('key')
    slave_key = slave_info.get('key')
    relation_clazz = _get_relation_clazz(
        master_info.get('clazz'), slave_info.get('clazz'))

    login = login_utils.get_login(request.user)
    queryset = get_relates(slave_info.get('clazz'), slave_key,
                           relation_clazz, master_key, master_id, login, intersections=False,)

    return slave_info.get('serializer')(queryset, many=True).data
