# Generated by Django 3.2.20 on 2023-09-29 01:02

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('aggregator_association', '0001_initial'),
        ('training', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='experimentaggregator',
            name='training_exp',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='training.trainingexperiment'),
        ),
    ]