from django.contrib import admin
from .models import Document, Employee, ReadingRecord, SocializationEvent, SocializationExclusion


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


@admin.register(SocializationExclusion)
class SocializationExclusionAdmin(admin.ModelAdmin):
    list_display = ('employee', 'document', 'event', 'reason', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('employee__name', 'employee__badge_id', 'document__title', 'event__title', 'reason')
