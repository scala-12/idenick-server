"""URLs"""
from django.conf.urls import url
from django.urls import path
from rest_framework.routers import DefaultRouter

from idenick_rest_api_v0.views import (ControllerViewSet, DepartmentViewSet,
                                       CheckpointViewSet, DeviceViewSet,
                                       EmployeeViewSet, OrganizationViewSet,
                                       RegistratorViewSet, UserViewSet,
                                       add_relation, get_counts,
                                       get_current_user, get_non_related,
                                       get_report, get_employees_requests, get_report_file,
                                       registrate_biometry, remove_relation)

ROUTER = DefaultRouter()
ROUTER.register(r'organizations', OrganizationViewSet, basename='Organization')
ROUTER.register(r'departments', DepartmentViewSet, basename='Department')
ROUTER.register(r'employees', EmployeeViewSet, basename='Employee')
ROUTER.register(r'registrators', RegistratorViewSet, basename='Login')
ROUTER.register(r'controllers', ControllerViewSet, basename='Login')
ROUTER.register(r'users', UserViewSet, basename='Login')
ROUTER.register(r'devices', DeviceViewSet, basename='Device')
ROUTER.register(r'checkpoints', CheckpointViewSet, basename='Checkpoint')

urlpatterns = ROUTER.urls

urlpatterns += [
    path('currentUser/', get_current_user),
    url('report/', get_report),
    url('employeesRequests/', get_employees_requests),
    url('reportFile/', get_report_file),
    url('counts/', get_counts),

    url(
        '(?P<master_name>\\w+)/(?P<master_id>[0-9]+)/add(?P<slave_name>\\w+)s/',
        add_relation),
    url(
        '(?P<master_name>\\w+)/(?P<master_id>[0-9]+)/remove(?P<slave_name>\\w+)s/',
        remove_relation),
    url(
        '(?P<master_name>\\w+)/(?P<master_id>[0-9]+)/other(?P<slave_name>\\w+)s/',
        get_non_related),
    url(
        'employees/(?P<employee_id>[0-9]+)/registrateBiometry/', registrate_biometry),
]
