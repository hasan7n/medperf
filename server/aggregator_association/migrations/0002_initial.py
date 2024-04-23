# Generated by Django 4.2.11 on 2024-04-23 01:12

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("training", "0001_initial"),
        ("aggregator_association", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="experimentaggregator",
            name="training_exp",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                to="training.trainingexperiment",
            ),
        ),
    ]
