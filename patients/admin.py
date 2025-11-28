from django.contrib import admin

from patients.models import Patient


# Register your models here.
@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = (
        "card_number",
        "first_name",
        "last_name",
        "surname",
        "phone_number",
        "date_of_birth",
    )
    search_fields = (
        "card_number",
        "first_name",
        "last_name",
        "surname",
        "phone_number",
        "date_of_birth",
    )
