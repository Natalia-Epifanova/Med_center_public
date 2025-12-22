from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    """Кастомный администратор для пользователей"""

    fieldsets = (
        (None, {"fields": ("username", "password")}),
        (_("Personal info"), {"fields": ("first_name", "last_name", "email", "phone")}),
        (
            _("Permissions"),
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                ),
            },
        ),
        (_("Important dates"), {"fields": ("last_login", "date_joined")}),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("username", "email", "phone", "password1", "password2"),
            },
        ),
    )

    list_display = (
        "username",
        "email",
        "phone",
        "first_name",
        "last_name",
        "is_staff",
        "is_active",
        "role_display",
    )
    list_filter = ("is_staff", "is_superuser", "is_active", "groups")
    search_fields = ("username", "first_name", "last_name", "email", "phone")
    ordering = ("username",)

    def save_model(self, request, obj, form, change):
        """Правильно сохраняем пароль при создании/изменении"""
        if "password" in form.changed_data:
            obj.set_password(form.cleaned_data["password"])
            messages.success(request, "Пароль успешно обновлен")
        super().save_model(request, obj, form, change)

    def role_display(self, obj):
        """Отображаем роль пользователя в списке"""
        return obj.get_role_display()

    role_display.short_description = "Роль"
