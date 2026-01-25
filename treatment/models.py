from django.db import models
from django.utils import timezone


class MKB10Diagnosis(models.Model):
    """Справочник диагнозов МКБ-10"""

    code = models.CharField(
        max_length=10,
        unique=True,
        verbose_name="Код МКБ-10",
        help_text="Например: M05.8, I10, J45.9",
    )

    name = models.CharField(
        max_length=500,
        verbose_name="Название диагноза",
        help_text="Полное наименование диагноза",
    )

    chapter = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Глава",
        help_text="Название главы МКБ-10",
    )

    block = models.CharField(
        max_length=200, blank=True, verbose_name="Блок", help_text="Название блока"
    )

    is_active = models.BooleanField(default=True, verbose_name="Активный диагноз")

    class Meta:
        verbose_name = "Диагноз МКБ-10"
        verbose_name_plural = "Диагнозы МКБ-10"
        ordering = ["code"]
        indexes = [
            models.Index(fields=["code"]),
            models.Index(fields=["name"]),
        ]

    def __str__(self):
        return f"{self.code} - {self.name}"

    @classmethod
    def search_by_name_or_code(cls, query):
        """Поиск диагноза по названию или коду"""
        return cls.objects.filter(
            models.Q(code__icontains=query)
            | models.Q(name__icontains=query)
            | models.Q(chapter__icontains=query)
        ).filter(is_active=True)


# Create your models here.
class DoctorTreatment(models.Model):
    """Модель приема врача (ревматолога, невролога и др.)"""

    # Связи с другими моделями
    appointment = models.OneToOneField(
        "appointments.Appointment",
        on_delete=models.CASCADE,
        verbose_name="Запись на прием",
        related_name="doctor_appointment",
    )

    # Жалобы пациента
    complaints = models.TextField(
        blank=True, verbose_name="Жалобы", help_text="Основные жалобы пациента"
    )

    # Анамнез жизни
    life_anamnesis = models.TextField(
        blank=True,
        verbose_name="Анамнез жизни",
        help_text="Общие сведения о жизни пациента",
    )

    # Анамнез заболевания
    disease_anamnesis = models.TextField(
        blank=True,
        verbose_name="Анамнез заболевания",
        help_text="История развития текущего заболевания",
    )

    # Объективный статус
    objective_status = models.TextField(
        blank=True,
        verbose_name="Объективный статус",
        help_text="Результаты общего осмотра",
    )
    # Объективный статус
    additional_surveys = models.TextField(
        blank=True,
        verbose_name="Дополнительные обследования",
        help_text="Дополнительные обследования",
    )

    # Диагноз
    diagnosis = models.TextField(
        blank=True,
        verbose_name="Диагноз",
        help_text="Клинический диагноз",
    )
    mkb10_diagnoses = models.ManyToManyField(
        MKB10Diagnosis,
        blank=True,
        verbose_name="Диагнозы по МКБ-10",
        related_name="appointments",
    )

    # Рекомендации
    recommendations = models.TextField(
        blank=True,
        verbose_name="Рекомендации",
        help_text="Назначения и рекомендации врача",
    )

    class Meta:
        verbose_name = "Прием врача"
        verbose_name_plural = "Приемы врачей"
        constraints = [
            models.UniqueConstraint(
                fields=["appointment"], name="unique_appointment_doctor_exam"
            )
        ]

    def __str__(self):
        return f"Прием от {self.appointment.time_slot.date} - {self.appointment.patient.full_name} ({self.appointment.time_slot.doctor.surname})"
