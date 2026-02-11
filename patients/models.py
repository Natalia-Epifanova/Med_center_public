from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone


class Patient(models.Model):
    """Модель пациента медицинской системы"""

    GENDER_CHOICES = [
        ("male", "Мужской"),
        ("female", "Женский"),
    ]

    # === ОБЯЗАТЕЛЬНЫЕ ПОЛЯ ===
    surname = models.CharField(
        max_length=50,
        verbose_name="Фамилия",
        help_text="Обязательное поле",
    )
    first_name = models.CharField(
        max_length=20,
        verbose_name="Имя",
        help_text="Обязательное поле",
    )

    # === ОСНОВНЫЕ ДАННЫЕ ===
    last_name = models.CharField(
        max_length=30,
        blank=True,
        default="",
        verbose_name="Отчество",
    )
    date_of_birth = models.DateField(
        blank=True,
        null=True,
        verbose_name="Дата рождения",
    )
    gender = models.CharField(
        max_length=10,
        choices=GENDER_CHOICES,
        blank=True,
        default="",
        verbose_name="Пол",
    )

    # === КОНТАКТНЫЕ ДАННЫЕ ===
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

    email = models.EmailField(
        verbose_name="Email",
        blank=True,
        null=True,
        help_text="Электронная почта пациента",
    )
    trusted_person = models.CharField(
        max_length=300,
        blank=True,
        null=True,
        verbose_name="Доверенное лицо",
    )

    # === НОМЕРА КАРТ ===
    card_number = models.PositiveIntegerField(
        blank=True,
        null=True,
        unique=True,
        verbose_name="Номер карты",
    )
    card_number_IP = models.PositiveIntegerField(
        blank=True,
        null=True,
        unique=True,
        verbose_name="Номер карты (ИП)",
    )
    card_number_OMS = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        unique=True,
        verbose_name="Номер карты (ОМС)",
    )

    # === АДРЕС ===
    area = models.CharField(
        max_length=100, blank=True, default="", verbose_name="Субъект РФ"
    )
    locality = models.CharField(
        max_length=100, blank=True, default="", verbose_name="Населенный пункт"
    )
    city = models.CharField(
        max_length=100, blank=True, default="", verbose_name="Город"
    )
    district = models.CharField(
        max_length=100, blank=True, default="", verbose_name="Район"
    )
    street = models.CharField(
        max_length=100, blank=True, default="", verbose_name="Улица"
    )
    home = models.CharField(max_length=8, blank=True, default="", verbose_name="Дом")
    building = models.CharField(
        max_length=4, blank=True, default="", verbose_name="Корпус/строение"
    )
    apartment = models.CharField(
        max_length=5, blank=True, default="", verbose_name="Квартира"
    )

    # === ПАСПОРТНЫЕ ДАННЫЕ ===
    passport_series = models.CharField(
        max_length=4, blank=True, default="", verbose_name="Серия паспорта"
    )
    passport_number = models.CharField(
        max_length=6, blank=True, default="", verbose_name="Номер паспорта"
    )
    passport_issue_date = models.DateField(
        blank=True, null=True, verbose_name="Дата выдачи"
    )
    who_issued_the_passport = models.CharField(
        max_length=100, blank=True, default="", verbose_name="Кем выдан"
    )

    # === СТРАХОВАНИЕ ===
    polis_oms = models.CharField(
        max_length=20, blank=True, default="", verbose_name="Полис ОМС"
    )
    snils = models.CharField(
        max_length=14, blank=True, default="", verbose_name="СНИЛС"
    )
    insurance_company = models.CharField(
        max_length=200, blank=True, default="", verbose_name="Страховая компания"
    )

    # === СВОЙСТВА (PROPERTIES) ===
    @property
    def full_name(self):
        """Полное ФИО пациента"""
        parts = [self.surname, self.first_name]
        if self.last_name:
            parts.append(self.last_name)
        return " ".join(parts)

    @property
    def full_address(self):
        """Форматированный полный адрес"""
        parts = []
        if self.area:
            parts.append(self.area)
        if self.city:
            parts.append(f"г. {self.city}")
        if self.street:
            parts.append(f"ул. {self.street}")
        if self.home:
            house_part = f"д. {self.home}"
            if self.building:
                house_part += f" корп. {self.building}"
            parts.append(house_part)
        if self.apartment:
            parts.append(f"кв. {self.apartment}")
        return ", ".join(parts)

    @property
    def age(self):
        """Возраст пациента в годах"""
        if not self.date_of_birth:
            return None
        today = timezone.now().date()
        return (
            today.year
            - self.date_of_birth.year
            - (
                (today.month, today.day)
                < (self.date_of_birth.month, self.date_of_birth.day)
            )
        )

    def get_last_appointment(self):
        """Для обратной совместимости"""
        from appointments.models import Appointment

        return (
            Appointment.objects.filter(patient=self)
            .select_related("time_slot__doctor", "service")
            .order_by("-time_slot__date", "-time_slot__start_time")
            .first()
        )

    def get_full_name(self):
        """Метод для обратной совместимости со старым кодом"""
        return self.full_name

    def get_appointments_for_documents(self):
        """Получить все записи пациента для выбора в документах"""
        from appointments.models import Appointment

        return (
            Appointment.objects.filter(patient=self)
            .select_related("time_slot__doctor", "service")
            .order_by("-time_slot__date", "-time_slot__start_time")
        )

    def get_appointment_history(self):
        """Получить историю записей пациента (для обратной совместимости)"""
        from appointments.models import Appointment

        return (
            Appointment.objects.filter(patient=self)
            .select_related("time_slot__doctor", "time_slot__cabinet", "service")
            .prefetch_related("selected_blood_tests")
            .order_by("-time_slot__date", "-time_slot__start_time")
        )

    # === ВАЛИДАЦИЯ ===
    def clean(self):
        """Валидация модели"""
        errors = {}

        # Проверка уникальности по ФИО и дате рождения
        if self.surname and self.first_name and self.date_of_birth:
            query = Patient.objects.filter(
                surname__iexact=self.surname,
                first_name__iexact=self.first_name,
                date_of_birth=self.date_of_birth,
            )
            if self.pk:
                query = query.exclude(pk=self.pk)

            if query.exists():
                errors.setdefault("__all__", []).append(
                    "Пациент с такими ФИО и датой рождения уже существует"
                )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        """Сохранение с предварительной очисткой"""
        self.clean()
        super().save(*args, **kwargs)

    # === МЕТА-ИНФОРМАЦИЯ ===
    class Meta:
        verbose_name = "Пациент"
        verbose_name_plural = "Пациенты"
        ordering = ["surname", "first_name", "last_name"]
        indexes = [
            models.Index(fields=["surname", "first_name"]),
            models.Index(fields=["phone_number"]),
            models.Index(fields=["card_number"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["surname", "first_name", "last_name", "date_of_birth"],
                name="unique_patient_full_info",
                violation_error_message="Пациент с такими ФИО и датой рождения уже существует",
            ),
        ]

    def __str__(self):
        return f"{self.full_name} ({self.card_number or 'без карты'})"


class ReserveList(models.Model):
    """Основная модель резервного списка, группирует записи по месяцам"""

    doctor = models.ForeignKey(
        "timetable.Doctor", on_delete=models.CASCADE, verbose_name="Врач"
    )
    month = models.PositiveSmallIntegerField(verbose_name="Месяц (1-12)")
    year = models.PositiveSmallIntegerField(verbose_name="Год")

    class Meta:
        verbose_name = "Список резерва"
        verbose_name_plural = "Списки резерва"
        ordering = ["-year", "-month", "doctor"]
        unique_together = ["doctor", "month", "year"]

    def __str__(self):
        return f"{self.doctor.surname} {self.doctor.first_name} {self.doctor.last_name} - {self.get_month_display()} {self.year}"

    def get_month_display(self):
        """Получаем название месяца"""
        from patients.utils import get_russian_month_name

        return get_russian_month_name(self.month).capitalize()

    def patient_count(self):
        """Количество пациентов в списке"""
        return self.entries.count()


class ReservePatient(models.Model):
    """Отдельная запись в резервном списке"""

    reserve_list = models.ForeignKey(
        ReserveList, on_delete=models.CASCADE, related_name="entries"
    )
    patient = models.ForeignKey(
        Patient,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="Пациент (если найден в БД)",
    )

    # Данные пациента (заполняются, если нет в БД)
    surname = models.CharField(max_length=50, verbose_name="Фамилия")
    first_name = models.CharField(max_length=20, verbose_name="Имя")
    last_name = models.CharField(
        max_length=30, blank=True, default="", verbose_name="Отчество"
    )
    date_of_birth = models.DateField(
        null=True, blank=True, verbose_name="Дата рождения"
    )
    # === КОНТАКТНЫЕ ДАННЫЕ ===
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

    comment = models.TextField(blank=True, verbose_name="Комментарий")

    class Meta:
        verbose_name = "Запись резерва"
        verbose_name_plural = "Записи резерва"


class WaitlistPatient(models.Model):
    """Пациенты в листе ожидания (не имеющие текущих записей)"""

    doctor = models.ForeignKey(
        "timetable.Doctor", on_delete=models.CASCADE, verbose_name="Врач"
    )
    patient = models.ForeignKey(
        Patient, on_delete=models.CASCADE, verbose_name="Пациент", null=True, blank=True
    )

    # Основные данные (если пациента нет в базе)
    surname = models.CharField(max_length=50, verbose_name="Фамилия")
    first_name = models.CharField(max_length=20, verbose_name="Имя")
    last_name = models.CharField(
        max_length=30, blank=True, default="", verbose_name="Отчество"
    )
    phone_number = models.CharField(
        max_length=12, blank=True, null=True, verbose_name="Телефон пациента"
    )
    date_of_birth = models.DateField(
        null=True, blank=True, verbose_name="Дата рождения"
    )

    comment = models.TextField(blank=True, verbose_name="Комментарий")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Пациент листа ожидания"
        verbose_name_plural = "Пациенты листа ожидания"
        ordering = ["-created_at"]
