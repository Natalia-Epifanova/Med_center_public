from django.db import models
from django.utils.translation import gettext_lazy as _
from multiselectfield import MultiSelectField

from patients.models import Patient


class MedicalServiceCategory(models.TextChoices):
    """Категории медицинских услуг (для группировки)."""

    JOINT_ULTRASOUND = "joint_us", _("УЗИ суставов")
    ORGAN_ULTRASOUND = "organ_us", _("УЗИ внутренних органов")
    DOPPLEROGRAPHY = "doppler", _("Ультразвуковая допплерография")
    DENSITOMETRY = "densitometry", _("Ультразвуковая денситометрия")
    XRAY = "xray", _("Рентген")
    FIRST_CONSULTATION = "first_consult", _("Первичная консультация")
    SECOND_CONSULTATION = "second_consult", _("Повторная консультация")
    MANUFACTURE_OF_INSOLES = "manufacture_of_insoles", _("Изготовление стелек")
    ANALYZES = "analyzes", _("Анализы")
    MEDICAL_BLOCKADES = "medical_blockades", _("Медикаментозные блокады")


class Cabinet(models.Model):
    number = models.PositiveIntegerField(unique=True, verbose_name="Номер кабинета")
    name_of_cabinet = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name="Название/описание кабинета",
    )

    def __str__(self):
        return f"Кабинет №: {self.number}. ({self.name_of_cabinet})"

    class Meta:
        verbose_name = "Кабинет"
        verbose_name_plural = "Кабинеты"


class MedicalService(models.Model):
    """Модель для хранения медицинских услуг, прайса и кодов."""

    code = models.CharField(max_length=20, verbose_name="Код услуги")
    name = models.CharField(max_length=255, verbose_name="Название услуги")
    price = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name="Цена услуги"
    )
    category = models.CharField(
        max_length=30,
        choices=MedicalServiceCategory.choices,
        verbose_name="Категория услуги",
    )

    description = models.TextField(blank=True, verbose_name="Описание услуги")
    is_active = models.BooleanField(default=True, verbose_name="Активная услуга")

    class Meta:
        verbose_name = "Медицинская услуга"
        verbose_name_plural = "Медицинские услуги"
        ordering = ["category", "name"]

    def __str__(self):
        return f"{self.name} - {self.price} руб."


class Doctor(models.Model):
    class DoctorSpecialization(models.TextChoices):
        RHEUMATOLOGIST_1 = "rheumatologist_1", _("Ревматолог категория 1")
        RHEUMATOLOGIST_2 = "rheumatologist_2", _("Ревматолог категория 2")
        RHEUMATOLOGIST_3 = "rheumatologist_3", _("Ревматолог категория 3")
        ORTHOPEDIC_TRAUMATOLOGIST = "Orthopedic-traumatologist", _(
            "Травматолог-ортопед"
        )
        NURSE = "nurse", _("Медсестра")
        NEUROLOGIST = "neurologist", _("Невролог")
        CARDIOLOGIST = "cardiologist", _("Кардиолог")
        GASTROENTEROLOGIST = "gastroenterologist", _("Гастроэнтеролог")
        NEPHROLOGIST = "nephrologist", _("Нефролог")
        DERMATOVENEROLOGIST = (
            "dermatovenerologist",
            _("Дерматовенеролог"),
        )
        ULTRASOUND_DIAGNOSTICS_DOCTOR = "ultrasound_diagnostics_doctor", _(
            "Врач ультразвуковой диагностики"
        )
        RADIOLOGIST = "radiologist", _("Рентгенолог")

    first_name = models.CharField(max_length=20, verbose_name="Имя врача")
    last_name = models.CharField(max_length=30, verbose_name="Отчество врача")
    surname = models.CharField(max_length=50, verbose_name="Фамилия врача")
    specialization = models.CharField(
        max_length=50,
        choices=DoctorSpecialization.choices,
        verbose_name="Основная специализация",
    )

    provided_services = MultiSelectField(
        choices=MedicalServiceCategory.choices,
        max_choices=10,
        max_length=200,
        blank=True,
        verbose_name="Категории оказываемых услуг",
        help_text="Выберите категории услуг, которые оказывает врач",
    )

    excluded_services = models.ManyToManyField(
        MedicalService,
        blank=True,
        verbose_name="Исключенные услуги",
        help_text="Услуги, которые недоступны для этого врача (исключения из категорий)",
    )

    schedule_comment = models.TextField(
        blank=True,
        verbose_name="Комментарий для расписания",
        help_text="Этот комментарий будет отображаться перед слотами врача в расписании",
    )

    def __str__(self):
        specialization_dict = dict(self.DoctorSpecialization.choices)
        spec_display = specialization_dict.get(self.specialization, self.specialization)
        return f"{spec_display}: {self.surname} {self.first_name} {self.last_name}"

    def get_available_services(self):
        """Получить все услуги, доступные врачу с учетом исключений"""
        services = MedicalService.objects.filter(
            category__in=self.provided_services, is_active=True
        ).exclude(id__in=self.excluded_services.values_list("id", flat=True))
        return services

    class Meta:
        verbose_name = "Врач"
        verbose_name_plural = "Врачи"


