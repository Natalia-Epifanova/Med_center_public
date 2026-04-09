from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("patients", "0012_patient_trusted_person"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="patient",
            name="blacklist_comment",
            field=models.TextField(
                blank=True,
                default="",
                verbose_name="Причина черного списка",
            ),
        ),
        migrations.AddField(
            model_name="patient",
            name="blacklist_created_at",
            field=models.DateTimeField(
                blank=True,
                null=True,
                verbose_name="Дата добавления в черный список",
            ),
        ),
        migrations.AddField(
            model_name="patient",
            name="blacklist_created_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.SET_NULL,
                related_name="blacklisted_patients",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Кто добавил в черный список",
            ),
        ),
        migrations.AddField(
            model_name="patient",
            name="is_blacklisted",
            field=models.BooleanField(
                default=False,
                verbose_name="В черном списке",
            ),
        ),
    ]
