from django.contrib import admin
from .models import Document, Employee, ReadingRecord, SocializationEvent


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ('name', 'badge_id', 'department', 'section', 'division')
    search_fields = ('name', 'badge_id', 'department', 'section', 'division')


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ('title', 'theme', 'valid_from', 'valid_until', 'is_active')
    list_filter = ('theme', 'valid_until')
    search_fields = ('title', 'theme')


@admin.register(SocializationEvent)
class SocializationEventAdmin(admin.ModelAdmin):
    list_display = ('title', 'division', 'place', 'schedule', 'presenter')
    filter_horizontal = ('materials',)


@admin.register(ReadingRecord)
class ReadingRecordAdmin(admin.ModelAdmin):
    list_display = ('employee', 'document', 'mode', 'event', 'completed_at')
    list_filter = ('mode', 'completed_at')
