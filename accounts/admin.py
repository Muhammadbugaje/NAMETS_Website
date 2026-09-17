from unfold.admin import ModelAdmin
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from .models import User, Department, Office, OfficeAssignment


@admin.register(User)
class UserAdmin(DjangoUserAdmin, ModelAdmin):
    fieldsets = DjangoUserAdmin.fieldsets + (
        ('NAMETS Profile', {
            'fields': (
                'middle_name', 'phone_number', 'matric_number', 'department',
                'address', 'profile_picture', 'is_alumni', 'is_super_protected',
            )
        }),
    )
    list_display = ('email', 'get_full_name', 'is_active', 'is_staff', 'is_alumni')
    search_fields = ('email', 'first_name', 'last_name', 'matric_number')


@admin.register(Department)
class DepartmentAdmin(ModelAdmin):
    list_display = ('name', 'code')
    search_fields = ('name', 'code')


@admin.register(Office)
class OfficeAdmin(ModelAdmin):
    list_display = ('name', 'linked_group', 'is_protected')
    search_fields = ('name',)
    filter_horizontal = ('permissions',)


@admin.register(OfficeAssignment)
class OfficeAssignmentAdmin(ModelAdmin):
    list_display = ('user', 'office', 'display_label', 'is_active')
    list_filter = ('office', 'is_active')
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 'office__name')