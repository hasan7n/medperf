# Generated by Django 3.2.20 on 2023-11-24 04:21

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('benchmark', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='benchmark',
            name='demo_dataset_tarball_url',
            field=models.CharField(max_length=256),
        ),
    ]