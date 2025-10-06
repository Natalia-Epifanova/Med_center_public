from django.db import models
from django.utils.translation import gettext_lazy as _
from multiselectfield import MultiSelectField


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
        return f"Номер кабинета: {self.number}."

    class Meta:
        verbose_name = "Кабинет"
        verbose_name_plural = "Кабинеты"


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
    phone_number = models.CharField(
        max_length=12,
        verbose_name="Телефон пациента",
    )
    date_of_birth = models.DateField(
        blank=True,
        null=True,
        verbose_name="Дата рождения пациента",
    )
    registration_address = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="Адрес регистрации пациента",
    )
    residential_address = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="Адрес проживания пациента",
    )

    def __str__(self):
        return f"Пациент: {self.surname} {self.first_name} {self.last_name}"

    class Meta:
        verbose_name = "Пациент"
        verbose_name_plural = "Пациенты"


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
    specialization = MultiSelectField(
        choices=DoctorSpecialization.choices,
        max_choices=4,
        max_length=200,
        blank=True,
        verbose_name="Специализации врача",
        help_text="Выберите специализации врача",
    )

    provided_services = MultiSelectField(
        choices=MedicalServiceCategory.choices,
        max_choices=5,
        max_length=200,
        blank=True,
        verbose_name="Оказываемые категории услуг",
        help_text="Выберите категории услуг, которые оказывает врач",
    )

    def __str__(self):
        if not self.specialization:
            return f"{self.surname} {self.first_name} {self.last_name}"
        specializations_dict = dict(self.DoctorSpecialization.choices)

        specialization_labels = [
            str(specializations_dict.get(spec, spec)) for spec in self.specialization
        ]

        specialization_display = ", ".join(specialization_labels)
        return f"{specialization_display}: {self.surname} {self.first_name} {self.last_name}"

    class Meta:
        verbose_name = "Врач"
        verbose_name_plural = "Врачи"


class MedicalService(models.Model):
    """Модель для хранения медицинских услуг, прайса и кодов."""

    name = models.CharField(max_length=255, verbose_name="Название услуги")
    code = models.CharField(unique=True, max_length=20, verbose_name="Код услуги")
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

    allowed_specializations = MultiSelectField(
        choices=Doctor.DoctorSpecialization.choices,
        max_length=500,
        blank=True,
        verbose_name="Разрешенные специализации",
    )

    class Meta:
        verbose_name = "Медицинская услуга"
        verbose_name_plural = "Медицинские услуги"
        ordering = ["category", "name"]

    def __str__(self):
        return f"{self.name} - {self.price} руб."


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

    # Описание (например, "Обед", "Перерыв на кофе")
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
    patient = models.ForeignKey(
        Patient, on_delete=models.CASCADE, verbose_name="Пациент"
    )
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, verbose_name="Врач")
    service = models.ForeignKey(
        MedicalService, on_delete=models.PROTECT, verbose_name="Услуга"
    )
    cabinet = models.ForeignKey(
        Cabinet, on_delete=models.PROTECT, verbose_name="Кабинет", blank=True, null=True
    )

    # Временные метки
    date = models.DateField(verbose_name="Дата приема")
    start_time = models.TimeField(verbose_name="Время начала")
    end_time = models.TimeField(verbose_name="Время окончания")

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
    guarantee_letter_received = models.BooleanField(
        default=False, verbose_name="Гарантийное письмо получено"
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
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        verbose_name="Предыдущая запись в цепочке",
    )

    class Meta:
        verbose_name = "Запись на прием"
        verbose_name_plural = "Записи на прием"
        ordering = ["date", "start_time"]
        # Запрещаем дублирование времени для врача и кабинета
        constraints = [
            models.UniqueConstraint(
                fields=["doctor", "date", "start_time"],
                name="unique_appointment_doctor_time",
            ),
            models.UniqueConstraint(
                fields=["cabinet", "date", "start_time"],
                condition=models.Q(cabinet__isnull=False),
                name="unique_appointment_cabinet_time",
            ),
            models.UniqueConstraint(
                fields=["patient", "date", "start_time"],
                name="unique_appointment_patient_time",
            ),
        ]

    def __str__(self):
        return f"{self.patient.surname} - {self.doctor.surname} - {self.date} {self.start_time}"
