# Generated by Django 3.2.5 on 2022-01-08 18:48

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('asrot_server', '0001_initial'),
    ]

    operations = [
        migrations.RenameField(
            model_name='transcriptioncorrection',
            old_name='transcription_correct',
            new_name='transcription_correction',
        ),
        migrations.AlterField(
            model_name='transcriptioncorrection',
            name='last_commit',
            field=models.DateTimeField(auto_now=True, verbose_name='last upload'),
        ),
    ]
