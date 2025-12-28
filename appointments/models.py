from django.db import models
from django.db.models import Sum
from django.utils.translation import gettext_lazy as _

from patients.models import Patient
from timetable.models import BloodTest, MedicalService, TimeSlot


class AppointmentChain(models.Model):
    """Связь между записями к разным врачам"""

    class Meta:
        verbose_name = "Связь записей"
        verbose_name_plural = "Связи записей"
        ordering = ["order"]
        unique_together = ["main_appointment", "related_appointment"]

    # Основные связи
    main_appointment = models.ForeignKey(
        "Appointment",
        on_delete=models.CASCADE,
        related_name="chain_as_main",
        verbose_name="Основная запись",
    )
    related_appointment = models.ForeignKey(
        "Appointment",
        on_delete=models.CASCADE,
        related_name="chain_as_related",
        verbose_name="Связанная запись",
    )

    # Порядок в цепочке (для отображения)
    order = models.PositiveIntegerField(default=0, verbose_name="Порядок в цепочке")

    # Тип связи
    class ChainType(models.TextChoices):
        SAME_DOCTOR_ADDITIONAL = "same_doctor_additional", _(
            "Вторая услуга у того же врача"
        )
        SAME_DOCTOR_TWO_SLOTS = "same_doc_two_slots", _("Два слота у того же врача")
        ANOTHER_DOCTOR = "another_doctor", _("Запись к другому врачу")
        PROCEDURAL = "procedural", _("Процедурный кабинет")

    chain_type = models.CharField(
        max_length=30,
        choices=ChainType.choices,
        default=ChainType.ANOTHER_DOCTOR,
        verbose_name="Тип связи",
    )

    # Время создания
    created_at = models.DateTimeField(
        auto_now_add=True, verbose_name="Время создания связи"
    )

    def __str__(self):
        return f"Связь {self.main_appointment.id} → {self.related_appointment.id} ({self.chain_type})"


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

    # НОВОЕ: Тип цепочки записей
    class ChainType(models.TextChoices):
        SINGLE = "single", _("Одиночная запись")
        SAME_DOCTOR = "same_doctor", _("Несколько услуг у одного врача")
        MULTIPLE_DOCTORS = "multiple_doctors", _("Записи к разным врачам")
        PROCEDURAL = "procedural", _("С процедурным кабинетом")

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
    price_at_appointment = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Цена на момент записи",
        help_text="Цена услуги на момент создания записи",
    )
    total_with_blood_tests = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Общая сумма с анализами",
    )

    # НОВОЕ: Тип цепочки (изначально single)
    chain_type = models.CharField(
        max_length=20,
        choices=ChainType.choices,
        default=ChainType.SINGLE,
        verbose_name="Тип цепочки записей",
    )

    # НОВОЕ: Является ли эта запись основной в цепочке
    is_chain_main = models.BooleanField(
        default=False,
        verbose_name="Основная запись в цепочке",
        help_text="Отметьте, если это основная запись в цепочке к разным врачам",
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

    @property
    def actual_price(self):
        """Возвращает цену, которая должна отображаться в истории"""
        return self.price_at_appointment or self.service.price

    @property
    def get_tests_price(self):
        """Возвращает общую стоимость выбранных анализов"""
        if hasattr(self, "selected_blood_tests"):
            total = (
                self.selected_blood_tests.aggregate(total=Sum("blood_test__price"))[
                    "total"
                ]
                or 0
            )
            return total
        return 0

    @property
    def get_total_price(self):
        """Возвращает общую стоимость (анализы + услуга)"""
        tests_price = self.get_tests_price
        service_price = self.service.price if self.service else 0
        return tests_price + service_price

    def save(self, *args, **kwargs):
        """Переопределяем save для сохранения цены на момент записи и установки типа цепочки"""

        # Если запись создается и у нее есть услуга
        if not self.pk and self.service and not self.price_at_appointment:
            self.price_at_appointment = self.service.price

        # Если обновляется услуга
        elif self.service and not self.price_at_appointment:
            self.price_at_appointment = self.service.price

        # Определяем тип цепочки для новых записей с предыдущей записью
        if not self.pk and self.previous_appointment:
            self.chain_type = self.ChainType.SAME_DOCTOR
        super().save(*args, **kwargs)

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

    def get_chain_appointments(self):
        """Получить все записи в цепочке (как основные, так и связанные)"""
        from .models import \
            AppointmentChain  # Импорт внутри метода чтобы избежать циклического импорта

        appointments = []

        # Получаем записи, где эта запись является основной
        as_main = (
            AppointmentChain.objects.filter(main_appointment=self)
            .select_related(
                "related_appointment",
                "related_appointment__time_slot",
                "related_appointment__patient",
                "related_appointment__service",
            )
            .order_by("order")
        )

        # Получаем записи, где эта запись является связанной
        as_related = AppointmentChain.objects.filter(
            related_appointment=self
        ).select_related("main_appointment")

        # Если эта запись - основная в цепочке
        if self.is_chain_main:
            appointments.append(self)
            for chain in as_main:
                appointments.append(chain.related_appointment)

        # Если эта запись - связанная в цепочке
        elif as_related.exists():
            main_chain = as_related.first()
            main_appointment = main_chain.main_appointment
            appointments = main_appointment.get_chain_appointments()

        # Если это одиночная запись
        else:
            appointments = [self]

        return appointments

    def get_related_appointments(self):
        """Получить только связанные записи (без основной)"""
        if not self.is_chain_main:
            # Если это не основная запись, получаем основную
            chain = AppointmentChain.objects.filter(related_appointment=self).first()
            if chain:
                return chain.main_appointment.get_related_appointments()
            return []

        return (
            AppointmentChain.objects.filter(main_appointment=self)
            .select_related("related_appointment")
            .order_by("order")
        )

    def add_related_appointment(
        self, appointment, chain_type="another_doctor", order=None
    ):
        """Добавить связанную запись"""
        if not self.is_chain_main:
            raise ValueError("Только основная запись может иметь связанные записи")

        # Определяем порядок
        if order is None:
            max_order = (
                AppointmentChain.objects.filter(main_appointment=self).aggregate(
                    models.Max("order")
                )["order__max"]
                or 0
            )
            order = max_order + 1

        # Создаем связь
        chain = AppointmentChain.objects.create(
            main_appointment=self,
            related_appointment=appointment,
            chain_type=chain_type,
            order=order,
        )

        # Обновляем тип цепочки основной записи
        if chain_type in ["another_doctor", "procedural"]:
            self.chain_type = self.ChainType.MULTIPLE_DOCTORS
        elif chain_type == "same_doctor_additional":
            self.chain_type = self.ChainType.SAME_DOCTOR
        self.save()

        return chain

    def remove_related_appointment(self, appointment):
        """Удалить связанную запись"""
        chain = AppointmentChain.objects.filter(
            main_appointment=self, related_appointment=appointment
        ).first()

        if chain:
            chain.delete()

            # Проверяем, остались ли связанные записи
            if not self.get_related_appointments().exists():
                self.chain_type = self.ChainType.SINGLE
                self.save()

    @property
    def has_related_appointments(self):
        """Есть ли связанные записи"""
        return AppointmentChain.objects.filter(main_appointment=self).exists()


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
