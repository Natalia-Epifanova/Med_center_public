from django.core.cache import cache
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
    MANUFACTURE_OF_INSOLES = "manufacture_of_insoles", _("Плантография")
    ANALYZES = "analyzes", _("Анализы")
    MEDICAL_BLOCKADES = "medical_blockades", _("Медикаментозные блокады")
    PHYSIO_PROCEDURES = "physio_procedures", _("Физио процедуры")


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


class MedicalServicePrice(models.Model):
    service = models.ForeignKey(
        MedicalService,
        on_delete=models.CASCADE,
        related_name="prices",
        verbose_name="Услуга",
    )
    valid_from = models.DateField(verbose_name="Действует с")
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Цена")

    class Meta:
        verbose_name = "Цена услуги"
        verbose_name_plural = "Цены услуг"
        ordering = ["-valid_from"]
        constraints = [
            models.UniqueConstraint(
                fields=["service", "valid_from"], name="uniq_service_valid_from"
            )
        ]
        indexes = [
            models.Index(
                fields=["service", "valid_from"], name="idx_service_valid_from"
            )
        ]

    def __str__(self):
        return f"{self.service.name}: {self.price} руб. с {self.valid_from}"


class Doctor(models.Model):
    class DoctorSpecialization(models.TextChoices):
        RHEUMATOLOGIST = "rheumatologist", _("Ревматолог")
        ORTHOPEDIC_TRAUMATOLOGIST = "Orthopedic-traumatologist", _(
            "Травматолог-ортопед"
        )
        NURSE = "nurse", _("Старшая медсестра")
        NEUROLOGIST = "neurologist", _("Невролог")
        CARDIOLOGIST = "cardiologist", _("Кардиолог")
        GASTROENTEROLOGIST = "gastroenterologist", _("Гастроэнтеролог")
        NEPHROLOGIST = "nephrologist", _("Нефролог")
        DERMATOVENEROLOGIST = (
            "dermatovenerologist",
            _("Дерматовенеролог"),
        )
        PSYCHOLOGIST = (
            "specialist_in_psychological_support)",
            _(
                "Специалист по психологическому сопровождению психосоматических расстройств"
            ),
        )
        ULTRASOUND_DIAGNOSTICS_DOCTOR = "ultrasound_diagnostics_doctor", _(
            "Врач ультразвуковой диагностики"
        )
        RADIOLOGIST = "radiologist", _("Рентгенолаборант")

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
        services = (
            MedicalService.objects.filter(
                category__in=self.provided_services, is_active=True
            )
            .exclude(id__in=self.excluded_services.values_list("id", flat=True))
            .order_by("name")
        )  # ДОБАВЛЕНО: сортировка по названию
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

    def is_available(self, exclude_appointment_id=None, exclude_slot_id=None):
        """Проверка доступности слота"""
        from appointments.models import Appointment

        # Быстрая проверка типа слота
        if self.slot_type != "working":
            return False

        # Проверяем наличие записей БЕЗ кэширования
        appointments_count = self.appointments.count()
        is_available = appointments_count == 0

        # Проверка исключений
        if not is_available and exclude_appointment_id:
            # Проверяем, является ли единственная запись исключаемой
            appointments = self.appointments.all()
            if (
                appointments.count() == 1
                and appointments.first().id == exclude_appointment_id
            ):
                return True

        return is_available

    def get_next_consecutive_slot(self):
        """Получает следующий последовательный слот"""
        return TimeSlot.objects.filter(
            date=self.date,
            cabinet=self.cabinet,
            doctor=self.doctor,
            start_time=self.end_time,
            slot_type="working",
        ).first()

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


class CabinetDayComment(models.Model):
    """Комментарий для кабинета на определенную дату"""

    date = models.DateField(verbose_name="Дата")
    cabinet = models.ForeignKey(
        Cabinet,
        on_delete=models.CASCADE,
        verbose_name="Кабинет",
        related_name="day_comments",
    )
    comment = models.TextField(verbose_name="Комментарий", blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Комментарий кабинета"
        verbose_name_plural = "Комментарии кабинетов"
        unique_together = ["date", "cabinet"]  # Один комментарий на кабинет в день
        ordering = ["date", "cabinet__number"]

    def __str__(self):
        return f"Комментарий кабинета {self.cabinet.number} на {self.date}"


class BloodTestCategory(models.Model):
    """Категории анализов крови"""

    name = models.CharField(max_length=200, verbose_name="Название категории")
    order = models.PositiveIntegerField(default=0, verbose_name="Порядок сортировки")
    is_active = models.BooleanField(default=True, verbose_name="Активная категория")

    class Meta:
        verbose_name = "Категория анализов крови"
        verbose_name_plural = "Категории анализов крови"

    def __str__(self):
        return self.name


class BloodTest(models.Model):
    """Модель для анализов крови"""

    class BiomaterialType(models.TextChoices):
        SERUM = "serum", _("Кровь (сыворотка)")
        PLASMA = "plasma", _("Кровь (плазма с NaCi)")
        EDTA = "edta", _("Кровь (ЭДТА)")
        LITHIUM_HEPARIN = "lithium_heparin", _("Кровь (литий-гепарин)")

    # Основная информация
    code = models.CharField(max_length=25, verbose_name="Код услуги")
    name = models.CharField(
        max_length=500, verbose_name="Наименование анализа", unique=True
    )
    category = models.ForeignKey(
        BloodTestCategory,
        on_delete=models.CASCADE,
        related_name="tests",
        verbose_name="Категория",
    )
    # Медицинская информация
    biomaterial = models.CharField(
        max_length=20,
        choices=BiomaterialType.choices,
        default=BiomaterialType.SERUM,
        verbose_name="Биоматериал",
    )
    execution_time = models.CharField(
        max_length=50, default="1 день", verbose_name="Срок выполнения"
    )
    # Ценовая информация
    price = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, verbose_name="Цена"
    )

    class Meta:
        verbose_name = "Анализ крови"
        verbose_name_plural = "Анализы крови"

    def __str__(self):
        return f"{self.name} - {self.price} руб."


class BloodTestPrice(models.Model):
    blood_test = models.ForeignKey(
        BloodTest,
        on_delete=models.CASCADE,
        related_name="prices",
        verbose_name="Анализ крови",
    )
    valid_from = models.DateField(verbose_name="Действует с")
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Цена")

    class Meta:
        verbose_name = "Цена анализа крови"
        verbose_name_plural = "Цены анализов крови"
        ordering = ["-valid_from"]
        constraints = [
            models.UniqueConstraint(
                fields=["blood_test", "valid_from"],
                name="uniq_blood_test_valid_from",
            )
        ]
        indexes = [
            models.Index(
                fields=["blood_test", "valid_from"],
                name="idx_blood_test_valid_from",
            )
        ]

    def __str__(self):
        return f"{self.blood_test.name}: {self.price} руб. с {self.valid_from}"
