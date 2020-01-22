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

            if (organization_filter is None) or Employee2Organization.objects \
                    .filter(employee_id=entity_id).filter(organization_id=organization_filter) \
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
                devices_ids = Device.objects.filter(
                    device_group_id=entity_id).values_list('id', flat=True)

                if organization_filter is not None:
                    devices_of_organization = Device2Organization.objects.filter(
                        organization_id=organization_filter).values_list('device_id', flat=True)

                    devices_ids = set(devices_ids).intersection(
                        set(devices_of_organization))

                report_queryset = report_queryset.filter(
                    device_id__in=devices_ids)
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
                               name=name, count=report_queryset.count(),
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


@dataclass
class _HumanReadableLine:
    _NOT_FOUNDED = 'Не определен'

    def __init__(self, line, organization: Optional[Organization], get_department_callback):
        self.timesheet_id = 'нет в базе'
        self.position = 'нет в базе'

        self.employee_name = line.get('employee_name')
        if self.employee_name is None:
            self.employee_name = _HumanReadableLine._NOT_FOUNDED

        self.device_name = line.get('device_name')
        self.device_group_name = None
        if self.device_name is None:
            self.device_name = _HumanReadableLine._NOT_FOUNDED
            self.device_group_name = _HumanReadableLine._NOT_FOUNDED
        if self.device_group_name is None:
            self.device_group_name = '-'

        date_info = line.get('date_info')
        self.month = date_info.get('month')
        self.day = date_info.get('day')
        self.week_day = date_info.get('week_day')
        self.time = date_info.get('time')
        self.date = date_info.get('date')

        department = get_department_callback(line)
        if department is None:
            self.department = '-'
        else:
            self.department = department.name

        self.employee: Optional[int] = line.get('employee')
        if organization is None:
            self.plan_start = 'Организация не выбрана'
            self.plan_end = 'Организация не выбрана'
        else:
            organization_employees = None
            if self.employee is not None:
                organization_employees = Employee2Organization.objects.filter(
                    employee=self.employee, organization=organization.id)

            if organization_employees is not None:
                if organization_employees.exists():
                    organization_employee = organization_employees.first()
                    if (organization_employee.timesheet_start is None) \
                            or (organization_employee.timesheet_start is None):
                        if (organization.timesheet_start is None) \
                                or (organization.timesheet_start is None):
                            self.plan_start = 'Не задано'
                            self.plan_end = 'Не задано'
                        else:
                            self.plan_start = organization.timesheet_start
                            self.plan_end = organization.timesheet_end
                    else:
                        self.plan_start = organization_employee.timesheet_start
                        self.plan_end = organization_employee.timesheet_end
                else:
                    # TODO починить фильтр по организации - показываются лишние
                    self.plan_start = 'Ошибка'
                    self.plan_end = 'Ошибка'
            else:
                self.plan_start = 'Сотрудник не определен'
                self.plan_end = 'Сотрудник не определен'

        _plan_start = date_utils.str_to_duration(self.plan_start)
        _plan_end = None if _plan_start is None else date_utils.str_to_duration(
            self.plan_end)
        if _plan_end is not None:
            self.plan_count = date_utils.duration_to_str(
                _plan_end - _plan_start, show_positive_symbol=False)
        else:
            self.plan_count = '-'


def _get_department(line, organization: Optional[Organization] = None) -> Optional[Department]:
    """return department from report line"""
    department = None
    employee = line.get('employee')
    if employee is None:
        return None

    organizations = None
    if organization is None:
        employee_organizations = set(Employee2Organization.objects.filter(
            employee=employee).values_list('organization_id', flat=True))
        if not employee_organizations:
            return None

        device = line.get('device')
        if device is not None:
            device_organizations = set(Device2Organization.objects.filter(
                device=device).values_list('organization_id', flat=True))
            employee_organizations = employee_organizations.intersection(
                device_organizations)
            if not employee_organizations:
                return None

        organizations = Organization.objects.filter(
            id__in=employee_organizations)
    else:
        organizations = [organization]

    employee_departments = Employee2Department.objects.filter(
        employee=employee).values_list('department_id', flat=True)
    if not employee_departments.exists():
        return None

    if not organizations:
        return None
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

    def write_lines(self,
                    queryset,
                    organization: Optional[Organization] = None,
                    department: Optional[Department] = None):
        queryset = EmployeeRequest.objects.filter(id__in=set(
            queryset.values_list('id', flat=True))).exclude(employee=None).order_by('employee', 'moment')
        if (organization is None) and (department is not None):
            organization = department.organization
        get_department = (lambda line: _get_department(line, organization)) if department is None \
            else lambda _line: department

        lines = list(map(lambda line: _HumanReadableLine(line=line,
                                                         organization=organization,
                                                         get_department_callback=get_department),
                         EmployeeRequestSerializers.HumanReadableSerializer(queryset, many=True).data))
        i = 0
        i_end = len(lines)
        while i < i_end:
            line = lines[i]
            self._write_cell(self._row, _HeaderName.DEVICE_GROUP,
                             line.device_group_name)

            self._write_cell(self._row, _HeaderName.MONTH, line.month)
            self._write_cell(self._row, _HeaderName.DATE, line.day)
            self._write_cell(self._row, _HeaderName.WEEK_DAY, line.week_day)

            self._write_cell(
                self._row, _HeaderName.EMPLOYEE_NAME, line.employee_name)
            self._write_cell(
                self._row, _HeaderName.TIMESHEET_ID, line.timesheet_id)
            self._write_cell(self._row, _HeaderName.POSITION, line.position)
            self._write_cell(
                self._row, _HeaderName.DEPARTMENT, line.department)
            self._write_cell(
                self._row, _HeaderName.PLAN_TIME_START, line.plan_start)
            self._write_cell(
                self._row, _HeaderName.PLAN_TIME_END, line.plan_end)
            self._write_cell(
                self._row, _HeaderName.PLAN_TIME_COUNT, line.plan_count)

            fact_start = line.time
            fact_end = None
            next_line = None
            fact_count = None
            if (i + 1) < i_end:
                next_line = lines[i + 1]
                next_employee: Optional[int] = next_line.employee
                if line.employee == next_employee:
                    fact_end = next_line.time
                    fact_count = date_utils.duration_to_str(
                        datetime.strptime(next_line.date, date_utils.DEFAULT_DATE_FORMAT)
                        - datetime.strptime(line.date, date_utils.DEFAULT_DATE_FORMAT),
                        show_positive_symbol=False)

            if fact_count is None:
                fact_count = '-'
            else:
                i += 1

            self._write_cell(
                self._row, _HeaderName.FACT_TIME_START, fact_start)
            self._write_cell(self._row, _HeaderName.FACT_TIME_END, fact_end)
            self._write_cell(
                self._row, _HeaderName.FACT_TIME_COUNT, fact_count)

            self._row += 1
            i += 1

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
    writer.write_lines(queryset=report_data.queryset,
                       organization=report_data.organization,
                       department=report_data.department)
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
