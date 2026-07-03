import csv
import io

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import DocumentForm, EventForm, UploadUsersForm
from .models import Document, Employee, ReadingRecord, SocializationEvent


def staff_required(view_func):
    return user_passes_test(lambda user: user.is_staff)(view_func)


def row_value(row, *keys):
    normalized = {key.strip().lower().replace('_', '').replace(' ', ''): (value or '').strip() for key, value in row.items()}
    for key in keys:
        value = normalized.get(key.strip().lower().replace('_', '').replace(' ', ''))
        if value:
            return value
    return ''


def dashboard(request):
    active_documents = Document.objects.filter(valid_from__lte=timezone.localdate(), valid_until__gte=timezone.localdate())
    return render(request, 'sop_portal/dashboard.html', {
        'documents_count': Document.objects.count(),
        'active_documents_count': active_documents.count(),
        'employees_count': Employee.objects.count(),
        'events': SocializationEvent.objects.select_related().all()[:5],
        'recent_records': ReadingRecord.objects.select_related('employee', 'document', 'event')[:8],
    })


@login_required
@staff_required
def document_upload(request):
    form = DocumentForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Dokumen berhasil diupload.')
        return redirect('training:document_list')
    return render(request, 'sop_portal/form.html', {'form': form, 'title': 'Upload Dokumen'})


def document_list(request):
    today = timezone.localdate()
    documents = Document.objects.all()
    if request.GET.get('theme'):
        documents = documents.filter(theme__icontains=request.GET['theme'])
    return render(request, 'sop_portal/document_list.html', {'documents': documents, 'today': today})


@login_required
def independent_start(request):
    documents = Document.objects.filter(valid_from__lte=timezone.localdate(), valid_until__gte=timezone.localdate())
    themes = documents.values_list('theme', flat=True).distinct()
    selected_theme = request.GET.get('theme')
    if selected_theme:
        documents = documents.filter(theme=selected_theme)
    return render(request, 'sop_portal/independent.html', {'documents': documents, 'themes': themes, 'selected_theme': selected_theme})


@login_required
def read_document(request, pk):
    document = get_object_or_404(Document, pk=pk, valid_from__lte=timezone.localdate(), valid_until__gte=timezone.localdate())
    employee, _ = Employee.objects.get_or_create(
        user=request.user,
        defaults={'name': request.user.get_full_name() or request.user.username, 'badge_id': f'USR-{request.user.id}', 'department': '-', 'section': '-', 'division': '-'},
    )
    return render(request, 'sop_portal/read_document.html', {'document': document, 'employee': employee})


@login_required
@require_POST
def complete_reading(request, pk):
    document = get_object_or_404(Document, pk=pk, valid_from__lte=timezone.localdate(), valid_until__gte=timezone.localdate())
    employee = get_object_or_404(Employee, user=request.user)
    ReadingRecord.objects.get_or_create(employee=employee, document=document, mode='MANDIRI')
    messages.success(request, 'Terima kasih. Status membaca materi sudah tercatat.')
    return redirect('training:dashboard')


@login_required
@staff_required
def event_create(request):
    form = EventForm(request.POST or None)
    form.fields['materials'].queryset = Document.objects.filter(valid_from__lte=timezone.localdate(), valid_until__gte=timezone.localdate())
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Event sosialisasi berhasil dibuat.')
        return redirect('training:event_list')
    return render(request, 'sop_portal/form.html', {'form': form, 'title': 'Buat Event Sosialisasi'})


def event_list(request):
    return render(request, 'sop_portal/event_list.html', {'events': SocializationEvent.objects.prefetch_related('materials')})


@login_required
@staff_required
def upload_users(request):
    form = UploadUsersForm(request.POST or None, request.FILES or None)
    imported = 0
    if request.method == 'POST' and form.is_valid():
        text = form.cleaned_data['csv_file'].read().decode('utf-8-sig')
        for row in csv.DictReader(io.StringIO(text)):
            name = row_value(row, 'NAME', 'nama', 'name')
            badge = row_value(row, 'IDBadge', 'id badge', 'badge_id', 'id_badge')
            section = row_value(row, 'SECTION', 'section')
            department = row_value(row, 'DEPT', 'departemen', 'department')
            division = row_value(row, 'DIVISI', 'division')
            if not badge or not name:
                continue
            user, _ = User.objects.get_or_create(username=name, defaults={'first_name': name})
            user.first_name = name
            user.set_password(badge)
            user.save(update_fields=['first_name', 'password'])
            Employee.objects.update_or_create(
                badge_id=badge,
                defaults={
                    'user': user,
                    'name': name,
                    'department': department,
                    'section': section,
                    'division': division,
                },
            )
            imported += 1
        messages.success(request, f'{imported} user berhasil diimport/diperbarui.')
        return redirect('training:dashboard')
    return render(request, 'sop_portal/upload_users.html', {'form': form})
