from django.contrib import admin

from timetable.models import (
    Cabinet,
    Doctor,
    MedicalService,
    MedicalServiceCategory,
    BloodTestCategory,
    BloodTest,
)


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

    # Добавляем фильтр для формы
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)

        # Если объект существует и у него есть выбранные категории
        if obj and obj.provided_services:
            # Ограничиваем queryset для excluded_services только услугами из выбранных категорий
            form.base_fields["excluded_services"].queryset = (
                MedicalService.objects.filter(
                    category__in=obj.provided_services, is_active=True
                )
            )
        elif obj:
            # Если категории не выбраны, показываем пустой queryset
            form.base_fields["excluded_services"].queryset = (
                MedicalService.objects.none()
            )

        return form

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
