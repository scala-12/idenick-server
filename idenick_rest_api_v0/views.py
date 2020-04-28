"""views"""
from typing import Optional

from django.contrib.auth.models import User
from django.db.models.expressions import Value
from django.db.models.functions.text import Concat
from django.db.models.query_utils import Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from idenick_app.classes.constants.identification import algorithm_constants
from idenick_app.models import (Checkpoint, Checkpoint2Organization,
                                Department, Device, Device2Organization,
                                Employee, Employee2Department,
                                Employee2Organization,
                                IndentificationTepmplate, Login, Organization)
from idenick_rest_api_v0.classes.utils import (login_utils, relation_utils,
                                               report_utils, request_utils,
                                               utils, views_utils)
from idenick_rest_api_v0.classes.utils.mqtt_utils import (BiometryType,
                                                          check_biometry)
from idenick_rest_api_v0.classes.utils.mqtt_utils import \
    registrate_biometry as registrate_biometry_by_device
from idenick_rest_api_v0.classes.views.abstract_view_set import AbstractViewSet
from idenick_rest_api_v0.classes.views.checkpoint_view_set import \
    CheckpointViewSet
from idenick_rest_api_v0.classes.views.department_view_set import \
    DepartmentViewSet
from idenick_rest_api_v0.classes.views.device_view_set import DeviceViewSet
from idenick_rest_api_v0.classes.views.employee_view_set import EmployeeViewSet
from idenick_rest_api_v0.classes.views.organization_view_set import \
    OrganizationViewSet
from idenick_rest_api_v0.classes.views.user_view_set import (
    ControllerViewSet, RegistratorViewSet, UserViewSet)
from idenick_rest_api_v0.serializers import (CheckpointSerializers,
                                             DepartmentSerializers,
                                             DeviceSerializers,
                                             EmployeeSerializers,
                                             LoginSerializer,
                                             OrganizationSerializers,
                                             UserSerializer)


@api_view(['GET'])
def get_current_user(request):
    user = request.user

    return Response({'data': views_utils.get_authentification(user)})


@api_view(['GET'])
@login_utils.login_check_decorator(Login.ADMIN)
def get_counts(request):
    return Response(views_utils.get_counts())


@api_view(['GET'])
@login_utils.login_check_decorator(Login.CONTROLLER, Login.REGISTRATOR, Login.ADMIN)
def get_report_file(request):
    """report file"""
    return report_utils.get_report_file(request)


@api_view(['GET'])
@login_utils.login_check_decorator(Login.CONTROLLER, Login.REGISTRATOR, Login.ADMIN)
def get_report(request):
    """return report"""
    return Response(vars(report_utils.get_report(request)))


@api_view(['GET'])
@login_utils.login_check_decorator(Login.CONTROLLER, Login.REGISTRATOR, Login.ADMIN)
def get_employees_requests(request):
    """return report"""
    return Response(vars(report_utils.get_employees_requests(request)))


@api_view(['POST'])
@login_utils.login_check_decorator(Login.REGISTRATOR, Login.ADMIN)
def add_relation(request, master_name, master_id, slave_name):
    """add relations"""
    return Response({'data': vars(relation_utils.add_relation(request,
                                                              master_name,
                                                              master_id,
                                                              slave_name))})


@api_view(['POST'])
@login_utils.login_check_decorator(Login.REGISTRATOR, Login.ADMIN)
def remove_relation(request, master_name, master_id, slave_name):
    """remove relations"""
    return Response({'data': vars(relation_utils.remove_relation(request,
                                                                 master_name,
                                                                 master_id,
                                                                 slave_name))})


@api_view(['GET'])
@login_utils.login_check_decorator(Login.REGISTRATOR, Login.ADMIN)
def get_non_related(request, master_name, master_id, slave_name):
    """get non-related entries"""
    return Response({'data': relation_utils.get_non_related(request,
                                                            master_name,
                                                            master_id,
                                                            slave_name)})


@api_view(['POST'])
@login_utils.login_check_decorator(Login.REGISTRATOR, Login.ADMIN)
def registrate_biometry(request, employee_id):
    """registrate biometry to employee"""
    employee = get_object_or_404(Employee.objects.all(), pk=employee_id)
    mqtt_id = request.POST.get('mqtt')
    biometry_data = request.POST.get('biometryData')
    biometry_type = BiometryType(request.POST.get('type'))

    result = registrate_biometry_by_device(
        employee, mqtt_id, biometry_data, biometry_type)

    return Response(vars(result))
