from django.conf.urls import url
from django.urls import path
from rest_framework.routers import DefaultRouter

from idenick_rest_api_v0.views import OrganizationViewSet, DepartmentViewSet, EmployeeSets, \
    RegistratorViews, ControllerViews
from idenick_rest_api_v0.views import get_current_user, add_employees, remove_employees


other_employees = 'others'

router = DefaultRouter()
router.register(r'organizations', OrganizationViewSet, basename='Organization')
router.register(r'departments', DepartmentViewSet, basename='Department')
router.register(r'departments/(?P<department_id>[0-9]+)/employees', EmployeeSets.ByDepartmentViewSet, basename='Employee')
router.register(r'departments/(?P<department_id>[0-9]+)/' + other_employees, EmployeeSets.ByDepartmentViewSet, basename='Employee')
router.register(r'employees', EmployeeSets.SimpleViewSet, basename='Employee')
router.register(r'organizations/(?P<organization_id>[0-9]+)/registrators', RegistratorViews.ByOrganizationViewSet, basename='Login')
router.register(r'organizations/(?P<organization_id>[0-9]+)/controllers', ControllerViews.ByOrganizationViewSet, basename='Login')
router.register(r'registrators', RegistratorViews.SimpleViewSet, basename='Login')
router.register(r'controllers', ControllerViews.SimpleViewSet, basename='Login')

urlpatterns = router.urls

urlpatterns += [
    path('currentUser/', get_current_user),
    url('departments/(?P<department_id>[0-9]+)/addEmployees/', add_employees),
    url('departments/(?P<department_id>[0-9]+)/removeEmployees/', remove_employees),
]
