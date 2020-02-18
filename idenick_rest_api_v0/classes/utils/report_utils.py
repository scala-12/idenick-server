"""report utils"""
import io
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import List, Optional

import xlsxwriter
from django.http import FileResponse

from idenick_app.classes.utils import date_utils
from idenick_app.models import (Department, Device, Device2Organization,
                                DeviceGroup, DeviceGroup2Organization,
                                Employee, Employee2Department,
                                Employee2Organization, EmployeeRequest, Login,
                                Organization)
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
class _RequestsQuerysetInfo:
    def __init__(self, queryset,
                 name: str,
                 count: int,
                 organization: Optional[Organization] = None,
                 department: Optional[Department] = None):
        self.queryset = queryset
        self.organization = organization
        self.department = department
        self.name = name
        self.count = count


def _get_employees_requests(request,
                            without_none: Optional[bool] = False,
                            without_pagination: Optional[bool] = False) -> _RequestsQuerysetInfo:
    entity_id = request_utils.get_request_param(request, 'id', True)
    entity_type = _ReportType(
        request_utils.get_request_param(request, 'type'))

    page = None
    page_count = None
    per_page = None
    if not without_pagination:
        page = request_utils.get_request_param(request, 'from', True)
        page_count = request_utils.get_request_param(request, 'count', True, 1)
        per_page = request_utils.get_request_param(request, 'perPage', True)

    from_date = None
    from_time = request_utils.get_request_param(request, 'start')
    if from_time is not None:
        from_date = datetime.strptime(from_time, "%Y%m%d")

    to_date = None
    to_time = request_utils.get_request_param(request, 'end')
    if to_time is not None:
        to_date = datetime.strptime(
            to_time, "%Y%m%d") + timedelta(days=1, microseconds=-1)

    report_queryset = EmployeeRequest.objects.all()
    if without_none:
        report_queryset = report_queryset.exclude(employee=None)

    organization = None
    department = None
    login = login_utils.get_login(request.user)
    if (login.role == Login.CONTROLLER) or (login.role == Login.REGISTRATOR):
        organization_filter = login.organization.id
        organization = organization_filter
    name = None
    if entity_id is not None:
        if entity_type == _ReportType.EMPLOYEE:
            name = 'employee '
            report_queryset = report_queryset.filter(employee_id=entity_id)

            if (organization_filter is None) or Employee2Organization.objects \
                    .filter(employee_id=entity_id, organization_id=organization_filter) \
            .exists():
                report_queryset = report_queryset.filter(
                    employee_id=entity_id)
            else:
                report_queryset = EmployeeRequest.objects.none()
        elif entity_type == _ReportType.DEPARTMENT:
            name = 'department '

            department = Department.objects.get(id=entity_id)

            department_employees = Employee2Department.objects.filter(
                department_id=entity_id)
            if (organization is None) and department_employees.exists():
                organization = department_employees.first().department.organization

            employees = Employee.objects.filter(
                id__in=department_employees.values_list('employee_id', flat=True))
            report_queryset = report_queryset.filter(
                employee__in=employees)
        elif entity_type == _ReportType.ORGANIZATION:
            name = 'organization '

            if (organization_filter is None) or (organization_filter == entity_id):
                organization = entity_id
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
                devices_ids = Device.objects.filter(
                    device_group_id=entity_id).values_list('id', flat=True)

                report_queryset = report_queryset.filter(
                    device_id__in=devices_ids)
            else:
                report_queryset = EmployeeRequest.objects.none()

        name += str(entity_id)
    else:
        name = 'full'

    if organization is not None:
        organization_employees = Employee2Organization.objects.filter(
            organization_id=organization).values_list('employee_id', flat=True)
        organization_devices = Device2Organization.objects.filter(
            organization_id=organization).values_list('device_id', flat=True)

        reports = EmployeeRequest.objects.filter(
            employee_id__in=organization_employees).values_list('id', flat=True)\
            .union(EmployeeRequest.objects.filter(
                device_id__in=organization_devices).values_list('id', flat=True))

        report_queryset = report_queryset.filter(id__in=reports)

    report_queryset = report_queryset.order_by('-moment')

    if from_date is not None:
        report_queryset = report_queryset.filter(moment__gte=from_date)
    if to_date is not None:
        report_queryset = report_queryset.filter(moment__lte=to_date)

    paginated_report_queryset = None
    if (page is None) or (per_page is None):
        paginated_report_queryset = report_queryset
    else:
        offset = int(page) * int(per_page)
        limit = offset + int(per_page) * int(page_count)
        paginated_report_queryset = report_queryset[offset:limit]

    return _RequestsQuerysetInfo(queryset=paginated_report_queryset,
                                 name=name,
                                 count=report_queryset.count(),
                                 organization=None if organization is None
                                 else Organization.objects.get(id=organization),
                                 department=department,)


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
    FACT_TIME_START = 'Приход (факт)'
    FACT_TIME_END = 'Уход (факт)'
    FACT_TIME_COUNT = 'Прод. (факт)'
    PLAN_TIME_START = 'Приход (план)'
    PLAN_TIME_END = 'Уход (план)'
    PLAN_TIME_COUNT = 'Прод. (план)'


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


