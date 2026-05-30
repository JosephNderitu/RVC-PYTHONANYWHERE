from django.db import migrations
import uuid


def generate_tokens(apps, schema_editor):
    Job = apps.get_model('Truck', 'Job')

    for job in Job.objects.all():
        job.confirmation_token = uuid.uuid4()
        job.save(update_fields=['confirmation_token'])


class Migration(migrations.Migration):

    dependencies = [
        ('Truck', '0022_job_confirmation_token_job_confirmed_at_and_more'),
    ]

    operations = [
        migrations.RunPython(generate_tokens),
    ]