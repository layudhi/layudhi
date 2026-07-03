from datetime import timedelta

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Document, Employee


class SopPortalTests(TestCase):

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

    def test_upload_users_imports_expected_columns(self):
        staff = User.objects.create_user(username='admin', password='pass', is_staff=True)
        self.client.force_login(staff)
        csv_file = SimpleUploadedFile(
            'users.csv',
            'nama,id badge,departemen,section,divisi\nBudi,B123,Produksi,A,Factory\n'.encode(),
            content_type='text/csv',
        )

        response = self.client.post(reverse('training:upload_users'), {'csv_file': csv_file})

        self.assertRedirects(response, reverse('training:dashboard'))
        employee = Employee.objects.get(badge_id='B123')
        self.assertEqual(employee.name, 'Budi')
        self.assertEqual(employee.division, 'Factory')
