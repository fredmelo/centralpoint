from django.contrib import admin

from .models import AbsenceRecord, Employee, PunchRecord


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ['name', 'cpf', 'email', 'daily_hours', 'is_active', 'created_at']
    list_filter = ['is_active']
    search_fields = ['name', 'cpf', 'email']


@admin.register(PunchRecord)
class PunchRecordAdmin(admin.ModelAdmin):
    list_display = ['employee', 'punch_type', 'punched_at', 'is_manual', 'face_confidence']
    list_filter = ['punch_type', 'is_manual', 'punched_at']
    search_fields = ['employee__name']
    date_hierarchy = 'punched_at'


@admin.register(AbsenceRecord)
class AbsenceRecordAdmin(admin.ModelAdmin):
    list_display = ['employee', 'date', 'hours_absent', 'is_approved', 'approved_by']
    list_filter = ['approved_by']
    search_fields = ['employee__name']
    date_hierarchy = 'date'
