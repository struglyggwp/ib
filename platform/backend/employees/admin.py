from django.contrib import admin
from .models import Department, Employee, Position


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name",)


@admin.register(Position)
class PositionAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name",)


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ("last_name", "first_name", "email", "department", "position", "is_active")
    list_filter = ("is_active", "department", "position")
    search_fields = ("first_name", "last_name", "email")
    list_select_related = ("department", "position")
