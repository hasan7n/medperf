# Generated by Django 3.2.20 on 2023-11-16 23:12

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('mlcube', '0001_initial'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='mlcube',
            unique_together={('image_tarball_hash', 'image_hash', 'additional_files_tarball_hash', 'mlcube_hash', 'parameters_hash')},
        ),
    ]
