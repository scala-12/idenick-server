"""user view"""

from typing import Optional

from django.contrib.auth.models import User
from django.db.models.expressions import Value
from django.db.models.functions.text import Concat
from django.db.models.query_utils import Q
from django.shortcuts import get_object_or_404
from rest_framework import status

from idenick_app.models import Login, Organization
from idenick_rest_api_v0.classes.utils import (login_utils, request_utils,
                                               utils, views_utils)
from idenick_rest_api_v0.classes.views.abstract_view_set import AbstractViewSet
from idenick_rest_api_v0.serializers import (organization_serializers,
                                             user_serializers)


class _UserViewSet(AbstractViewSet):
    def get_serializer_by_action(self, action: str, is_full: Optional[bool] = False):
        result = None
        if (action == 'list') or (action == 'retrieve'):
            result = user_serializers.FullSerializer
        elif action == 'create':
            result = user_serializers.CreateSerializer
        elif action == 'partial_update':
            result = user_serializers.UpdateSerializer

        return result

    def _user_role(self, request):
        return Login.REGISTRATOR if (login_utils.get_login(request.user).role == Login.ADMIN) \
            else Login.CONTROLLER

    def _get_queryset(self, request, base_filter=False, with_dropped=False):
        queryset = Login.objects.filter(
            role=self._user_role(request)).exclude(user=None)
        dropped_filter = views_utils.get_deleted_filter(
            request, base_filter, with_dropped)
        if dropped_filter is views_utils.DeletedFilter.NON_DELETED.value:
            queryset = queryset.filter(dropped_at=None)
        elif dropped_filter is views_utils.DeletedFilter.DELETED_ONLY.value:
            queryset = queryset.exclude(dropped_at=None)

        if not base_filter:
            name_filter = request_utils.get_request_param(request, 'name')
            if name_filter is not None:
                users_ids = set(map(lambda i: user_serializers.ModelSerializer(i).data.get('id'), User.objects.annotate(
                    full_name_1=Concat('last_name', Value(' '), 'first_name'),
                    full_name_2=Concat('first_name', Value(' '), 'last_name'),
                ).filter(Q(full_name_1__icontains=name_filter) | Q(full_name_2__icontains=name_filter)
                         | Q(last_name__icontains=name_filter) | Q(first_name__icontains=name_filter))))
                queryset = queryset.filter(user_id__in=users_ids)

        login = login_utils.get_login(request.user)
        if login.role == Login.REGISTRATOR:
            queryset = queryset.filter(organization__id=login.organization_id)

        organization_filter = request_utils.get_request_param(
            request, 'organization', True, base_filter=base_filter)
        if organization_filter is not None:
            queryset = queryset.filter(organization__id=organization_filter)

        user_ids = queryset.values_list('user', flat=True)
        exists_ids = User.objects.filter(
            id__in=user_ids).values_list('id', flat=True)

        return queryset.filter(user_id__in=exists_ids)

    @login_utils.login_check_decorator(Login.REGISTRATOR, Login.ADMIN)
    def list(self, request):
        result = self._list_data(request)

        if 'full' in request.GET:
            organizations_ids = set(
                map(lambda d: d.get('organization'), result.get('data')))

            result.update(
                {'organizations': utils.get_organizations_by_id(organizations_ids)})

        return request_utils.response(result)

    def _retrieve_user(self, request, pk=None):
        result = self._retrieve_data(
            request=request, pk=pk, queryset=self._get_queryset(request))
        if 'full' in request.GET:
            result.update({'organization': organization_serializers.ModelSerializer(
                Organization.objects.get(id=result.get('data').get('organization'))).data})

        return request_utils.response(result)

    def _create(self, request):
        serializer_class = self.get_current_serializer()
        serializer = serializer_class(data=request.data)
        result = None

        if serializer.is_valid():
            current_user = login_utils.get_login(request.user)
            organization_id = None
            if current_user.role == Login.REGISTRATOR:
                organization_id = current_user.organization_id
            elif current_user.role == Login.ADMIN:
                organization_id = int(request.data.get('organization'))

            user_data = User(**serializer.data)
            if user_data.username and user_data.password:
                user = User.objects.create_user(
                    username=user_data.username, password=user_data.password)
                if (user_data.last_name):
                    user.last_name = user_data.last_name
                if (user_data.first_name):
                    user.first_name = user_data.first_name
                user.save()

                login = Login.objects.get(user=user)
                login.organization = Organization.objects.get(
                    id=organization_id)
                login.role = self._user_role(request)
                login.save()
                result = self._response4update_n_create(
                    data=login, code=status.HTTP_201_CREATED)
            else:
                result = self._response4update_n_create(
                    message='Name is empty')
        else:
            result = self._response4update_n_create(
                message=self._get_validation_error_msg(serializer.errors, User, True))

        return result

    def _partial_update(self, request, pk=None):
        login = get_object_or_404(Login.objects.all(), pk=pk)
        user = login.user

        serializer_class = self.get_current_serializer()
        serializer = serializer_class(request.data)
        update = serializer.data
        if update.get('first_name', '') != '':
            user.first_name = update.get('first_name')
        if update.get('last_name', '') != '':
            user.last_name = update.get('last_name')
        # it is for mysql-connector-python
        user.is_superuser = False
        user.is_staff = False

        user.save()
        result = self._response4update_n_create(data=login)

        return result


class UserViewSet(_UserViewSet):
    @login_utils.login_check_decorator(Login.REGISTRATOR, Login.ADMIN)
    def retrieve(self, request, pk=None):
        return self._retrieve_user(request, pk=pk)


class RegistratorViewSet(_UserViewSet):
    @login_utils.login_check_decorator(Login.ADMIN)
    def create(self, request):
        return self._create(request)

    @login_utils.login_check_decorator(Login.ADMIN)
    def retrieve(self, request, pk=None):
        return self._retrieve_user(request, pk=pk)

    @login_utils.login_check_decorator(Login.ADMIN)
    def partial_update(self, request, pk=None):
        return self._partial_update(request, pk)


class ControllerViewSet(_UserViewSet):
    @login_utils.login_check_decorator(Login.REGISTRATOR)
    def create(self, request):
        return self._create(request)

    @login_utils.login_check_decorator(Login.REGISTRATOR)
    def retrieve(self, request, pk=None):
        return self._retrieve_user(request, pk)

    @login_utils.login_check_decorator(Login.REGISTRATOR)
    def partial_update(self, request, pk=None):
        return self._partial_update(request, pk)
