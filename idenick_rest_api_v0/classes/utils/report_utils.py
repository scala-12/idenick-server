"""report utils"""
import io
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

import xlsxwriter
from django.core.exceptions import ObjectDoesNotExist
from django.http import FileResponse

from idenick_app.models import (Department, Device, Device2DeviceGroup,
                                Device2Organization, DeviceGroup2Organization,
                                Employee, Employee2Department,
                                Employee2Organization, EmployeeRequest, Login,
                                Organization)
from idenick_rest_api_v0.classes.utils import login_utils, request_utils, utils
from idenick_rest_api_v0.serializers import (DepartmentSerializers,
                                             DeviceSerializers,
                                             EmployeeRequestSerializer,
                                             EmployeeSerializers,
                                             OrganizationSerializers)


class _ReportType(Enum):
    EMPLOYEE = 'EMPLOYEE'
    DEPARTMENT = 'DEPARTMENT'
    ORGANIZATION = 'ORGANIZATION'
    DEVICE = 'DEVICE'
    DEVICE_GROUP = 'DEVICE_GROUP'
    ALL = 'ALL'


@dataclass
class _ReportQuerysetInfo:
    def __init__(self, queryset, name: str, count: int):
        self.queryset = queryset
        self.name = name
        self.count = count


def _get_report(request) -> _ReportQuerysetInfo:
    entity_id = request_utils.get_request_param(request, 'id', True)
    entity_type = _ReportType(
        request_utils.get_request_param(request, 'type'))

    page = request_utils.get_request_param(request, 'from', True)
    page_count = request_utils.get_request_param(request, 'count', True, 1)
    per_page = request_utils.get_request_param(request, 'perPage', True)

    start_date = None
    start_time = request_utils.get_request_param(request, 'start')
    if start_time is not None:
        start_date = datetime.strptime(start_time, "%Y%m%d")

    end_date = None
    end_time = request_utils.get_request_param(request, 'end')
    if end_time is not None:
        end_date = datetime.strptime(
            end_time, "%Y%m%d") + timedelta(days=1, microseconds=-1)

    report_queryset = EmployeeRequest.objects.all()

    login = login_utils.get_login(request.user)
    if login.role == Login.CONTROLLER:
        organization_filter = login.organization.id
    name = None
    if entity_id is not None:
        if entity_type == _ReportType.EMPLOYEE:
            name = 'employee '

            if (organization_filter is None) or Employee2Organization.objects \
                    .filter(employee_id=entity_id).filter(organization_id=organization_filter) \
                .exists():
                report_queryset = report_queryset.filter(
                    employee_id=entity_id)
            else:
                report_queryset = EmployeeRequest.objects.none()
        elif entity_type == _ReportType.DEPARTMENT:
            name = 'department '

            employees = Employee.objects.filter(id__in=Employee2Department.objects.filter(
                department_id=entity_id).values_list('employee_id', flat=True))
            report_queryset = report_queryset.filter(
                employee__in=employees)
        elif entity_type == _ReportType.ORGANIZATION:
            name = 'organization '

            if (organization_filter is None) or (organization_filter == entity_id):
                employees = Employee2Organization.objects.filter(
                    organization_id=entity_id).values_list('employee_id', flat=True)
                devices_of_organization = Device2Organization.objects.filter(
                    organization_id=entity_id).values_list('device_id', flat=True)
                devices_of_device_groups = Device2DeviceGroup.objects\
                    .filter(device_group__in=DeviceGroup2Organization.objects.filter(
                        organization_id=entity_id).values_list('device_group_id', flat=True))

                devices = devices_of_organization.union(
                    devices_of_device_groups)

                reports = EmployeeRequest.objects.filter(
                    employee_id__in=employees).values_list('id', flat=True)\
                    .union(EmployeeRequest.objects.filter(
                        device_id__in=devices).values_list('id', flat=True))

                report_queryset = report_queryset.filter(id__in=reports)
            else:
                report_queryset = EmployeeRequest.objects.none()

        elif entity_type == _ReportType.DEVICE:
            name = 'device '

            if (organization_filter is None) \
                    or Device2Organization.objects.filter(device_id=entity_id)\
                .filter(organization_id=organization_filter).exists():
                report_queryset = report_queryset.filter(
                    device_id=entity_id)
            else:
                report_queryset = EmployeeRequest.objects.none()
        elif entity_type == _ReportType.DEVICE_GROUP:
            name = 'device_groups '

            if (organization_filter is None) \
                    or DeviceGroup2Organization.objects.filter(device_group_id=entity_id) \
                .filter(organization_id=organization_filter).exists():
                devices = Device2DeviceGroup.objects.filter(
                    device_group_id=entity_id).values_list('device_id', flat=True)

                if organization_filter is not None:
                    devices_of_organization = Device2Organization.objects.filter(
                        organization_id=organization_filter).values_list('device_id', flat=True)

                    devices = set(devices).intersection(
                        set(devices_of_organization))

                report_queryset = report_queryset.filter(
                    device_id__in=devices)
            else:
                report_queryset = EmployeeRequest.objects.none()

        name += str(entity_id)
    else:
        name = 'full'

    report_queryset = report_queryset.order_by('-moment')

    if start_date is not None:
        report_queryset = report_queryset.filter(moment__gte=start_date)
    if end_date is not None:
        report_queryset = report_queryset.filter(moment__lte=end_date)

    paginated_report_queryset = None
    if (page is None) or (per_page is None):
        paginated_report_queryset = report_queryset
    else:
        offset = int(page) * int(per_page)
        limit = offset + int(per_page) * int(page_count)
        paginated_report_queryset = report_queryset[offset:limit]

    return _ReportQuerysetInfo(queryset=paginated_report_queryset,
                               name=name, count=report_queryset.count())


