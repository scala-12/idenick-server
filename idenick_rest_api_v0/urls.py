"""URLs"""
from django.conf.urls import url
from django.urls import path
from rest_framework.routers import DefaultRouter

from idenick_rest_api_v0.views import (ControllerViewSet, DepartmentViewSet,
                                       DeviceGroupViewSet, DeviceViewSet,
                                       EmployeeViewSet, OrganizationViewSet,
                                       RegistratorViewSet, RelationsUtils,
                                       ReportTools, UserViewSet, get_counts,
                                       get_current_user)

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
    url('report/', ReportTools.get_report),
    url('counts/', get_counts),
    url('reportFile/', ReportTools.get_report_file),

    url(
        '(?P<master_name>\\w+)/(?P<master_id>[0-9]+)/add(?P<slave_name>\\w+)s/', RelationsUtils.add_relation),
    url(
        '(?P<master_name>\\w+)/(?P<master_id>[0-9]+)/remove(?P<slave_name>\\w+)s/', RelationsUtils.remove_relation),
    url(
        '(?P<master_name>\\w+)/(?P<master_id>[0-9]+)/other(?P<slave_name>\\w+)s/', RelationsUtils.get_non_related),
]
