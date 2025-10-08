from django.contrib import admin

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
        "id",
        "first_name",
        "last_name",
        "surname",
        "phone_number",
        "date_of_birth",
        "registration_address",
        "residential_address",
    )
    search_fields = (
        "first_name",
        "last_name",
        "surname",
        "phone_number",
        "date_of_birth",
    )


@admin.register(Doctor)
class DoctorAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "surname",
        "first_name",
        "last_name",
        "get_specialization_display",
        "get_provided_services",
    )
    search_fields = (
        "first_name",
        "last_name",
        "surname",
    )

    def get_specialization_display(self, obj):
        """
        Возвращает строку с читаемыми названиями специализаций врача.
        """
        selected_specializations = obj.specialization
        if not selected_specializations:
            return "-"

        specializations_dict = dict(Doctor.DoctorSpecialization.choices)
        readable_specializations = [
            str(specializations_dict.get(spec, spec))
            for spec in selected_specializations
        ]

        return ", ".join(readable_specializations)

    get_specialization_display.short_description = "Специализации врача"

    def get_provided_services(self, obj):
        """
        Возвращает строку с читаемыми названиями оказываемых категорий услуг.
        """
        selected_services = obj.provided_services
        if not selected_services:
            return "-"
        services_dict = dict(MedicalServiceCategory.choices)
        readable_services = [
            services_dict.get(service, service) for service in selected_services
        ]
        return ", ".join(str(service) for service in readable_services)

    get_provided_services.short_description = "Оказываемые категории услуг"


@admin.register(MedicalService)
class MedicalServiceAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "name",
        "category",
        "price",
        "get_allowed_specializations",  # Заменяем на кастомный метод
        "is_active",
    )
    list_filter = ("category", "is_active", "allowed_specializations")
    search_fields = ("name", "code")

    def get_allowed_specializations(self, obj):
        """
        Возвращает строку с читаемыми названиями разрешенных специализаций.
        """
        selected_specializations = obj.allowed_specializations
        if not selected_specializations:
            return "-"
        specializations_dict = dict(Doctor.DoctorSpecialization.choices)
        readable_specializations = [
            specializations_dict.get(spec, spec) for spec in selected_specializations
        ]

        return ", ".join(str(spec) for spec in readable_specializations)

    get_allowed_specializations.short_description = "Разрешенные специализации"


@admin.register(TimeSlot)
class TimeSlotAdmin(admin.ModelAdmin):
    list_display = (
        "date",
        "start_time",
        "end_time",
        "cabinet",
        "doctor",
        "slot_type",
        "get_duration",
    )
    list_filter = ("date", "cabinet", "doctor", "slot_type")
    search_fields = ("doctor__surname", "cabinet__number")
    list_editable = (
        "start_time",
        "end_time",
        "slot_type",
    )  # Быстрое редактирование в списке

    # Фильтры сверху для удобной навигации
    date_hierarchy = "date"

    def get_duration(self, obj):
        """Отображает продолжительность слота в минутах."""
        if obj.start_time and obj.end_time:
            start_minutes = obj.start_time.hour * 60 + obj.start_time.minute
            end_minutes = obj.end_time.hour * 60 + obj.end_time.minute
            return f"{end_minutes - start_minutes} мин"
        return "-"

    get_duration.short_description = "Продолжительность"
