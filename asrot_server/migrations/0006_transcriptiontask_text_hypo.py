# Generated by Django 3.1.2 on 2022-01-20 17:22

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('asrot_server', '0005_auto_20220119_1343'),
    ]

    operations = [
        migrations.AddField(
            model_name='transcriptiontask',
            name='text_hypo',
            field=models.CharField(blank=True, max_length=1000),
        ),
    ]
