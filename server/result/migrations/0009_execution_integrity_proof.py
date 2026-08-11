from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("result", "0008_rename_the_model_modelresult_model"),
    ]

    operations = [
        migrations.AddField(
            model_name="modelresult",
            name="integrity_proof",
            field=models.JSONField(blank=True, default=dict, null=True),
        ),
    ]
