"""employee view"""

import base64
from datetime import datetime
from typing import Optional

from django.db.models.expressions import Value
from django.db.models.functions.text import Concat
from django.db.models.query_utils import Q
from django.shortcuts import get_object_or_404
from rest_framework import status

from idenick_app.classes.constants.identification import algorithm_constants
from idenick_app.classes.model_entities.relations.employee2organization import \
    Employee2Organization
from idenick_app.models import (Employee, Employee2Department,
                                IndentificationTepmplate, Login)
from idenick_rest_api_v0.classes.utils import (login_utils, request_utils,
                                               views_utils)
from idenick_rest_api_v0.classes.utils.mqtt_utils import check_biometry
from idenick_rest_api_v0.classes.views.abstract_view_set import AbstractViewSet
from idenick_rest_api_v0.serializers import (EmployeeSerializers,
                                             OrganizationSerializers)


class EmployeeViewSet(AbstractViewSet):
    def get_serializer_by_action(self, action: str, is_full: Optional[bool] = False):
        result = None
        if (action == 'list') or (action == 'retrieve'):
            result = EmployeeSerializers.FullModelSerializer if is_full \
                else EmployeeSerializers.ModelSerializer
        elif (action == 'create') or (action == 'partial_update'):
            result = EmployeeSerializers.CreateSerializer

        return result

    def _get_queryset(self, request, base_filter=False, with_dropped=False):
        queryset = Employee.objects.all()

        login = login_utils.get_login(request.user)

        dropped_filter = views_utils.get_deleted_filter(
            request, base_filter, with_dropped)
        if login.role == Login.ADMIN:
            if dropped_filter is views_utils.DeletedFilter.NON_DELETED.value:
                queryset = queryset.filter(dropped_at=None)
            elif dropped_filter is views_utils.DeletedFilter.DELETED_ONLY.value:
                queryset = queryset.exclude(dropped_at=None)
        else:
            queryset = queryset.filter(dropped_at=None)

        organization_filter = None
        if (login.role == Login.CONTROLLER) or (login.role == Login.REGISTRATOR):
            organization_filter = login.organization_id
        elif login.role == Login.ADMIN:
            organization_filter = request_utils.get_request_param(
                request, 'organization', True, base_filter=base_filter)

        if not base_filter:
            name_filter = request_utils.get_request_param(request, 'name')
            if name_filter is not None:
                queryset = queryset.annotate(
                    __full_name=Concat('last_name', Value(
                        ' '), 'first_name', Value(' '), 'patronymic'),
                ).filter(Q(__full_name__icontains=name_filter)
                         | Q(last_name__icontains=name_filter)
                         | Q(first_name__icontains=name_filter)
                         | Q(patronymic__icontains=name_filter))

        department_filter = request_utils.get_request_param(
            request, 'department', True, base_filter=base_filter)
        if (department_filter is not None):
            department_employees = Employee2Department.objects.filter(
                department_id=department_filter)
            if dropped_filter is views_utils.DeletedFilter.NON_DELETED.value:
                department_employees = department_employees.filter(
                    dropped_at=None)
            elif dropped_filter is views_utils.DeletedFilter.DELETED_ONLY.value:
                department_employees = department_employees.exclude(
                    dropped_at=None)

            queryset = queryset.filter(
                id__in=department_employees.values_list('employee', flat=True))

        if organization_filter is not None:
            employee_id_list = queryset.values_list('id', flat=True)
            employees_queryset = Employee2Organization.objects.filter(
                organization_id=organization_filter, employee_id__in=employee_id_list)

            if (login.role == Login.ADMIN) \
                    or (dropped_filter is views_utils.DeletedFilter.NON_DELETED.value):
                employees_queryset = employees_queryset.filter(dropped_at=None)
            elif dropped_filter is views_utils.DeletedFilter.DELETED_ONLY.value:
                employees_queryset = employees_queryset.exclude(
                    dropped_at=None)

            queryset = queryset.filter(
                id__in=employees_queryset.values_list('employee', flat=True))

        return queryset

    @login_utils.login_check_decorator()
    def list(self, request):
        result = self._list_data(request)

        return request_utils.response(result)

    @login_utils.login_check_decorator()
    def retrieve(self, request, pk):
        full_info = 'full' in request.GET
        result = self._retrieve_data(request, pk, is_full=full_info)

        login = login_utils.get_login(request.user)
        if (login.role == Login.CONTROLLER) or (login.role == Login.REGISTRATOR):
            entity = result.get('data')
            if entity.get('dropped_at') is None:
                dropped_at = Employee2Organization.objects.get(
                    employee=pk, organization=login.organization).dropped_at
                if not (dropped_at is None):
                    entity.update(dropped_at=dropped_at.isoformat())
                    result.update(data=entity)

            result.update({'departments_count': Employee2Department.objects.filter(
                employee_id=pk).filter(department__organization_id=login.organization_id).count()})
            if full_info:
                organization = OrganizationSerializers.ModelSerializer(
                    login.organization).data

                result.update({'organization': organization})

        return request_utils.response(result)

    @login_utils.login_check_decorator(Login.REGISTRATOR, Login.ADMIN)
    def partial_update(self, request, pk=None):
        login = login_utils.get_login(request.user)
        delete_restore_mode = ('delete' in request.data) or (
            'restore' in request.data)

        entity: Employee = get_object_or_404(
            self._get_queryset(request, with_dropped=delete_restore_mode), pk=pk)

        result = None
        if delete_restore_mode:
            if login.role == Login.ADMIN:
                result = self._delete_or_restore(request, entity)
            elif login.role == Login.REGISTRATOR:
                relations = Employee2Organization.objects.filter(organization=login.organization,
                                                                 employee=entity)
                if relations.exists():
                    delete_or_restore_result = self._delete_or_restore(
                        request, entity=relations.first(), return_entity=entity)
                    if delete_or_restore_result.data.get('success'):
                        result = self._response4update_n_create(data=entity)
                    else:
                        result = delete_or_restore_result
        else:
            serializer_class = self.get_current_serializer()
            serializer = serializer_class(data=request.data)
            if serializer.is_valid():
                data = serializer.data
                entity.last_name = data.get('last_name', entity.last_name)
                entity.first_name = data.get(
                    'first_name', entity.first_name)
                entity.patronymic = data.get(
                    'patronymic', entity.patronymic)

                has_photo = entity.has_photo
                old_template = IndentificationTepmplate.objects.get(
                    employee_id=entity.id,
                    algorithm_type=algorithm_constants.EMPLOYEE_AVATAR,
                    dropped_at=None) if has_photo else None
                new_template = None
                if ('photo' in request.data) and (len(request.data.get('photo').strip()) != 0):
                    template_data = base64.b64decode(
                        request.data.get('photo').encode())
                    biometry_check_result = check_biometry(template_data)
                    if (entity.has_face
                            and (biometry_check_result.employee == entity.id))\
                            or (not entity.has_face and not biometry_check_result.exists):
                        new_template = IndentificationTepmplate(**{
                            'employee_id': entity.id,
                            'algorithm_type': algorithm_constants.EMPLOYEE_AVATAR,
                            'algorithm_version': 0,
                            'template': template_data,
                            'quality': 100,
                        })
                    else:
                        new_template = old_template

                if has_photo:
                    if (new_template is None) or (old_template.template != new_template.template):
                        old_template.dropped_at = datetime.now()
                        old_template.save()
                        new_template.save()
                elif new_template is not None:
                    new_template.save()

                entity.save()

                if login.role == Login.REGISTRATOR:
                    organization_employee = Employee2Organization.objects.get(
                        organization=login.organization.id, employee=entity.id)
                    organization_employee.timesheet_start = request.data.get(
                        'timesheet_start', None)
                    organization_employee.timesheet_end = request.data.get(
                        'timesheet_end', None)
                    organization_employee.save()

                result = self._response4update_n_create(data=entity)

        return result

    @login_utils.login_check_decorator(Login.REGISTRATOR, Login.ADMIN)
    def create(self, request):
        serializer_class = self.get_current_serializer()
        serializer = serializer_class(data=request.data)
        result = None

        login = login_utils.get_login(request.user)
        if serializer.is_valid():
            employee = Employee(**serializer.data)
            employee.save()

            organization = None
            if login.role == Login.REGISTRATOR:
                organization = login.organization_id
            elif login.role == Login.ADMIN:
                organization = request_utils.get_request_param(
                    request, 'organization', is_int=True)

            if organization is not None:
                Employee2Organization.objects.create(
                    **{'organization_id': organization, 'employee_id': employee.id})

            result = self._response4update_n_create(
                data=employee, code=status.HTTP_201_CREATED)
        else:
            result = self._response4update_n_create(
                message=self._get_validation_error_msg(serializer.errors, Employee))

        return result
