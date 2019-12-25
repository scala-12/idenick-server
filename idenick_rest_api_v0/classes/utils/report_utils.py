"""report utils"""
import io
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import List, Optional

import xlsxwriter
from django.core.exceptions import ObjectDoesNotExist
from django.http import FileResponse

from idenick_app.classes.utils import date_utils
from idenick_app.models import (Department, Device, Device2Organization,
                                DeviceGroup2Organization, Employee,
                                Employee2Department, Employee2Organization,
                                EmployeeRequest, Login, Organization)
from idenick_rest_api_v0.classes.utils import login_utils, request_utils, utils
from idenick_rest_api_v0.serializers import (DepartmentSerializers,
                                             DeviceSerializers,
                                             EmployeeRequestSerializers,
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
                devices_of_device_groups = Device.objects\
                    .filter(device_group__in=DeviceGroup2Organization.objects.filter(
                        organization_id=entity_id).values_list('device_group_id', flat=True))\
                    .values_list('id', flat=True)

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
                devices = Device.objects.filter(
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


class _HeaderName(Enum):
    """set of headers for report file"""
    DEVICE_GROUP = 'Проходная'
    MONTH = 'Месяц'
    DATE = 'Дата'
    WEEK_DAY = 'д.н.'
    EMPLOYEE_NAME = 'ФИО'
    TIMESHEET_ID = 'Табельный №'
    POSITION = 'Должность'
    DEPARTMENT = 'Подразделение'
    FACT_TIME_START = 'Приход'
    FACT_TIME_END = 'Уход'
    FACT_TIME_SUM = 'Прод.'


@dataclass
class _SubHeaderInfo:
    def __init__(self, caption: _HeaderName, size: Optional[int] = 8):
        self.caption = caption
        self.size = size


@dataclass
class _HeaderInfo:
    def __init__(self, caption: str, sub: Optional[List[_SubHeaderInfo]] = None):
        self.caption = caption
        self.sub = sub


def _get_department(line) -> Optional[Department]:
    """return department from report line"""
    department = None
    employee = line.get('employee')
    if employee is None:
        return department

    employee_organizations = set(Employee2Organization.objects.filter(
        employee=employee).values_list('organization_id', flat=True))
    if not employee_organizations:
        return department

    device = line.get('device')
    if device is not None:
        device_organizations = set(Device2Organization.objects.filter(
            device=device).values_list('organization_id', flat=True))
        employee_organizations = employee_organizations.intersection(
            device_organizations)
        if not employee_organizations:
            return department

    employee_departments = Employee2Department.objects.filter(
        employee=employee).values_list('department_id', flat=True)
    if not employee_departments.exists():
        return department

    organizations = Organization.objects.filter(id__in=employee_organizations)
    if not organizations:
        return department
    departments = Department.objects.filter(
        id__in=employee_departments, organization_id__in=organizations, show_in_report=True)

    if departments.exists():
        department = departments.first()

    return department


class _ReportFileWriter:
    """class for creation with report file"""
    HEADERS = [
        _HeaderInfo('Место и дата регистрации', [
            _SubHeaderInfo(_HeaderName.DEVICE_GROUP),
            _SubHeaderInfo(_HeaderName.MONTH),
            _SubHeaderInfo(_HeaderName.DATE),
            _SubHeaderInfo(_HeaderName.WEEK_DAY),
        ]),
        _HeaderInfo('Информация о сотруднике', [
            _SubHeaderInfo(_HeaderName.EMPLOYEE_NAME),
            _SubHeaderInfo(_HeaderName.TIMESHEET_ID),
            _SubHeaderInfo(_HeaderName.POSITION),
            _SubHeaderInfo(_HeaderName.DEPARTMENT),
        ]),
        _HeaderInfo('Факт', [
            _SubHeaderInfo(_HeaderName.FACT_TIME_START),
            _SubHeaderInfo(_HeaderName.FACT_TIME_END),
            _SubHeaderInfo(_HeaderName.FACT_TIME_SUM),
        ]),
    ]
    _NOT_FOUNDED = 'Не определен'
    LAST_HEADER_ROW_INDEX = 1

    def __init__(self):
        self._row = _ReportFileWriter.LAST_HEADER_ROW_INDEX + 1

        self._output_file = io.BytesIO()
        self._workbook = xlsxwriter.Workbook(
            self._output_file, {'in_memory': True})
        self._worksheet = self._workbook.add_worksheet()
        self._columns_map = {}
        self._columns_size = {}

        i = 0
        for header in _ReportFileWriter.HEADERS:
            self._worksheet.merge_range(
                first_row=0, first_col=i, last_row=0, last_col=(i + len(header.sub) - 1), data=header.caption)
            for sub in header.sub:
                self._worksheet.write(1, i, sub.caption.value)
                self._columns_map.update({sub.caption: i})
                self._columns_size.update(
                    {sub.caption: len(sub.caption.value)})
                i += 1

    def _get_column_index(self, column: _HeaderName):
        return self._columns_map.get(column)

    def _get_column_size(self, column: _HeaderName):
        return self._columns_size.get(column)

    def _write_cell(self, row: int, column: _HeaderName, value: str):
        self._worksheet.write(
            row, self._get_column_index(column), value)

        if self._columns_size.get(column) < len(value):
            self._columns_size.update({column: len(value)})

    def write_lines(self, queryset):
        for line in EmployeeRequestSerializers.HumanReadableSerializer(queryset, many=True).data:
            if line.get('employee_name') is None:
                line.update(employee_name=_ReportFileWriter._NOT_FOUNDED)
            if line.get('device_name') is None:
                line.update(device_name=_ReportFileWriter._NOT_FOUNDED)

            # TODO: сделать связь прибор-проходная n:1
            self._write_cell(self._row, _HeaderName.DEVICE_GROUP, '-')

            date_info = line.get('date_info')
            self._write_cell(self._row, _HeaderName.MONTH,
                             date_info.get('month'))
            self._write_cell(self._row, _HeaderName.DATE, date_info.get('day'))
            self._write_cell(self._row, _HeaderName.WEEK_DAY,
                             date_info.get('week_day'))

            self._write_cell(self._row, _HeaderName.EMPLOYEE_NAME,
                             line.get('employee_name'))
            self._write_cell(self._row, _HeaderName.TIMESHEET_ID, 'нет в базе')
            self._write_cell(self._row, _HeaderName.POSITION, 'нет в базе')

            department = _get_department(line)
            self._write_cell(self._row, _HeaderName.DEPARTMENT,
                             '-' if department is None else department.name)

            self._write_cell(self._row, _HeaderName.FACT_TIME_START, '-')
            self._write_cell(self._row, _HeaderName.FACT_TIME_END, '-')
            self._write_cell(self._row, _HeaderName.FACT_TIME_SUM, '-')

            self._row += 1

    def close(self, name: str) -> FileResponse:
        self._worksheet.write(
            self._row, 0, 'Кол-во: %d' % (self._row -
                                          1 - _ReportFileWriter.LAST_HEADER_ROW_INDEX))
        for header in _ReportFileWriter.HEADERS:
            for sub in header.sub:
                index = self._get_column_index(sub.caption)
                self._worksheet.set_column(
                    index, index, self._get_column_size(sub.caption) + 4)

        self._workbook.close()
        self._output_file.seek(0)

        file_name = 'Report ' + \
            name + ' ' + \
            datetime.now().strftime('%Y_%m_%d') + '.xlsx'

        response = FileResponse(
            streaming_content=self._output_file,
            as_attachment=True,
            filename=file_name,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

        response['Access-Control-Allow-Headers'] = 'Content-Type'

        return response


def get_report_file(request) -> FileResponse:
    """report file"""
    report_data = _get_report(request)

    writer = _ReportFileWriter()
    writer.write_lines(report_data.queryset)
    response = writer.close(report_data.name)

    return response


@dataclass
class ReportInfo:
    def __init__(self, queryset, count, extra):
        self.data = EmployeeRequestSerializers.ModelSerializer(
            queryset, many=True).data
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
