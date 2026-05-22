from django.db import migrations, models


def fill_blood_test_prices(apps, schema_editor):
    AppointmentBloodTest = apps.get_model("appointments", "AppointmentBloodTest")

    for selected_test in AppointmentBloodTest.objects.select_related("blood_test"):
        selected_test.price_at_appointment = selected_test.blood_test.price
        selected_test.save(update_fields=["price_at_appointment"])


class Migration(migrations.Migration):
    dependencies = [
        ("timetable", "0007_bloodtestprice"),
        ("appointments", "0006_appointment_payment_method"),
    ]

    operations = [
        migrations.AddField(
            model_name="appointmentbloodtest",
            name="price_at_appointment",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text="Цена анализа на дату приема",
                max_digits=10,
                null=True,
                verbose_name="Цена анализа на момент записи",
            ),
        ),
        migrations.RunPython(fill_blood_test_prices, migrations.RunPython.noop),
    ]
