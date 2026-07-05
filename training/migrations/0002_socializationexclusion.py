# Generated manually for SOP Portal exclusions
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('training', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='SocializationExclusion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('reason', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('document', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='training.document')),
                ('employee', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='training.employee')),
                ('event', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='training.socializationevent')),
            ],
            options={'ordering': ['employee__name']},
        ),
        migrations.AddConstraint(
            model_name='socializationexclusion',
            constraint=models.UniqueConstraint(condition=models.Q(('event__isnull', True)), fields=('employee', 'document'), name='unique_document_exclusion'),
        ),
        migrations.AddConstraint(
            model_name='socializationexclusion',
            constraint=models.UniqueConstraint(condition=models.Q(('document__isnull', True)), fields=('employee', 'event'), name='unique_event_exclusion'),
        ),
    ]
