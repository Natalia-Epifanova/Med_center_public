from django.db import models
from django.utils.translation import gettext_lazy as _

from patients.models import Patient
from timetable.models import TimeSlot, MedicalService, BloodTest


class Appointment(models.Model):
    # Статусы записи
    class AppointmentStatus(models.TextChoices):
        SCHEDULED = "scheduled", _("Запланирован")
        CONFIRMED = "confirmed", _("Подтвержден")
        COMPLETED = "completed", _("Завершен")
        CANCELLED = "cancelled", _("Отменен пациентом")
        NO_SHOW = "no_show", _("Не явился")

    # Типы оплаты
    class InsuranceType(models.TextChoices):
        OMS = "oms", _("ОМС")
        DMS = "dms", _("ДМС")
        PAID = "paid", _("Платный")

    # Основные связи
    time_slot = models.ForeignKey(
        TimeSlot,
        on_delete=models.CASCADE,
        verbose_name="Временной слот",
        related_name="appointments",
    )
    patient = models.ForeignKey(
        Patient, on_delete=models.CASCADE, verbose_name="Пациент"
    )
    service = models.ForeignKey(
        MedicalService, on_delete=models.PROTECT, verbose_name="Услуга"
    )

    # Статусы и пометки
    status = models.CharField(
        max_length=20,
        choices=AppointmentStatus.choices,
        default=AppointmentStatus.SCHEDULED,
        verbose_name="Статус записи",
    )
    insurance_type = models.CharField(
        max_length=10, choices=InsuranceType.choices, verbose_name="Тип оплаты"
    )
    needs_reschedule = models.BooleanField(
        default=False, verbose_name="Требуется перезапись на более ранний срок"
    )
    comment = models.TextField(blank=True, verbose_name="Комментарий администратора")

    # Метка, если пациент записан на несколько процедур подряд
    is_consecutive = models.BooleanField(
        default=False, verbose_name="Запись подряд (второе и последующее 'окно')"
    )
    previous_appointment = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        verbose_name="Предыдущая запись в цепочке",
    )
    occupies_two_slots = models.BooleanField(
        default=False,
        verbose_name="Занимает два временных слота",
        help_text="Отметьте, если услуга требует два последовательных временных слота",
    )

    class Meta:
        verbose_name = "Запись на прием"
        verbose_name_plural = "Записи на прием"
        ordering = ["time_slot__date", "time_slot__start_time"]

    def __str__(self):
        patient_name = self.patient.surname if self.patient else "Нет пациента"
        doctor_name = (
            self.time_slot.doctor.surname if self.time_slot.doctor else "Нет врача"
        )
        date_time = (
            f"{self.time_slot.date} {self.time_slot.start_time}"
            if self.time_slot
            else "Нет слота"
        )
        return f"{patient_name} - {doctor_name} - {date_time}"

    @property
    def date(self):
        return self.time_slot.date

    @property
    def start_time(self):
        return self.time_slot.start_time

    @property
    def end_time(self):
        return self.time_slot.end_time

    @property
    def doctor(self):
        return self.time_slot.doctor

    @property
    def cabinet(self):
        return self.time_slot.cabinet

    def get_consecutive_appointments(self):
        """Возвращает все последующие записи в цепочке"""
        appointments = []
        current = self
        while current:
            appointments.append(current)
            # Ищем следующую запись в цепочке
            next_appointment = Appointment.objects.filter(
                previous_appointment=current
            ).first()
            current = next_appointment
        return appointments

    def get_full_chain(self):
        """Возвращает полную цепочку записей (все связанные)"""
        # Находим начало цепочки
        chain_start = self
        while chain_start.previous_appointment:
            chain_start = chain_start.previous_appointment

        return chain_start.get_consecutive_appointments()

    def can_add_consecutive(self):
        """Проверяет, можно ли добавить следующую запись"""
        if self.time_slot.slot_type != "working":
            return False

        # Проверяем, есть ли уже следующая запись
        if Appointment.objects.filter(previous_appointment=self).exists():
            return False

        return True


class AppointmentBloodTest(models.Model):
    """Связь между записью и выбранными анализами крови"""

    appointment = models.ForeignKey(
        Appointment,
        on_delete=models.CASCADE,
        related_name="selected_blood_tests",
        verbose_name="Запись на прием",
    )
    blood_test = models.ForeignKey(
        BloodTest, on_delete=models.CASCADE, verbose_name="Анализ крови"
    )

    class Meta:
        verbose_name = "Выбранный анализ крови"
        verbose_name_plural = "Выбранные анализы крови"
        unique_together = ["appointment", "blood_test"]
