from rest_framework.routers import DefaultRouter

from idenick_rest_api_v0.views import OrganizationViewSet, DepartmentViewSet, EmployeeViewSet, \
    RegisterViewSets, ControllerViewSets


router = DefaultRouter()
router.register(r'organizations', OrganizationViewSet, basename='Organization')
router.register(r'departments', DepartmentViewSet, basename='Department')
router.register(r'employees', EmployeeViewSet, basename='Employee')
router.register(r'organizations/(?P<organization_id>[0-9]+)/registrators', RegisterViewSets.OrganizationViewSet, basename='Login')
router.register(r'organizations/(?P<organization_id>[0-9]+)/controllers', ControllerViewSets.OrganizationViewSet, basename='Login')
router.register(r'registrators', RegisterViewSets.SimpleViewSet, basename='Login')
router.register(r'controllers', ControllerViewSets.SimpleViewSet, basename='Login')

urlpatterns = router.urls