class TimeSlot(models.Model):
    """
    Модель для хранения временных слотов расписания.
    Каждый слот привязан к конкретному врачу, кабинету и дате.
    """

    # Основные связи
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, verbose_name="Врач")
    cabinet = models.ForeignKey(
        Cabinet, on_delete=models.CASCADE, verbose_name="Кабинет"
    )
    date = models.DateField(verbose_name="Дата расписания")

    # Временные интервалы
    start_time = models.TimeField(verbose_name="Время начала")
    end_time = models.TimeField(verbose_name="Время окончания")

    # Тип слота: рабочий слот или перерыв
    SLOT_TYPE_CHOICES = (
        ("working", "Рабочий слот"),
        ("break", "Перерыв"),
    )
    slot_type = models.CharField(
        max_length=10,
        choices=SLOT_TYPE_CHOICES,
        default="working",
        verbose_name="Тип слота",
    )
    description = models.CharField(max_length=100, blank=True, verbose_name="Описание")

    class Meta:
        verbose_name = "Слот расписания"
        verbose_name_plural = "Слоты расписания"
        ordering = ["date", "cabinet", "start_time"]
        # Запрещаем дублирование слотов для одного врача
        constraints = [
            models.UniqueConstraint(
                fields=["doctor", "date", "start_time"], name="unique_doctor_time_slot"
            ),
        ]

    def __str__(self):
        slot_type_display = "Перерыв" if self.slot_type == "break" else "Слот"
        return f"{self.date} {self.start_time}-{self.end_time} - {self.doctor.surname} ({slot_type_display})"

    def is_available(self):
        """Проверяет, доступен ли слот для записи"""
        return self.slot_type == "working" and not self.appointments.exists()

    def get_next_consecutive_slot(self):
        """Получает следующий последовательный слот"""
        return TimeSlot.objects.filter(
            date=self.date,
            cabinet=self.cabinet,
            doctor=self.doctor,
            start_time=self.end_time,
            slot_type="working",
        ).first()

    def has_time_conflict(self, other_slot):
        """Проверяет, пересекается ли этот слот с другим слотом"""
        if self.date != other_slot.date:
            return False

        # Проверяем пересечение временных интервалов
        return not (
            self.end_time <= other_slot.start_time
            or self.start_time >= other_slot.end_time
        )

    @classmethod
    def get_conflicting_slots(
        cls, date, start_time, end_time, cabinet=None, exclude_slot_id=None
    ):
        """Находит все конфликтующие слоты для указанного времени"""
        queryset = cls.objects.filter(
            date=date,
            # Ищем слоты, которые пересекаются с указанным временем
            start_time__lt=end_time,  # слот начинается до окончания нашего времени
            end_time__gt=start_time,  # слот заканчивается после начала нашего времени
            slot_type="working",  # только рабочие слоты
        )

        if cabinet:
            queryset = queryset.filter(cabinet=cabinet)

        if exclude_slot_id:
            queryset = queryset.exclude(id=exclude_slot_id)

        return queryset

    def is_time_available(self, cabinet=None):
        """Проверяет, доступно ли это время в указанном кабинете"""
        conflicting_slots = TimeSlot.get_conflicting_slots(
            date=self.date,
            start_time=self.start_time,
            end_time=self.end_time,
            cabinet=cabinet,
            exclude_slot_id=self.id,
        )
        return not conflicting_slots.exists()

    def has_time_overlap(self, other_start, other_end):
        """Проверяет, пересекается ли этот временной интервал с другим"""
        return not (self.end_time <= other_start or self.start_time >= other_end)


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


class DayComment(models.Model):
    """Комментарий для дня (только для администраторов)"""

    date = models.DateField(unique=True, verbose_name="Дата")
    comment = models.TextField(verbose_name="Комментарий", blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Комментарий дня"
        verbose_name_plural = "Комментарии дней"
        ordering = ["-date"]

    def __str__(self):
        return f"Комментарий на {self.date}: {self.comment[:50]}..."
