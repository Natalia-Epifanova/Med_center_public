from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("timetable", "0007_bloodtestprice"),
    ]

    operations = [
        migrations.AlterField(
            model_name="timeslot",
            name="slot_type",
            field=models.CharField(
                choices=[
                    ("working", "Рабочий слот"),
                    ("break", "Перерыв"),
                    ("emergency", "Экстренный слот"),
                ],
                default="working",
                max_length=10,
                verbose_name="Тип слота",
            ),
        ),
    ]