def _find_report_department(request: EmployeeRequest,
                            organization: Optional[Organization] = None) -> Optional[Department]:
    """return department from report line"""
    department = None
    employee = request.employee

    organizations = None
    if organization is None:
        employee_organizations = set(Employee2Organization.objects.filter(
            employee=employee).values_list('organization_id', flat=True))
        if not employee_organizations:
            return None

        device = request.device
        device_organizations = set(Device2Organization.objects.filter(
            device=device).values_list('organization_id', flat=True))
        employee_organizations = employee_organizations.intersection(
            device_organizations)

        if not employee_organizations:
            return None

        organizations = Organization.objects.filter(
            id__in=employee_organizations)

        if not organizations:
            return None
    else:
        organizations = [organization]

    employee_departments = Employee2Department.objects.filter(
        employee=employee).values_list('department_id', flat=True)
    if not employee_departments.exists():
        return None

    departments = Department.objects.filter(
        id__in=employee_departments, organization_id__in=organizations, show_in_report=True)

    if departments.exists():
        department = departments.first()

    return department


@dataclass
class RequestsInfo:
    def __init__(self, queryset, count, extra):
        self.data = EmployeeRequestSerializers.ModelSerializer(
            queryset, many=True).data
        self.count = count
        self.extra = extra


def get_employees_requests(request) -> RequestsInfo:
    """get request events"""
    info = _get_employees_requests(request)
    report_queryset = info.queryset

    login = login_utils.get_login(request.user)

    show_organization = 'showorganization' in request.GET
    entity_id = request_utils.get_request_param(request, 'id', True)
    entity_type = _ReportType(
        request_utils.get_request_param(request, 'type'))
    show_department = (entity_type == _ReportType.DEPARTMENT) and (
        entity_id is not None)
    show_device = 'showdevice' in request.GET

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
        devices_ids = set(report_queryset.values_list('device_id', flat=True))
        extra.update(devices=utils.get_objects_by_id(
            DeviceSerializers.ModelSerializer, clazz=Device, ids=devices_ids))

    return RequestsInfo(queryset=report_queryset, count=info.count, extra=extra)


@dataclass
class _ReportLine:
    def __init__(self,
                 id: int,
                 employee: Employee,
                 department: Optional[Department],
                 utc: str,
                 incoming_date: date_utils.DateInfo,
                 incoming_device: Optional[DeviceGroup] = None,
                 outcoming_date: Optional[date_utils.DateInfo] = None,
                 outcoming_device: Optional[DeviceGroup] = None,
                 ):
        self.id = id
        self.employee = employee
        self.department = department

        self.date = incoming_date.day
        self.month = incoming_date.month
        self.week_day = incoming_date.week_day
        self.utc = utc

        self.incoming_time = incoming_date.time
        outcoming_time = None
        time_count = None
        if outcoming_date is None:
            time_count = '-'
        else:
            outcoming_time = outcoming_date.time
            time_count = date_utils.duration_to_str(
                outcoming_date.date - incoming_date.date,
                show_positive_symbol=False)

        self.outcoming_time = outcoming_time
        self.time_count = time_count

        device_groups = None
        if (incoming_device is not None) \
                and (incoming_device.device_group is not None):
            device_groups = incoming_device.device_group.name
        else:
            device_groups = '-'

        if (outcoming_device is not None) \
                and (outcoming_device.device_group is not None):
            device_groups += ' / ' + outcoming_device.device_group.name
        self.device_groups = device_groups


@dataclass
class _ReportLinesInfo:
    def __init__(self, lines: List[_ReportLine], count: int, organization: Organization, name: str):
        self.lines = lines
        self.count = count
        self.organization = organization
        self.name = name


def _get_report_info(request) -> _ReportLinesInfo:
    """get report info for users"""
    report_data = _get_employees_requests(
        request, without_none=True, without_pagination=True)
    report_queryset = report_data.queryset

    queryset = EmployeeRequest.objects.filter(id__in=set(
        report_queryset.values_list('id', flat=True))).order_by('employee', 'moment')

    get_department = (lambda employee_request: _find_report_department(employee_request, report_data.organization)) \
        if report_data.department is None \
        else lambda _line: report_data.department

    employee_requests = list(queryset)
    i = 0
    i_end = len(employee_requests)

    report_lines = []
    while i < i_end:
        employee_request: EmployeeRequest = employee_requests[i]

        incoming_device = employee_request.device
        outcoming_device = None
        incoming_date = employee_request.get_date_info()
        outcoming_date = None
        next_employee_request = None
        if (i + 1) < i_end:
            next_employee_request: EmployeeRequest = employee_requests[i + 1]
            next_date_info = next_employee_request.get_date_info()
            if (employee_request.employee_id == next_employee_request.employee_id) \
                    and (incoming_date.day == next_date_info.day):
                outcoming_date = next_date_info
                outcoming_device = next_employee_request.device
                i += 1

        line = _ReportLine(id=employee_request.id,
                           employee=employee_request.employee,
                           department=get_department(employee_request),
                           incoming_date=incoming_date,
                           incoming_device=incoming_device,
                           outcoming_date=outcoming_date,
                           outcoming_device=outcoming_device,
                           utc=incoming_date.utc)
        report_lines.append(line)

        i += 1

    page = request_utils.get_request_param(request, 'from', True)
    page_count = request_utils.get_request_param(request, 'count', True, 1)
    per_page = request_utils.get_request_param(request, 'perPage', True)

    count = len(report_lines)
    if (page is not None) and (per_page is not None):
        offset = int(page) * int(per_page)
        limit = offset + int(per_page) * int(page_count)
        report_lines = report_lines[offset:limit]

    return _ReportLinesInfo(lines=report_lines,
                            count=count,
                            organization=report_data.organization,
                            name=report_data.name)


