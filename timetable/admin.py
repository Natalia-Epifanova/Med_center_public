from django.contrib import admin
from django.forms import ModelForm, MultipleChoiceField

from timetable.models import (
    Cabinet,
    Doctor,
    MedicalService,
    MedicalServiceCategory,
    Patient,
    TimeSlot,
)


@admin.register(Cabinet)
class CabinetAdmin(admin.ModelAdmin):
    list_display = ("id", "number", "name_of_cabinet")
    search_fields = ("number",)


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = (
        "card_number",
        "first_name",
        "last_name",
        "surname",
        "phone_number",
        "date_of_birth",
        "registration_address",
        "residential_address",
    )
    search_fields = (
        "card_number",
        "first_name",
        "last_name",
        "surname",
        "phone_number",
        "date_of_birth",
    )


@admin.register(Doctor)
class DoctorAdmin(admin.ModelAdmin):
    list_display = (
        "surname",
        "first_name",
        "last_name",
        "specialization",
        "services_count",
        "categories_display",
    )
    search_fields = ("first_name", "last_name", "surname")
    list_filter = ("specialization",)

    def services_count(self, obj):
        return obj.get_available_services().count()

    services_count.short_description = "Доступных услуг"

    def categories_display(self, obj):
        """Отображаем категории услуг врача"""
        categories_dict = dict(MedicalServiceCategory.choices)
        categories = [
            str(categories_dict.get(cat, cat)) for cat in obj.provided_services
        ]
        return ", ".join(categories) if categories else "-"

    categories_display.short_description = "Категории услуг"


@admin.register(MedicalService)
class MedicalServiceAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "category", "price", "is_active")
    list_filter = ("category", "is_active")
    search_fields = ("name", "code")
