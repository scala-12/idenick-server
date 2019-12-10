"""report utils"""
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Set, Union

from django.db.models.query_utils import Q
from rest_framework import serializers

from idenick_app.models import (AbstractSimpleEntry, Department, Device, Device2DeviceGroup,
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


@dataclass
class EntityClassInfo:
    def __init__(self, model: AbstractSimpleEntry, serializer: serializers.ModelSerializer, key: str):
        self.model = model
        self.serializer = serializer
        self.key = key


_ENTRY2CLAZZ_N_SERIALIZER = {
    Device: EntityClassInfo(Device, DeviceSerializers.ModelSerializer, 'device_id'),
    DeviceGroup: EntityClassInfo(DeviceGroup, DeviceGroupSerializers.ModelSerializer, 'device_group_id'),
    Organization: EntityClassInfo(Organization, OrganizationSerializers.ModelSerializer, 'organization_id'),
    Employee: EntityClassInfo(Employee, EmployeeSerializers.ModelSerializer, 'employee_id'),
    Department: EntityClassInfo(Department, DepartmentSerializers.ModelSerializer, 'department_id'),
}

_CLASS_NAME2CLASS = {
    'devices': Device,
    'deviceGroups': DeviceGroup,
    'organizations': Organization,
    'employees': Employee,
    'departments': Department,
}


def _get_clazz_n_serializer(
        model: Union[str, AbstractSimpleEntry],
        is_many: bool = False) -> EntityClassInfo:
    model_clazz = _CLASS_NAME2CLASS.get(model[:1].lower() + model[1:] + ('' if is_many else 's')) \
        if isinstance(model, str) \
        else model
    return _ENTRY2CLAZZ_N_SERIALIZER.get(model_clazz, None)


def _get_relation_clazz(info1: EntityClassInfo,
                        info2: EntityClassInfo,
                        swap_if_undefined: bool = True) -> AbstractSimpleEntry:
    clazz1 = info1.model
    clazz2 = info2.model
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
        else (_get_relation_clazz(info2, info1, False) if swap_if_undefined else result)


def get_relates(slave_info: EntityClassInfo,
                master_info: EntityClassInfo,
                master_id: int,
                login: Login,
                intersections: bool = True,):
    """return relates queryset"""

    queryset = None
    relation_clazz = None

    relation_clazz = _get_relation_clazz(master_info, slave_info)
    related_object_ids = relation_clazz.objects.filter(
        Q(**{master_info.key: master_id}))\
        .filter(dropped_at=None).values_list(slave_info.key, flat=True)
    if intersections:
        queryset = slave_info.model.objects.filter(
            id__in=related_object_ids)
    else:
        queryset = slave_info.model.objects.exclude(
            id__in=related_object_ids)

    queryset = queryset.filter(dropped_at=None)  # remove deleted record

    role = login.role
    if role in (Login.CONTROLLER, Login.REGISTRATOR):
        organization = login.organization_id
        if relation_clazz is Employee2Department:
            if slave_info.model is Employee:
                queryset = queryset.filter(id__in=Employee2Organization.objects.filter(
                    organization_id=organization).values_list('employee', flat=True))
            elif slave_info.model is Department:
                queryset = queryset.filter(organization_id=organization)
        elif relation_clazz is Device2DeviceGroup:
            if slave_info.model is Device:
                queryset = queryset.filter(id__in=Device2Organization.objects.filter(
                    organization_id=organization).values_list('device', flat=True))
            elif slave_info.model is DeviceGroup:
                queryset = queryset.filter(id__in=DeviceGroup2Organization.objects.filter(
                    organization_id=organization).values_list('device_group', flat=True))

    return queryset


@dataclass
class RelationChangeResult:
    def __init__(self, success: List[int], failure: List[int]):
        self.success = success
        self.failure = failure


def _add_or_remove_relations(request,
                             master: Union[str, EntityClassInfo, AbstractSimpleEntry],
                             master_id: Union[int, str],
                             slave: Union[str, EntityClassInfo, AbstractSimpleEntry],
                             adding_mode: bool = True,
                             getted_ids: Optional[Set[int]] = None) -> RelationChangeResult:
    master_id = int(master_id)
    master_info: EntityClassInfo = master if isinstance(master, EntityClassInfo) \
        else _get_clazz_n_serializer(master, True)
    slave_info: EntityClassInfo = slave if isinstance(slave, EntityClassInfo) \
        else _get_clazz_n_serializer(slave)

    login = login_utils.get_login(request.user)

    exists_ids = get_relates(slave_info, master_info,
                             master_id, login).values_list('id', flat=True)

    if getted_ids is None:
        getted_ids = set(map(int, set(
            request.POST.get('ids').split(','))))

    success = getted_ids.difference(
        exists_ids) if adding_mode else getted_ids.intersection(exists_ids)

    master_key = master_info.key
    slave_key = slave_info.key
    relation_clazz = _get_relation_clazz(master_info, slave_info)
    if adding_mode:
        exists = relation_clazz.objects \
            .filter(**{master_key: master_id, (slave_key + '__in'): success})
        exists.update(dropped_at=None)
        not_exists = success.difference(
            exists.values_list(slave_key, flat=True))

        for new_id in not_exists:
            relation_clazz.objects.create(
                **{slave_key: new_id, master_key: master_id})
    else:
        relation_clazz.objects \
            .filter(**{master_key: master_id, (slave_key + '__in'): success}) \
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

    master_info = _get_clazz_n_serializer(
        master_name, True)
    slave_info = _get_clazz_n_serializer(
        slave_name)

    login = login_utils.get_login(request.user)
    queryset = get_relates(slave_info,
                           master_info, master_id, login, intersections=False,)

    return slave_info.serializer(queryset, many=True).data