@dataclass
class ReportInfo:
    def __init__(self, info: _ReportLinesInfo):
        def serialize(line: _ReportLine):
            result = {}
            result.update(vars(line))
            result.update(employee=line.employee.id)
            result.update(
                department=None if line.department is None else line.department.id)

            return result

        self.data = list(map(serialize, info.lines))
        self.count = info.count

        employees = {}
        departments = {}
        for line in info.lines:
            if not (line.employee.id in employees):
                employees.update(
                    {line.employee.id: EmployeeSerializers.ModelSerializer(line.employee).data})
            if not ((line.department is None) or (line.department.id in departments)):
                departments.update(
                    {line.department.id:
                        DepartmentSerializers.ModelSerializer(line.department).data})

        extra = {'employees': employees, 'departments': departments}

        self.extra = extra


def get_report(request):
    """get report for users"""
    info = _get_report_info(request)

    return ReportInfo(info)


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
            _SubHeaderInfo(_HeaderName.FACT_TIME_COUNT),
        ]),
        _HeaderInfo('План', [
            _SubHeaderInfo(_HeaderName.PLAN_TIME_START),
            _SubHeaderInfo(_HeaderName.PLAN_TIME_END),
            _SubHeaderInfo(_HeaderName.PLAN_TIME_COUNT),
        ]),
    ]
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

    def _write_cell(self, row: int, column: _HeaderName, value: Optional[str]):
        if value is None:
            value = ''

        self._worksheet.write(
            row, self._get_column_index(column), value)

        if self._columns_size.get(column) < len(value):
            self._columns_size.update({column: len(value)})

    def write_lines(self, info: _ReportLinesInfo):
        for line in info.lines:
            self._write_cell(
                self._row, _HeaderName.DEVICE_GROUP, line.device_groups)

            self._write_cell(self._row, _HeaderName.MONTH, line.month)
            self._write_cell(self._row, _HeaderName.DATE, line.date)
            self._write_cell(self._row, _HeaderName.WEEK_DAY, line.week_day)

            self._write_cell(
                self._row, _HeaderName.EMPLOYEE_NAME, line.employee.full_name)
            self._write_cell(
                self._row, _HeaderName.TIMESHEET_ID, 'нет в базе')
            self._write_cell(self._row, _HeaderName.POSITION, 'нет в базе')
            self._write_cell(
                self._row, _HeaderName.DEPARTMENT, '-' if line.department is None
                else line.department.name)

            plan_start = '-'
            plan_end = '-'
            plan_count = '-'

            _plan_start = info.organization.timesheet_start_as_duration
            _plan_end = info.organization.timesheet_end_as_duration
            _plan_count = info.organization.timesheet_count
            if (_plan_start is None) or (_plan_end is None) or (_plan_count is None):
                plan_start = '-'
                plan_end = '-'
                plan_count = '-'
            else:
                plan_start = info.organization.timesheet_start
                plan_end = info.organization.timesheet_end
                plan_count = date_utils.duration_to_str(
                    _plan_count, show_positive_symbol=False)

            self._write_cell(
                self._row, _HeaderName.PLAN_TIME_START, plan_start)
            self._write_cell(
                self._row, _HeaderName.PLAN_TIME_END, plan_end)
            self._write_cell(
                self._row, _HeaderName.PLAN_TIME_COUNT, plan_count)

            self._write_cell(
                self._row, _HeaderName.FACT_TIME_START, line.incoming_time)
            self._write_cell(
                self._row, _HeaderName.FACT_TIME_END, '-' if line.outcoming_time is None
                else line.outcoming_time)
            self._write_cell(
                self._row, _HeaderName.FACT_TIME_COUNT, line.time_count)

            self._row += 1

    def close(self, name: str) -> FileResponse:
        """save file as response"""
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
    info = _get_report_info(request)

    writer = _ReportFileWriter()
    writer.write_lines(info)
    response = writer.close(info.name)

    return response
