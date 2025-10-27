from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models


# Create your models here.
class Patient(models.Model):
    first_name = models.CharField(
        max_length=20,
        verbose_name="Имя пациента",
    )
    last_name = models.CharField(
        max_length=30,
        verbose_name="Отчество пациента",
    )
    surname = models.CharField(
        max_length=50,
        verbose_name="Фамилия пациента",
    )
    card_number = models.PositiveIntegerField(
        blank=True,
        null=True,
        verbose_name="Номер карты пациента",
    )
    phone_number = models.CharField(
        max_length=12,
        blank=True,
        null=True,
        verbose_name="Телефон пациента",
        validators=[
            RegexValidator(
                regex=r"^\+7\d{10}$",
                message="Номер телефона должен начинаться с +7 и содержать 12 символов",
            )
        ],
    )
    date_of_birth = models.DateField(
        blank=True,
        null=True,
        verbose_name="Дата рождения пациента",
    )
    gender = models.CharField(
        max_length=10,
        blank=True,
        null=True,
        verbose_name="Пол",
        choices=[("male", "Мужской"), ("female", "Женский")],
    )
    area = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="Субъект РФ",
    )
    locality = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="Населенный пункт",
    )
    city = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="Город",
    )
    district = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="Район",
    )
    address = models.TextField(
        blank=True,
        null=True,
        verbose_name="Адрес",
    )
    passport = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="Паспортные данные",
    )
    polis_oms = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name="Полис ОМС",
    )
    snils = models.CharField(
        max_length=14,
        blank=True,
        null=True,
        verbose_name="СНИЛС",
    )
    insurance_company = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        verbose_name="Страховая компания",
    )

    def clean(self):
        """Валидация на уровне модели"""
        super().clean()
        if self.phone_number:
            # Удаляем пробелы и дефисы
            cleaned_phone = self.phone_number.replace(" ", "").replace("-", "")

            if not cleaned_phone.startswith("+7"):
                raise ValidationError(
                    {"phone_number": "Номер телефона должен начинаться с +7"}
                )

            if len(cleaned_phone) != 12:
                raise ValidationError(
                    {"phone_number": "Номер телефона должен содержать 12 символов"}
                )

            if not cleaned_phone[1:].isdigit():
                raise ValidationError(
                    {"phone_number": "После +7 должны быть только цифры"}
                )

            self.phone_number = cleaned_phone

    def save(self, *args, **kwargs):
        """Переопределяем save для автоматической очистки телефона"""
        self.clean()
        super().save(*args, **kwargs)

    def get_full_name(self):
        """Возвращает полное ФИО пациента"""
        parts = [self.surname, self.first_name]
        if self.last_name:
            parts.append(self.last_name)
        return " ".join(parts)

    def __str__(self):
        card_info = f" (карта {self.card_number})" if self.card_number else ""
        return f"{self.get_full_name()}{card_info}"

    class Meta:
        verbose_name = "Пациент"
        verbose_name_plural = "Пациенты"
        constraints = [
            models.UniqueConstraint(
                fields=["surname", "first_name", "last_name", "date_of_birth"],
                name="unique_patient_full_info_patients",
                violation_error_message="Пациент с такими ФИО и датой рождения уже существует в базе.",
            )
        ]
