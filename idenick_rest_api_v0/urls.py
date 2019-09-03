"""URLs"""
from django.conf.urls import url
from django.urls import path
from rest_framework.routers import DefaultRouter

from idenick_rest_api_v0.views import (ControllerViewSet, DepartmentViewSet,
                                       DeviceGroupViewSet, DeviceViewSet,
                                       EmployeeViewSet, OrganizationViewSet,
                                       RegistratorViewSet, UserViewSet,
                                       add_devices2device_group, add_employees,
                                       add_organizations2device_group, get_counts,
                                       get_current_user, get_other_devices4device_group,
                                       get_other_employees,
                                       get_other_organizations4device_group, get_report,
                                       get_report_file, remove_devices4device_group,
                                       remove_employees, remove_organizations2device_group)

ROUTER = DefaultRouter()
ROUTER.register(r'organizations', OrganizationViewSet, basename='Organization')
ROUTER.register(r'departments', DepartmentViewSet, basename='Department')
ROUTER.register(r'employees', EmployeeViewSet, basename='Employee')
ROUTER.register(r'registrators', RegistratorViewSet, basename='Login')
ROUTER.register(r'controllers', ControllerViewSet, basename='Login')
ROUTER.register(r'users', UserViewSet, basename='Login')
ROUTER.register(r'devices', DeviceViewSet, basename='Device')
ROUTER.register(r'deviceGroups', DeviceGroupViewSet, basename='DeviceGroup')

urlpatterns = ROUTER.urls

urlpatterns += [
    path('currentUser/', get_current_user),
    url('report/', get_report),
    url('counts/', get_counts),
    url('reportFile/', get_report_file),
    url('departments/(?P<department_id>[0-9]+)/addEmployees/', add_employees),
    url('departments/(?P<department_id>[0-9]+)/otherEmployees/',
        get_other_employees),
    url('departments/(?P<department_id>[0-9]+)/removeEmployees/',
        remove_employees),

    url('deviceGroups/(?P<device_group_id>[0-9]+)/addOrganizations/',
        add_organizations2device_group),
    url('deviceGroups/(?P<device_group_id>[0-9]+)/otherOrganizations/',
        get_other_organizations4device_group),
    url('deviceGroups/(?P<device_group_id>[0-9]+)/removeOrganizations/',
        remove_organizations2device_group),

    url('deviceGroups/(?P<device_group_id>[0-9]+)/addDevices/',
        add_devices2device_group),
    url('deviceGroups/(?P<device_group_id>[0-9]+)/otherDevices/',
        get_other_devices4device_group),
    url('deviceGroups/(?P<device_group_id>[0-9]+)/removeDevices/',
        remove_devices4device_group,),
]
