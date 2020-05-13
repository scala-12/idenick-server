"""department view"""
from typing import Optional

from django.db.models.query_utils import Q
from django.http.request import QueryDict
from django.shortcuts import get_object_or_404
from rest_framework import status

from idenick_app.models import (Department, Employee2Department, Login,
                                Organization)
from idenick_rest_api_v0.classes.utils import (login_utils, request_utils,
                                               utils, views_utils)
from idenick_rest_api_v0.classes.views.abstract_view_set import AbstractViewSet
from idenick_rest_api_v0.serializers import (department_serializers,
                                             organization_serializers)


class DepartmentViewSet(AbstractViewSet):
    def get_serializer_by_action(self, action: str, is_full: Optional[bool] = False):
        result = None
        if (action == 'list') or (action == 'retrieve'):
            result = department_serializers.ModelSerializer
        elif action == 'create':
            result = department_serializers.CreateSerializer
        elif action == 'partial_update':
            result = department_serializers.UpdateSerializer

        return result

    def _get_queryset(self, request, base_filter=False, with_dropped=False):
        queryset = Department.objects.all()

        dropped_filter = views_utils.get_deleted_filter(
            request, base_filter, with_dropped)
        if dropped_filter is views_utils.DeletedFilter.NON_DELETED.value:
            queryset = queryset.filter(dropped_at=None)
        elif dropped_filter is views_utils.DeletedFilter.DELETED_ONLY.value:
            queryset = queryset.exclude(dropped_at=None)

        login = login_utils.get_login(request.user)
        role = login.role
        if (role == Login.CONTROLLER) or (role == Login.REGISTRATOR):
            queryset = queryset.filter(
                organization_id=login.organization_id)

        if not base_filter:
            name_filter = request_utils.get_request_param(request, 'name')
            if name_filter is not None:
                queryset = queryset.filter(name__icontains=name_filter)

        employee_filter = request_utils.get_request_param(
            request, 'employee', True, base_filter=base_filter)
        if employee_filter is not None:
            employee_departments = Employee2Department.objects.filter(
                employee_id=employee_filter).values_list('department_id', flat=True)
            queryset = queryset.filter(id__in=employee_departments)

        return queryset

    @login_utils.login_check_decorator(Login.REGISTRATOR, Login.CONTROLLER)
    def list(self, request):
        result = self._list_data(request)

        if 'full' in request.GET:
            organizations_ids = set(
                map(lambda d: d.get('organization'), result.get('data')))
            result.update(
                {'organizations': utils.get_organizations_by_id(organizations_ids)})

        return request_utils.response(result)

    @login_utils.login_check_decorator(Login.REGISTRATOR, Login.CONTROLLER)
    def retrieve(self, request, pk=None):
        result = self._retrieve_data(request, pk)

        if 'full' in request.GET:
            result.update({'organization': organization_serializers.ModelSerializer(
                Organization.objects.get(id=result.get('data',).get('organization'))).data})

        return request_utils.response(result)

    @login_utils.login_check_decorator(Login.REGISTRATOR)
    def create(self, request):
        serializer_class = self.get_current_serializer()

        serializer = serializer_class(data=request.data, context={
            'organization': login_utils.get_login(request.user).organization_id})
        result = None

        if serializer.is_valid():
            department = Department(**serializer.data)
            if Department.objects.filter(name=department.name).exists():
                result = self._response4update_n_create(
                    message=views_utils.ErrorMessage.UNIQUE_DEPARTMENT_NAME.value)
            else:
                department.save()
                result = self._response4update_n_create(
                    data=department, code=status.HTTP_201_CREATED)
        else:
            result = self._response4update_n_create(
                message=self._get_validation_error_msg(serializer.errors, Department))

        return result

    @login_utils.login_check_decorator(Login.REGISTRATOR)
    def partial_update(self, request, pk=None):
        login = login_utils.get_login(request.user)
        delete_restore_mode = ('delete' in request.data) or (
            'restore' in request.data)

        entity: Department = get_object_or_404(
            self._get_queryset(request, with_dropped=delete_restore_mode), pk=pk)

        result = None
        if delete_restore_mode:
            result = self._delete_or_restore(request, entity)
        else:
            serializer_class = self.get_current_serializer()
            result = None

            department_data = QueryDict('', mutable=True)
            department_data.update(request.data)
            organization_id = {'organization': login.organization_id}
            department_data.update(organization_id)

            valid_result = self._validate_on_update(
                pk, serializer_class, Department, department_data, organization_id)
            serializer = valid_result.get('serializer')
            update = valid_result.get('update')
            if update is not None:
                entity.name = update.name
                entity.rights = update.rights
                entity.address = update.address
                entity.description = update.description
                entity.show_in_report = update.show_in_report
                entity.save()
                result = self._response4update_n_create(data=entity)
            else:
                result = self._response4update_n_create(
                    message=self._get_validation_error_msg(serializer.errors, Department))

        return result

    def _alternative_valid(self, pk, data, errors, extra):
        return (len(errors.keys()) == 1) \
            and errors.keys().__contains__('non_field_errors') \
            and (errors.get('non_field_errors')[0].code == 'unique') \
            and not Department.objects.filter(name=data.get('name'), organization_id=extra.get('organization')) \
            .exclude(id=pk).exists()
