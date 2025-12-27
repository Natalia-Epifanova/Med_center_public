from django import forms
from django.contrib import admin

from timetable.models import (BloodTest, BloodTestCategory, Cabinet, Doctor,
                              MedicalService, MedicalServiceCategory)


@admin.register(Cabinet)
class CabinetAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "number",
        "name_of_cabinet",
    )
    search_fields = ("number",)


@admin.register(Doctor)
class DoctorAdmin(admin.ModelAdmin):
    list_display = (
        "surname",
        "first_name",
        "last_name",
        "specialization",
        "services_count",
        "categories_display",
        "has_comment",
    )
    search_fields = (
        "first_name",
        "last_name",
        "surname",
    )
    list_filter = ("specialization",)

    def get_form(self, request, obj=None, **kwargs):
        # Получаем форму родительского класса
        form = super().get_form(request, obj, **kwargs)

        # Получаем поле excluded_services
        if "excluded_services" in form.base_fields:
            # При создании нового врача (obj=None) показываем все активные услуги
            if obj is None:
                # При создании нового врача показываем все активные услуги
                form.base_fields["excluded_services"].queryset = (
                    MedicalService.objects.filter(is_active=True).order_by(
                        "category", "name"
                    )
                )
            # При редактировании существующего врача
            elif obj and obj.provided_services:
                # Преобразуем MultiSelectField в список
                if isinstance(obj.provided_services, str):
                    # Если это строка (например, "xray,organ_us")
                    categories_list = [
                        cat.strip() for cat in obj.provided_services.split(",")
                    ]
                elif isinstance(obj.provided_services, list):
                    # Если это уже список
                    categories_list = obj.provided_services
                else:
                    # По умолчанию пустой список
                    categories_list = []

                if categories_list:
                    # Фильтруем услуги только по выбранным категориям
                    form.base_fields["excluded_services"].queryset = (
                        MedicalService.objects.filter(
                            category__in=categories_list, is_active=True
                        ).order_by("category", "name")
                    )
                else:
                    # Если категории не выбраны, показываем все активные услуги
                    form.base_fields["excluded_services"].queryset = (
                        MedicalService.objects.filter(is_active=True).order_by(
                            "category", "name"
                        )
                    )
            else:
                # Если у врача нет выбранных категорий, показываем все активные услуги
                form.base_fields["excluded_services"].queryset = (
                    MedicalService.objects.filter(is_active=True).order_by(
                        "category", "name"
                    )
                )

        return form

    def save_model(self, request, obj, form, change):
        """Сохраняем модель и обновляем queryset для excluded_services"""
        super().save_model(request, obj, form, change)

        # После сохранения нужно обновить queryset, если были изменены категории
        if "excluded_services" in form.cleaned_data:
            # Получаем выбранные исключенные услуги
            excluded_services = form.cleaned_data.get("excluded_services", [])

            # Если у врача есть выбранные категории
            if obj.provided_services:
                # Преобразуем MultiSelectField в список
                if isinstance(obj.provided_services, str):
                    categories_list = [
                        cat.strip() for cat in obj.provided_services.split(",")
                    ]
                elif isinstance(obj.provided_services, list):
                    categories_list = obj.provided_services
                else:
                    categories_list = []

                # Фильтруем исключенные услуги, оставляя только те, что входят в выбранные категории
                valid_excluded_services = []
                for service in excluded_services:
                    if service.category in categories_list:
                        valid_excluded_services.append(service)

                # Сохраняем только валидные исключенные услуги
                obj.excluded_services.set(valid_excluded_services)

    def services_count(self, obj):
        return obj.get_available_services().count()

    services_count.short_description = "Доступных услуг"

    def categories_display(self, obj):
        """Отображаем категории услуг врача"""
        categories_dict = dict(MedicalServiceCategory.choices)
        # Преобразуем MultiSelectField в список
        if isinstance(obj.provided_services, str):
            categories = [cat.strip() for cat in obj.provided_services.split(",")]
        elif isinstance(obj.provided_services, list):
            categories = obj.provided_services
        else:
            categories = []

        categories_names = [str(categories_dict.get(cat, cat)) for cat in categories]
        return ", ".join(categories_names) if categories_names else "-"

    categories_display.short_description = "Категории услуг"

    def has_comment(self, obj):
        return bool(obj.schedule_comment)

    has_comment.short_description = "Есть комментарий"
    has_comment.boolean = True


@admin.register(MedicalService)
class MedicalServiceAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "name",
        "category",
        "price",
        "is_active",
    )
    list_filter = ("category", "is_active")
    search_fields = ("name", "code")


@admin.register(BloodTestCategory)
class BloodTestCategoryAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "order",
        "is_active",
    )
    list_filter = ("is_active",)


@admin.register(BloodTest)
class BloodTestAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "name",
        "category",
        "biomaterial",
        "execution_time",
        "price",
    )
    list_filter = ("category",)