def get_report_file(request) -> FileResponse:
    """report file"""
    report_data = _get_report(request)
    queryset = report_data.queryset

    output_file = io.BytesIO()
    workbook = xlsxwriter.Workbook(output_file, {'in_memory': True})
    worksheet = workbook.add_worksheet()

    not_founded = 'Не определен'
    row = 1
    for line in queryset:
        employee = None
        try:
            if line.employee is not None:
                employee = line.employee
        except ObjectDoesNotExist:
            pass
        device = None
        try:
            if line.device is not None:
                device = line.device
        except ObjectDoesNotExist:
            pass

        fields = [
            not_founded if employee is None else employee.get_full_name(),
            not_founded if device is None else device.name,
            not_founded if device is None else device.mqtt,
            line.moment.strftime('%Y-%m-%d %H:%M:%S'),
            not_founded if line.request_type is None else line.get_request_type_display(),
            not_founded if line.response_type is None else line.get_response_type_display(),
            line.description,
            not_founded if line.algorithm_type is None else line.get_algorithm_type_display(),
        ]
        col = 0
        for field in fields:
            worksheet.write(row, col, field)
            col += 1
        row += 1

    def get_max_field_lenght_list(field, caption=None):
        return 4 + max(list(len(str(s)) for s in set(queryset.values_list(field, flat=True)))
                       + [0 if caption is None else len(caption)])

    max_employee_name_lenght = 4 + max(list(
        map(lambda e: len(e.get_full_name()),
            Employee.objects.filter(id__in=set(
                queryset.values_list('employee', flat=True)))
            )) + [len('Сотрудник')])

    fields = [
        {'name': 'Сотрудник', 'length': max_employee_name_lenght},
        {'name': 'Устройство', 'length': get_max_field_lenght_list(
            'device__name', 'Устройство')},
        {'name': 'ИД устройства', 'length': get_max_field_lenght_list(
            'device__mqtt', 'ИД устройства')},
        {'name': 'Дата', 'length': 23},
        {'name': 'Запрос', 'length': get_max_field_lenght_list(
            'request_type', 'Запрос')},
        {'name': 'Ответ', 'length': get_max_field_lenght_list(
            'response_type', 'Ответ')},
        {'name': 'Описание', 'length': get_max_field_lenght_list(
            'description', 'Описание')},
        {'name': 'Алгоритм', 'length': get_max_field_lenght_list(
            'algorithm_type', 'Алгоритм')},
    ]
    i = 0
    for field in fields:
        worksheet.write(0, i, field.get('name'))
        worksheet.set_column(i, i, field.get('length'))
        i += 1

    workbook.close()

    output_file.seek(0)

    file_name = 'Report ' + \
        report_data.name + ' ' + \
        datetime.now().strftime('%Y_%m_%d') + '.xlsx'

    response = FileResponse(
        streaming_content=output_file,
        as_attachment=True,
        filename=file_name,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

    response['Access-Control-Allow-Headers'] = 'Content-Type'

    return response


@dataclass
class ReportInfo:
    def __init__(self, queryset, count, extra):
        self.data = EmployeeRequestSerializer(queryset, many=True).data
        self.count = count
        self.extra = extra


def get_report(request) -> ReportInfo:
    """return report"""
    login = login_utils.get_login(request.user)

    show_organization = 'showorganization' in request.GET
    entity_id = request_utils.get_request_param(request, 'id', True)
    entity_type = _ReportType(
        request_utils.get_request_param(request, 'type'))
    show_department = (entity_type == _ReportType.DEPARTMENT) and (
        entity_id is not None)
    show_device = 'showdevice' in request.GET

    report_data = _get_report(request)
    report_queryset = report_data.queryset

    extra = {}

    employees_ids = set(
        report_queryset.values_list('employee_id', flat=True))
    employees_queryset = Employee.objects.filter(
        id__in=employees_ids)

    extra.update(employees=utils.get_objects_by_id(
        EmployeeSerializers.ModelSerializer, queryset=employees_queryset))

    if show_organization:
        if login.role == Login.CONTROLLER:
            extra.update(organizations={
                login.organization_id: OrganizationSerializers.ModelSerializer(
                    Organization.objects.get(pk=login.organization_id)).data})

    if show_department:
        extra.update({'department': DepartmentSerializers.ModelSerializer(
            Department.objects.get(id=entity_id)).data})

    if show_device:
        devices_ids = set(
            report_queryset.values_list('device_id', flat=True))
        extra.update(devices=utils.get_objects_by_id(
            DeviceSerializers.ModelSerializer, clazz=Device, ids=devices_ids))

    return ReportInfo(queryset=report_queryset, count=report_data.count, extra=extra)
