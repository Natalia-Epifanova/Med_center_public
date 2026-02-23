from django.db import migrations
import datetime

BASE_DATE = datetime.date(2026, 1, 1)


def seed_prices(apps, schema_editor):
    MedicalService = apps.get_model("timetable", "MedicalService")
    MedicalServicePrice = apps.get_model("timetable", "MedicalServicePrice")

    for service in MedicalService.objects.all():
        MedicalServicePrice.objects.get_or_create(
            service=service,
            valid_from=BASE_DATE,
            defaults={"price": service.price},
        )


class Migration(migrations.Migration):
    dependencies = [
        ("timetable", "0005_medicalserviceprice"),
    ]

    operations = [
        migrations.RunPython(seed_prices, migrations.RunPython.noop),
    ]
