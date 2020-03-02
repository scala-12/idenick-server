from django.contrib import admin

from idenick_app.classes.model_entities.department import Department
from idenick_app.classes.model_entities.employee import Employee
from idenick_app.classes.model_entities.login import Login
from idenick_app.classes.model_entities.organization import Organization
from idenick_app.classes.model_entities.relations.employee2department import \
    Employee2Department


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'guid', 'created_at']


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'created_at']
    
    
@admin.register(Login)
class LoginAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'role', 'organization']
    
    
@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ['id', 'last_name', 'first_name', 'patronymic']
    
    
@admin.register(Employee2Department)
class Employee2DepartmentAdmin(admin.ModelAdmin):
    list_display = ['id', 'department', 'employee']
