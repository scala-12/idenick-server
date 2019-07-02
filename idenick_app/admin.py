from django.contrib import admin
from idenick_app.models import Organization, Department, Login, Employee, Employee2Department


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
    list_display = ['id', 'surname', 'first_name', 'patronymic']
    
    
@admin.register(Employee2Department)
class Employee2DepartmentAdmin(admin.ModelAdmin):
    list_display = ['id', 'department', 'employee']
