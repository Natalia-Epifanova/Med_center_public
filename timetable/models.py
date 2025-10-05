from django.db import models
from django.utils.translation import gettext_lazy as _
from multiselectfield import MultiSelectField


class MedicalServiceCategory(models.TextChoices):
    """Категории медицинских услуг (для группировки)."""

    JOINT_ULTRASOUND = "joint_us", _("УЗИ суставов")
    ORGAN_ULTRASOUND = "organ_us", _("УЗИ внутренних органов")
    DOPPLEROGRAPHY = "doppler", _("Ультразвуковая допплерография")
    XRAY = "xray", _("Рентген")
    FIRST_CONSULTATION = "first_consult", _("Первичная консультация")
    SECOND_CONSULTATION = "second_consult", _("Повторная консультация")


class Cabinet(models.Model):
    number = models.PositiveIntegerField(unique=True, verbose_name="Номер стола")
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
        NEUROLOGIST = "neurologist", _("Невролог")
        CARDIOLOGIST = "cardiologist", _("Кардиолог")
        GASTROENTEROLOGIST = "gastroenterologist", _("Гастроэнтеролог")
        NEPHROLOGIST = "nephrologist", _("Нефролог")
        DERMATOVENEROLOGIST = "dermatovenerologist", _("Дерматовенеролог")

    first_name = models.CharField(max_length=20, verbose_name="Имя врача")
    last_name = models.CharField(max_length=30, verbose_name="Отчество врача")
    surname = models.CharField(max_length=50, verbose_name="Фамилия врача")
    specialization = models.CharField(
        max_length=100,
        choices=DoctorSpecialization.choices,  # Используем TextChoices
        verbose_name="Специализация врача",
    )
    provided_services = models.ManyToManyField(
        "MedicalService", verbose_name="Оказываемые услуги"
    )

    def __str__(self):
        specialization_label = self.get_specialization_display()
        return (
            f"{specialization_label}: {self.surname} {self.first_name} {self.last_name}"
        )

    class Meta:
        verbose_name = "Врач"
        verbose_name_plural = "Врачи"


class MedicalService(models.Model):
    """Модель для хранения медицинских услуг, прайса и кодов."""

    # Базовые поля
    name = models.CharField(max_length=255, verbose_name="Название услуги")
    code = models.CharField(max_length=20, verbose_name="Код услуги")
    price = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name="Цена услуги"
    )
    category = models.CharField(
        max_length=20,
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
