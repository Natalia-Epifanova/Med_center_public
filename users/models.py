from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    # username теперь будет использоваться как логин
    # email делаем необязательным
    email = models.EmailField(unique=False, verbose_name="Email", blank=True, null=True)

    # Убираем USERNAME_FIELD = "email"
    # Django по умолчанию использует username

    # Добавляем поля для информации
    phone = models.CharField(
        max_length=20, verbose_name="Телефон", blank=True, null=True
    )

    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"

    def __str__(self):
        return self.username if self.username else f"User #{self.id}"

    # Методы для проверки ролей
    @property
    def is_admin(self):
        return self.groups.filter(name="Admin").exists() or self.is_superuser

    @property
    def is_medical_admin(self):
        return self.groups.filter(name="Medical Center Administrator").exists()

    @property
    def is_doctor(self):
        return self.groups.filter(name="Doctors").exists()

    def get_role_display(self):
        """Возвращает отображаемое название роли"""
        if self.is_superuser:
            return "Суперпользователь"
        elif self.is_admin:
            return "Администратор"
        elif self.is_medical_admin:
            return "Администратор МЦ"
        elif self.is_doctor:
            return "Доктор"
        return "Пользователь"
