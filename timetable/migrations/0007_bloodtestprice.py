from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("timetable", "0006_seed_medicalserviceprice"),
    ]

    operations = [
        migrations.CreateModel(
            name="BloodTestPrice",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("valid_from", models.DateField(verbose_name="Действует с")),
                (
                    "price",
                    models.DecimalField(
                        decimal_places=2,
                        max_digits=10,
                        verbose_name="Цена",
                    ),
                ),
                (
                    "blood_test",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="prices",
                        to="timetable.bloodtest",
                        verbose_name="Анализ крови",
                    ),
                ),
            ],
            options={
                "verbose_name": "Цена анализа крови",
                "verbose_name_plural": "Цены анализов крови",
                "ordering": ["-valid_from"],
            },
        ),
        migrations.AddConstraint(
            model_name="bloodtestprice",
            constraint=models.UniqueConstraint(
                fields=("blood_test", "valid_from"),
                name="uniq_blood_test_valid_from",
            ),
        ),
        migrations.AddIndex(
            model_name="bloodtestprice",
            index=models.Index(
                fields=["blood_test", "valid_from"],
                name="idx_blood_test_valid_from",
            ),
        ),
    ]
