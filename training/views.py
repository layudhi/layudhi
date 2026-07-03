import csv
import io
import zipfile
from xml.sax.saxutils import escape


from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import DocumentForm, EventForm, UploadUsersForm
from .models import Document, Employee, ReadingRecord, SocializationEvent, SocializationExclusion


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
    employees_count = Employee.objects.count()
    socialized_users_count = ReadingRecord.objects.values('employee_id').distinct().count()
    chart_max = max(Document.objects.count(), active_documents.count(), employees_count, socialized_users_count, 1)
    return render(request, 'sop_portal/dashboard.html', {
        'documents_count': Document.objects.count(),
        'active_documents_count': active_documents.count(),
        'employees_count': employees_count,
        'socialized_users_count': socialized_users_count,
        'documents_percent': int(Document.objects.count() / chart_max * 100),
        'active_documents_percent': int(active_documents.count() / chart_max * 100),
        'employees_percent': int(employees_count / chart_max * 100),
        'socialized_users_percent': int(socialized_users_count / chart_max * 100),
        'events': SocializationEvent.objects.select_related().all()[:5],
        'recent_records': ReadingRecord.objects.select_related('employee', 'document', 'event')[:8],
    })





def column_name(index):
    name = ''
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name


def xlsx_response(filename, rows):
    output = io.BytesIO()
    sheet_rows = []
    for row_index, row in enumerate(rows, start=1):
        cells = []
        for column_index, value in enumerate(row, start=1):
            cell_ref = f'{column_name(column_index)}{row_index}'
            text = escape('' if value is None else str(value))
            cells.append(f'<c r="{cell_ref}" t="inlineStr"><is><t>{text}</t></is></c>')
        sheet_rows.append(f'<row r="{row_index}">{''.join(cells)}</row>')
    worksheet = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>' + ''.join(sheet_rows) + '</sheetData></worksheet>'
    workbook = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Report" sheetId="1" r:id="rId1"/></sheets></workbook>'
    rels = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>'
    workbook_rels = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>'
    content_types = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>'
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as workbook_zip:
        workbook_zip.writestr('[Content_Types].xml', content_types)
        workbook_zip.writestr('_rels/.rels', rels)
        workbook_zip.writestr('xl/workbook.xml', workbook)
        workbook_zip.writestr('xl/_rels/workbook.xml.rels', workbook_rels)
        workbook_zip.writestr('xl/worksheets/sheet1.xml', worksheet)
    response = HttpResponse(output.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@login_required
@staff_required
def report_index(request):
    documents = Document.objects.all()
    events = SocializationEvent.objects.prefetch_related('materials')
    return render(request, 'sop_portal/report_index.html', {'documents': documents, 'events': events})


def missing_for_document(document):
    completed_ids = ReadingRecord.objects.filter(document=document).values_list('employee_id', flat=True)
    excluded_ids = SocializationExclusion.objects.filter(document=document, event__isnull=True).values_list('employee_id', flat=True)
    missing = Employee.objects.exclude(id__in=completed_ids).exclude(id__in=excluded_ids).order_by('division', 'department', 'section', 'name')
    excluded = SocializationExclusion.objects.filter(document=document, event__isnull=True).select_related('employee')
    return missing, excluded


def missing_for_event(event):
    attended_ids = ReadingRecord.objects.filter(event=event, mode='EVENT').values_list('employee_id', flat=True)
    excluded_ids = SocializationExclusion.objects.filter(event=event, document__isnull=True).values_list('employee_id', flat=True)
    missing = Employee.objects.exclude(id__in=attended_ids).exclude(id__in=excluded_ids).order_by('division', 'department', 'section', 'name')
    excluded = SocializationExclusion.objects.filter(event=event, document__isnull=True).select_related('employee')
    return missing, excluded


@login_required
@staff_required
def document_missing_report(request, pk):
    document = get_object_or_404(Document, pk=pk)
    missing, excluded = missing_for_document(document)
    return render(request, 'sop_portal/missing_report.html', {
        'target_type': 'document',
        'target': document,
        'missing_employees': missing,
        'excluded_records': excluded,
    })


@login_required
@staff_required
def event_missing_report(request, pk):
    event = get_object_or_404(SocializationEvent, pk=pk)
    missing, excluded = missing_for_event(event)
    return render(request, 'sop_portal/missing_report.html', {
        'target_type': 'event',
        'target': event,
        'missing_employees': missing,
        'excluded_records': excluded,
    })


@login_required
@staff_required
@require_POST
def ignore_missing(request, target_type, pk, employee_id):
    employee = get_object_or_404(Employee, pk=employee_id)
    reason = request.POST.get('reason', '').strip() or 'Tidak relevan dengan SOP/materi sosialisasi ini.'
    if target_type == 'document':
        target = get_object_or_404(Document, pk=pk)
        SocializationExclusion.objects.get_or_create(employee=employee, document=target, event=None, defaults={'reason': reason})
        redirect_name = 'training:document_missing_report'
    else:
        target = get_object_or_404(SocializationEvent, pk=pk)
        SocializationExclusion.objects.get_or_create(employee=employee, event=target, document=None, defaults={'reason': reason})
        redirect_name = 'training:event_missing_report'
    messages.success(request, f'{employee.name} ditandai N/A untuk {target}.')
    return redirect(redirect_name, pk=pk)


@login_required
@staff_required
def download_socialization_report(request, target_type, pk, status):
    rows = [[
        'Status', 'Metode', 'Nama', 'ID Badge', 'Departemen', 'Section', 'Divisi',
        'SOP/Materi', 'Tema', 'Event', 'Tempat Event', 'Waktu Event', 'Pembawa Materi',
        'Waktu Sosialisasi', 'Keterangan'
    ]]
    if target_type == 'document':
        target = get_object_or_404(Document, pk=pk)
        filename_target = f'document-{target.pk}'
        if status == 'completed':
            records = ReadingRecord.objects.filter(document=target).select_related('employee', 'event', 'document').order_by('employee__name', '-completed_at')
            for record in records:
                rows.append([
                    'Sudah', record.get_mode_display(), record.employee.name, record.employee.badge_id,
                    record.employee.department, record.employee.section, record.employee.division,
                    target.title, target.theme, record.event.title if record.event else '',
                    record.event.place if record.event else '', record.event.schedule if record.event else '',
                    record.event.presenter if record.event else '', record.completed_at, ''
                ])
        elif status == 'na':
            exclusions = SocializationExclusion.objects.filter(document=target, event__isnull=True).select_related('employee')
            for exclusion in exclusions:
                rows.append(['N/A', 'N/A', exclusion.employee.name, exclusion.employee.badge_id, exclusion.employee.department, exclusion.employee.section, exclusion.employee.division, target.title, target.theme, '', '', '', '', exclusion.created_at, exclusion.reason])
        else:
            missing, _ = missing_for_document(target)
            for employee in missing:
                rows.append(['Belum', '', employee.name, employee.badge_id, employee.department, employee.section, employee.division, target.title, target.theme, '', '', '', '', '', 'Belum sosialisasi'])
    else:
        target = get_object_or_404(SocializationEvent, pk=pk)
        filename_target = f'event-{target.pk}'
        materials = ', '.join(target.materials.values_list('title', flat=True))
        if status == 'completed':
            records = ReadingRecord.objects.filter(event=target, mode='EVENT').select_related('employee').order_by('employee__name', '-completed_at')
            seen = set()
            for record in records:
                if record.employee_id in seen:
                    continue
                seen.add(record.employee_id)
                rows.append(['Sudah', record.get_mode_display(), record.employee.name, record.employee.badge_id, record.employee.department, record.employee.section, record.employee.division, materials, '', target.title, target.place, target.schedule, target.presenter, record.completed_at, 'Hadir event'])
        elif status == 'na':
            exclusions = SocializationExclusion.objects.filter(event=target, document__isnull=True).select_related('employee')
            for exclusion in exclusions:
                rows.append(['N/A', 'N/A', exclusion.employee.name, exclusion.employee.badge_id, exclusion.employee.department, exclusion.employee.section, exclusion.employee.division, materials, '', target.title, target.place, target.schedule, target.presenter, exclusion.created_at, exclusion.reason])
        else:
            missing, _ = missing_for_event(target)
            for employee in missing:
                rows.append(['Belum', '', employee.name, employee.badge_id, employee.department, employee.section, employee.division, materials, '', target.title, target.place, target.schedule, target.presenter, '', 'Belum hadir event'])
    return xlsx_response(f'{filename_target}-{status}.xlsx', rows)


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
    themes = documents.order_by('theme').values_list('theme', flat=True).distinct()
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
def event_detail(request, pk):
    event = get_object_or_404(SocializationEvent.objects.prefetch_related('materials'), pk=pk)
    employee, _ = Employee.objects.get_or_create(
        user=request.user,
        defaults={'name': request.user.get_full_name() or request.user.username, 'badge_id': f'USR-{request.user.id}', 'department': '-', 'section': '-', 'division': '-'},
    )
    attendance_records = ReadingRecord.objects.filter(event=event, mode='EVENT').select_related('employee').order_by('employee__name', '-completed_at')
    attended_material_ids = set(attendance_records.filter(employee=employee).values_list('document_id', flat=True))
    attendees_by_employee = {}
    for record in attendance_records:
        attendees_by_employee.setdefault(record.employee_id, record)
    return render(request, 'sop_portal/event_detail.html', {
        'event': event,
        'employee': employee,
        'attendance': attendees_by_employee.values(),
        'attended_material_ids': attended_material_ids,
    })


@login_required
@require_POST
def attend_event(request, pk):
    event = get_object_or_404(SocializationEvent.objects.prefetch_related('materials'), pk=pk)
    if not event.is_active:
        messages.error(request, 'Event sudah lewat tanggalnya sehingga daftar hadir ditutup.')
        return redirect('training:event_detail', pk=event.pk)
    employee, _ = Employee.objects.get_or_create(
        user=request.user,
        defaults={'name': request.user.get_full_name() or request.user.username, 'badge_id': f'USR-{request.user.id}', 'department': '-', 'section': '-', 'division': '-'},
    )
    created = 0
    for material in event.materials.all():
        _, was_created = ReadingRecord.objects.get_or_create(employee=employee, document=material, mode='EVENT', event=event)
        created += int(was_created)
    if created:
        messages.success(request, 'Daftar hadir event berhasil disimpan.')
    else:
        messages.info(request, 'Anda sudah terdaftar hadir pada event ini.')
    return redirect('training:event_detail', pk=event.pk)


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
