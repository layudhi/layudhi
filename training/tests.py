from datetime import timedelta
import io
import zipfile

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import Document, Employee, ReadingRecord, SocializationEvent, SocializationExclusion


class SopPortalTests(TestCase):


    def test_badge_login_uses_registered_employee_name(self):
        user = User.objects.create_user(username='B123', first_name='Budi')
        Employee.objects.create(user=user, name='Budi', badge_id='B123', department='Produksi', section='A', division='')

        response = self.client.post(reverse('login'), {'badge_id': 'B123'})

        self.assertRedirects(response, reverse('training:dashboard'))
        self.assertEqual(int(self.client.session['_auth_user_id']), user.id)

    def test_badge_login_rejects_unregistered_badge(self):
        response = self.client.post(reverse('login'), {'badge_id': 'UNKNOWN'})

        self.assertContains(response, 'ID Badge belum terdaftar')
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_mandiri_without_login_redirects_to_configured_login_page(self):
        response = self.client.get(reverse('training:independent_start'))

        self.assertRedirects(response, '/login/?next=/mandiri/')

    def test_expired_document_hidden_from_independent_selection(self):
        Document.objects.create(
            title='Expired SOP', theme='Safety', file=SimpleUploadedFile('expired.txt', b'old'),
            valid_from=timezone.localdate() - timedelta(days=10), valid_until=timezone.localdate() - timedelta(days=1),
        )
        active = Document.objects.create(
            title='Active SOP', theme='Safety', file=SimpleUploadedFile('active.txt', b'new'),
            valid_from=timezone.localdate(), valid_until=timezone.localdate() + timedelta(days=10),
        )
        user = User.objects.create_user(username='B001', password='pass')
        Employee.objects.create(user=user, name='User Test', badge_id='B001', department='QA', section='A', division='Plant')
        self.client.force_login(user)

        response = self.client.get(reverse('training:independent_start'))

        self.assertContains(response, active.title)
        self.assertNotContains(response, 'Expired SOP')



    def test_document_missing_report_can_ignore_employee(self):
        staff = User.objects.create_user(username='admin', password='pass', is_staff=True)
        employee = Employee.objects.create(name='Budi', badge_id='B123', department='Produksi', section='A', division='')
        document = Document.objects.create(
            title='SOP Wajib', theme='Safety', file=SimpleUploadedFile('sop.txt', b'sop'),
            valid_from=timezone.localdate(), valid_until=timezone.localdate() + timedelta(days=10),
        )
        self.client.force_login(staff)

        report_response = self.client.get(reverse('training:document_missing_report', args=[document.pk]))
        self.assertContains(report_response, employee.name)
        self.assertNotContains(report_response, 'Kirim Email')

        ignore_response = self.client.post(
            reverse('training:ignore_missing', args=['document', document.pk, employee.pk]),
            {'reason': 'Tidak relevan'},
        )
        self.assertRedirects(ignore_response, reverse('training:document_missing_report', args=[document.pk]))
        self.assertTrue(SocializationExclusion.objects.filter(employee=employee, document=document, reason='Tidak relevan').exists())


    def test_download_document_completed_report_includes_method_and_time(self):
        staff = User.objects.create_user(username='admin', password='pass', is_staff=True)
        employee = Employee.objects.create(name='Budi', badge_id='B123', department='Produksi', section='A', division='')
        document = Document.objects.create(
            title='SOP Download', theme='Safety', file=SimpleUploadedFile('download.txt', b'download'),
            valid_from=timezone.localdate(), valid_until=timezone.localdate() + timedelta(days=10),
        )
        ReadingRecord.objects.create(employee=employee, document=document, mode='MANDIRI')
        self.client.force_login(staff)

        response = self.client.get(reverse('training:download_socialization_report', args=['document', document.pk, 'completed']))

        self.assertEqual(response['Content-Type'], 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        with zipfile.ZipFile(io.BytesIO(response.content)) as workbook:
            sheet = workbook.read('xl/worksheets/sheet1.xml').decode()
        self.assertIn('Metode', sheet)
        self.assertIn('Sosialisasi Mandiri', sheet)
        self.assertIn('Waktu Sosialisasi', sheet)
        self.assertIn('UTC+8', sheet)
        self.assertIn('SOP Download', sheet)


    def test_dashboard_shows_section_compliance(self):
        staff = User.objects.create_user(username='admin', password='pass', is_staff=True)
        employee = Employee.objects.create(name='Budi', badge_id='B123', department='Produksi', section='Line A', division='')
        pending = Employee.objects.create(name='Siti', badge_id='B124', department='Produksi', section='Line A', division='')
        document = Document.objects.create(
            title='SOP Section', theme='Safety', file=SimpleUploadedFile('section.txt', b'section'),
            valid_from=timezone.localdate(), valid_until=timezone.localdate() + timedelta(days=10),
        )
        ReadingRecord.objects.create(employee=employee, document=document, mode='MANDIRI')
        self.client.force_login(staff)

        response = self.client.get(reverse('training:dashboard'))

        self.assertContains(response, 'Tingkat Kepatuhan Berdasarkan Section')
        self.assertContains(response, 'Line A')
        self.assertContains(response, '50%')

    def test_event_missing_report_excludes_attendees_and_na_users(self):
        staff = User.objects.create_user(username='admin', password='pass', is_staff=True)
        missing = Employee.objects.create(name='Missing', badge_id='B001', department='QA', section='A', division='')
        attended = Employee.objects.create(name='Attended', badge_id='B002', department='QA', section='A', division='')
        ignored = Employee.objects.create(name='Ignored', badge_id='B003', department='QA', section='A', division='')
        document = Document.objects.create(
            title='Event SOP', theme='Safety', file=SimpleUploadedFile('event-report.txt', b'event'),
            valid_from=timezone.localdate(), valid_until=timezone.localdate() + timedelta(days=10),
        )
        event = SocializationEvent.objects.create(
            title='Event Report', division='QA', place='Room A',
            schedule=timezone.now() + timedelta(days=1), presenter='Trainer',
        )
        event.materials.add(document)
        ReadingRecord.objects.create(employee=attended, document=document, event=event, mode='EVENT')
        SocializationExclusion.objects.create(employee=ignored, event=event, reason='Tidak relevan')
        self.client.force_login(staff)

        response = self.client.get(reverse('training:event_missing_report', args=[event.pk]))

        self.assertContains(response, missing.name)
        self.assertNotContains(response, attended.name)
        self.assertContains(response, ignored.name)
        self.assertContains(response, 'User N/A / Tidak Relevan')

    def test_active_event_can_be_selected_and_records_attendance(self):
        document = Document.objects.create(
            title='Event SOP', theme='Safety', file=SimpleUploadedFile('event.txt', b'event'),
            valid_from=timezone.localdate(), valid_until=timezone.localdate() + timedelta(days=10),
        )
        event = SocializationEvent.objects.create(
            title='Event Aktif', division='Factory', place='Room A',
            schedule=timezone.now() + timedelta(days=1), presenter='Trainer',
        )
        event.materials.add(document)
        user = User.objects.create_user(username='Budi', password='B123')
        employee = Employee.objects.create(user=user, name='Budi', badge_id='B123', department='Produksi', section='A', division='')
        self.client.force_login(user)

        list_response = self.client.get(reverse('training:event_list'))
        self.assertContains(list_response, reverse('training:event_detail', args=[event.pk]))

        response = self.client.post(reverse('training:attend_event', args=[event.pk]))

        self.assertRedirects(response, reverse('training:event_detail', args=[event.pk]))
        self.assertTrue(ReadingRecord.objects.filter(employee=employee, document=document, event=event, mode='EVENT').exists())

    def test_past_event_is_disabled_and_attendance_is_rejected(self):
        document = Document.objects.create(
            title='Past SOP', theme='Safety', file=SimpleUploadedFile('past.txt', b'past'),
            valid_from=timezone.localdate(), valid_until=timezone.localdate() + timedelta(days=10),
        )
        event = SocializationEvent.objects.create(
            title='Event Lewat', division='Factory', place='Room A',
            schedule=timezone.now() - timedelta(days=1), presenter='Trainer',
        )
        event.materials.add(document)
        user = User.objects.create_user(username='Budi', password='B123')
        employee = Employee.objects.create(user=user, name='Budi', badge_id='B123', department='Produksi', section='A', division='')
        self.client.force_login(user)

        list_response = self.client.get(reverse('training:event_list'))
        self.assertNotContains(list_response, reverse('training:event_detail', args=[event.pk]))
        self.assertContains(list_response, 'Event sudah lewat')

        response = self.client.post(reverse('training:attend_event', args=[event.pk]))

        self.assertRedirects(response, reverse('training:event_detail', args=[event.pk]))
        self.assertFalse(ReadingRecord.objects.filter(employee=employee, event=event, mode='EVENT').exists())


    def test_independent_theme_dropdown_shows_unique_themes(self):
        user = User.objects.create_user(username='Budi', password='B123')
        Employee.objects.create(user=user, name='Budi', badge_id='B123', department='Produksi', section='A', division='')
        for index in range(3):
            Document.objects.create(
                title=f'SOP Investigasi {index}', theme='Sosialisasi Hasil Investigasi', file=SimpleUploadedFile(f'sop-{index}.txt', b'sop'),
                valid_from=timezone.localdate(), valid_until=timezone.localdate() + timedelta(days=10),
            )
        self.client.force_login(user)

        response = self.client.get(reverse('training:independent_start'))

        self.assertContains(response, '<option >Sosialisasi Hasil Investigasi</option>', count=1, html=True)

    def test_media_url_is_root_relative_for_document_preview(self):
        document = Document.objects.create(
            title='PDF SOP', theme='Safety', file=SimpleUploadedFile('sop.pdf', b'%PDF-1.4'),
            valid_from=timezone.localdate(), valid_until=timezone.localdate() + timedelta(days=10),
        )

        self.assertTrue(document.file.url.startswith('/media/'))

    def test_upload_users_imports_expected_columns(self):
        staff = User.objects.create_user(username='admin', password='pass', is_staff=True)
        self.client.force_login(staff)
        csv_file = SimpleUploadedFile(
            'users.csv',
            'NAME,IDBadge,SECTION,DEPT\nBudi,B123,A,Produksi\n'.encode(),
            content_type='text/csv',
        )

        response = self.client.post(reverse('training:upload_users'), {'csv_file': csv_file})

        self.assertRedirects(response, reverse('training:dashboard'))
        employee = Employee.objects.get(badge_id='B123')
        self.assertEqual(employee.name, 'Budi')
        self.assertEqual(employee.department, 'Produksi')
        self.assertEqual(employee.section, 'A')
        self.assertEqual(employee.user.username, 'B123')
