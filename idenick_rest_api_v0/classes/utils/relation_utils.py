"""report utils"""
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Set, Union

from django.db.models.query_utils import Q
from rest_framework import serializers

from idenick_app.classes.model_entities.abstract_entries import \
    AbstractSimpleEntry
from idenick_app.classes.model_entities.department import Department
from idenick_app.classes.model_entities.device import Device
from idenick_app.classes.model_entities.device_group import DeviceGroup
from idenick_app.classes.model_entities.employee import Employee
from idenick_app.classes.model_entities.login import Login
from idenick_app.classes.model_entities.organization import Organization
from idenick_app.classes.model_entities.relations.device2organization import \
    Device2Organization
from idenick_app.classes.model_entities.relations.device_group2organization import \
    DeviceGroup2Organization
from idenick_app.classes.model_entities.relations.employee2department import \
    Employee2Department
from idenick_app.classes.model_entities.relations.employee2organization import \
    Employee2Organization
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
    is_device_2_device_group = (master_info.model is DeviceGroup) and (
        slave_info.model is Device)
    if is_device_2_device_group:
        if intersections:
            queryset = slave_info.model.objects.filter(
                **{master_info.key: master_id})
        else:
            queryset = slave_info.model.objects.exclude(
                **{master_info.key: master_id}).filter(**{master_info.key: None})
    else:
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
        if is_device_2_device_group:
            organization_devices = Device2Organization.objects.filter(
                organization_id=organization).values_list(slave_info.key, flat=True)
            queryset = queryset.filter(id__in=organization_devices)

            if intersections:
                organization_device_groups = DeviceGroup2Organization.objects.filter(
                    organization_id=organization).values_list(master_info.key, flat=True)
                queryset = queryset\
                    .filter(**{master_info.key + '__in': organization_device_groups})
        elif relation_clazz is Employee2Department:
            if slave_info.model is Employee:
                queryset = queryset.filter(id__in=Employee2Organization.objects.filter(
                    organization_id=organization).values_list('employee', flat=True))
            elif slave_info.model is Department:
                queryset = queryset.filter(organization_id=organization)

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

    if (master_info.model is DeviceGroup) and (slave_info.model is Device):
        if adding_mode:
            slave_info.model.objects.filter(
                id__in=success).update(device_group_id=master_id)
        else:
            slave_info.model.objects.filter(id__in=success,
                                            device_group_id=master_id).update(device_group_id=None)
    else:
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

            if relation_clazz is Device2Organization:
                _master = {'model': None, 'id': None}
                _slave = {'model': None, 'ids': None}
                if master_info.model is Organization:
                    _master.update(model=Organization, id=master_id)
                    _slave.update(model=DeviceGroup,
                                  ids=set(Device.objects.filter(id__in=getted_ids)
                                          .exclude(device_group=None)
                                          .values_list('device_group_id', flat=True)))
                else:
                    _master.update(model=DeviceGroup, id=Device.objects.filter(id=master_id)
                                   .values_list('device_group_id', flat=True)[0])
                    _slave.update(model=Organization, ids=getted_ids)

                if (_master.get('id') is not None) and (len(_slave.get('ids')) > 0):
                    _add_or_remove_relations(request,
                                             _master.get('model'),
                                             _master.get('id'),
                                             _slave.get('model'),
                                             getted_ids=_slave.get('ids'))
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
