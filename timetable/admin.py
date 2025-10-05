from django.contrib import admin

from timetable.models import Cabinet, Patient, Doctor, MedicalService


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
        "surname",  # Ставим фамилию первой для удобства
        "first_name",
        "last_name",
        "specialization",
        "view_provided_services",  # Заменяем стандартное отображение
    )
    search_fields = (
        "first_name",
        "last_name",
        "surname",
        "specialization",
    )
    # Добавляем удобный виджет для выбора услуг
    filter_horizontal = ("provided_services",)
    # Включаем поиск услуг при редактировании врача:cite[6]
    autocomplete_fields = ("provided_services",)

    def view_provided_services(self, obj):
        """Кастомный метод для отображения услуг в списке врачей."""
        return ", ".join([service.name for service in obj.provided_services.all()[:3]])

    view_provided_services.short_description = "Оказываемые услуги"


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
        # Получаем список ключей выбранных специализаций
        selected_specializations = obj.allowed_specializations

        # Если список пуст, возвращаем прочерк
        if not selected_specializations:
            return "-"

        # Сопоставляем ключи с человекочитаемыми названиями
        specializations_dict = dict(Doctor.DoctorSpecialization.choices)
        readable_specializations = [
            specializations_dict.get(spec, spec) for spec in selected_specializations
        ]

        # ВАЖНО: Преобразуем каждый элемент в строку перед объединением
        return ", ".join(str(spec) for spec in readable_specializations)

    get_allowed_specializations.short_description = "Разрешенные специализации"
