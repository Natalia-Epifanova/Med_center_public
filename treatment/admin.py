from django.contrib import admin

from treatment.models import MKB10Diagnosis


@admin.register(MKB10Diagnosis)
class MKB10DiagnosisAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "name",
        "chapter",
        "block",
        "is_active",
    )
    search_fields = (
        "code",
        "name",
        "chapter",
        "block",
    )
