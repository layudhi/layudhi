from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


class Employee(models.Model):
    user = models.OneToOneField(User, on_delete=models.SET_NULL, blank=True, null=True)
    name = models.CharField(max_length=150)
    badge_id = models.CharField(max_length=50, unique=True)
    department = models.CharField(max_length=100)
    section = models.CharField(max_length=100)
    division = models.CharField(max_length=100)

    def __str__(self):
        return f'{self.name} ({self.badge_id})'


class Document(models.Model):
    title = models.CharField(max_length=200)
    theme = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    file = models.FileField(upload_to='documents/')
    valid_from = models.DateField(default=timezone.localdate)
    valid_until = models.DateField()
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['theme', 'title']

    @property
    def is_active(self):
        today = timezone.localdate()
        return self.valid_from <= today <= self.valid_until

    def __str__(self):
        return self.title


class SocializationEvent(models.Model):
    title = models.CharField(max_length=200)
    division = models.CharField(max_length=100)
    place = models.CharField(max_length=150)
    schedule = models.DateTimeField()
    presenter = models.CharField(max_length=150)
    materials = models.ManyToManyField(Document, related_name='events')
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-schedule']

    def __str__(self):
        return self.title


class ReadingRecord(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    document = models.ForeignKey(Document, on_delete=models.CASCADE)
    mode = models.CharField(max_length=20, choices=[('MANDIRI', 'Sosialisasi Mandiri'), ('EVENT', 'Ikut Event')])
    event = models.ForeignKey(SocializationEvent, on_delete=models.SET_NULL, blank=True, null=True)
    completed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('employee', 'document', 'mode', 'event')]
        ordering = ['-completed_at']
