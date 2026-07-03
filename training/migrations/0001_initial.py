# Generated manually for SOP Portal
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(
            name='Document',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200)),
                ('theme', models.CharField(max_length=120)),
                ('description', models.TextField(blank=True)),
                ('file', models.FileField(upload_to='documents/')),
                ('valid_from', models.DateField(default=django.utils.timezone.localdate)),
                ('valid_until', models.DateField()),
                ('uploaded_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={'ordering': ['theme', 'title']},
        ),
        migrations.CreateModel(
            name='Employee',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=150)),
                ('badge_id', models.CharField(max_length=50, unique=True)),
                ('department', models.CharField(max_length=100)),
                ('section', models.CharField(max_length=100)),
                ('division', models.CharField(max_length=100)),
                ('user', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='SocializationEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200)),
                ('division', models.CharField(max_length=100)),
                ('place', models.CharField(max_length=150)),
                ('schedule', models.DateTimeField()),
                ('presenter', models.CharField(max_length=150)),
                ('notes', models.TextField(blank=True)),
                ('materials', models.ManyToManyField(related_name='events', to='training.document')),
            ],
            options={'ordering': ['-schedule']},
        ),
        migrations.CreateModel(
            name='ReadingRecord',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('mode', models.CharField(choices=[('MANDIRI', 'Sosialisasi Mandiri'), ('EVENT', 'Ikut Event')], max_length=20)),
                ('completed_at', models.DateTimeField(auto_now_add=True)),
                ('document', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='training.document')),
                ('employee', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='training.employee')),
                ('event', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='training.socializationevent')),
            ],
            options={'ordering': ['-completed_at'], 'unique_together': {('employee', 'document', 'mode', 'event')}},
        ),
    ]
