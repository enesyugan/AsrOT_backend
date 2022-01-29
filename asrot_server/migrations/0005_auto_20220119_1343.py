# Generated by Django 3.1.2 on 2022-01-19 13:43

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('asrot_server', '0004_auto_20220111_0830'),
    ]

    operations = [
        migrations.AddField(
            model_name='transcriptiontask',
            name='encoding',
            field=models.CharField(default='latin-1', max_length=500),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='transcriptioncorrection',
            name='id',
            field=models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID'),
        ),
        migrations.AlterField(
            model_name='transcriptiontask',
            name='id',
            field=models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID'),
        ),
    ]