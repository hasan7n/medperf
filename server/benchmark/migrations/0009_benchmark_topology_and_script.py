import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """Introduces the benchmark topology.

    Every benchmark that exists today is one where associated models bring
    their own inference container and the benchmark only evaluates, so they are
    all backfilled as `byo_inference_script`. `preserve_default=False` drops the
    default afterwards: new benchmarks must state their topology explicitly.
    """

    dependencies = [
        ("mlcube", "0001_initial"),
        ("benchmark", "0008_benchmark_committee_members"),
    ]

    operations = [
        migrations.AddField(
            model_name="benchmark",
            name="topology",
            field=models.CharField(
                choices=[
                    ("byo_inference_script", "byo_inference_script"),
                    ("end_to_end_script", "end_to_end_script"),
                    ("inference_script", "inference_script"),
                ],
                default="byo_inference_script",
                max_length=100,
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="benchmark",
            name="benchmark_script",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="benchmark_script",
                to="mlcube.mlcube",
            ),
        ),
        migrations.AlterField(
            model_name="benchmark",
            name="data_evaluator_mlcube",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="data_evaluator_mlcube",
                to="mlcube.mlcube",
            ),
        ),
    ]
