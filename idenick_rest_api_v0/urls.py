"""URLs"""
from django.conf.urls import url
from django.urls import path
from rest_framework.routers import DefaultRouter

from idenick_rest_api_v0.views import (
    ControllerViewSet, DepartmentViewSet, DeviceViewSet, EmployeeSets,
    OrganizationViewSet, RegistratorViewSet, UserViewSet, add_employees,
    get_current_user, get_report, get_report_file, remove_employees)

OTHER_EMPLOYEES = 'others'

ROUTER = DefaultRouter()
ROUTER.register(r'organizations', OrganizationViewSet, basename='Organization')
ROUTER.register(r'departments', DepartmentViewSet, basename='Department')
ROUTER.register(r'departments/(?P<department_id>[0-9]+)/employees',
                EmployeeSets.ByDepartmentViewSet, basename='Employee')
ROUTER.register(r'departments/(?P<department_id>[0-9]+)/' + OTHER_EMPLOYEES,
                EmployeeSets.ByDepartmentViewSet, basename='Employee')
ROUTER.register(r'employees', EmployeeSets.SimpleViewSet, basename='Employee')
ROUTER.register(r'registrators', RegistratorViewSet, basename='Login')
ROUTER.register(r'controllers', ControllerViewSet, basename='Login')
ROUTER.register(r'users', UserViewSet, basename='Login')
ROUTER.register(r'devices', DeviceViewSet, basename='Device')

urlpatterns = ROUTER.urls

urlpatterns += [
    path('currentUser/', get_current_user),
    url('report/', get_report),
    url('reportFile/', get_report_file),
    url('departments/(?P<department_id>[0-9]+)/addEmployees/', add_employees),
    url('departments/(?P<department_id>[0-9]+)/removeEmployees/',
        remove_employees),
]
