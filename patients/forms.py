from django import forms
from django.core.exceptions import ValidationError
from django.db import models
from django.forms import ModelForm
from django.utils import timezone

from patients.models import Patient, ReservePatient
from timetable.mixins import StyleFormMixin


class BasePatientForm(StyleFormMixin, ModelForm):
    """Базовая форма для пациента с общей логикой"""

    def clean(self):
        """Общая валидация для всех форм пациента"""
        cleaned_data = super().clean()

        # Валидация даты рождения (не может быть в будущем)
        date_of_birth = cleaned_data.get("date_of_birth")
        if date_of_birth and date_of_birth > timezone.now().date():
            self.add_error("date_of_birth", "Дата рождения не может быть в будущем")

        # Валидация паспортных данных
        passport_series = cleaned_data.get("passport_series")
        passport_number = cleaned_data.get("passport_number")

        if passport_series or passport_number:
            # Если указана серия, должен быть номер и наоборот
            if passport_series and not passport_number:
                self.add_error(
                    "passport_number", "Укажите номер паспорта при указании серии"
                )
            if passport_number and not passport_series:
                self.add_error(
                    "passport_series", "Укажите серию паспорта при указании номера"
                )

        return cleaned_data


class PatientForm(BasePatientForm):
    """Форма для быстрого создания/редактирования пациента при записи"""

    class Meta:
        model = Patient
        fields = [
            "surname",
            "first_name",
            "last_name",
            "phone_number",
            "card_number",
            "date_of_birth",
        ]
        widgets = {
            "date_of_birth": forms.DateInput(
                attrs={"type": "date", "class": "datepicker"}
            ),
            "phone_number": forms.TextInput(
                attrs={"placeholder": "+7 (___) ___-__-__", "class": "phone-input"}
            ),
        }
        labels = {
            "surname": "Фамилия",
            "first_name": "Имя",
            "last_name": "Отчество",
            "phone_number": "Телефон",
            "card_number": "Номер карты",
            "date_of_birth": "Дата рождения",
        }
        help_texts = {
            "phone_number": "Формат: +7XXXXXXXXXX",
            "card_number": "Основной номер карты пациента",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Помечаем обязательные поля
        self.fields["surname"].required = True
        self.fields["first_name"].required = True


class PatientFullForm(BasePatientForm):
    """Форма для полного редактирования пациента (все поля)"""

    class Meta:
        model = Patient
        fields = [
            # Личные данные
            "surname",
            "first_name",
            "last_name",
            "date_of_birth",
            "gender",
            # Контактные данные
            "phone_number",
            # Номера карт
            "card_number",
            "card_number_IP",
            "card_number_OMS",
            # Адрес
            "area",
            "locality",
            "city",
            "district",
            "street",
            "home",
            "building",
            "apartment",
            # Паспортные данные
            "passport_series",
            "passport_number",
            "passport_issue_date",
            "who_issued_the_passport",
            # Страхование
            "polis_oms",
            "snils",
            "insurance_company",
        ]
        widgets = {
            "date_of_birth": forms.DateInput(
                attrs={
                    "type": "date",
                    "class": "form-control date-input",
                }
            ),
            "passport_issue_date": forms.DateInput(
                attrs={
                    "type": "date",
                    "class": "form-control date-input",
                }
            ),
            "phone_number": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "+7 (___) ___-__-__"}
            ),
        }

        labels = {
            # Личные данные
            "surname": "Фамилия",
            "first_name": "Имя",
            "last_name": "Отчество",
            "date_of_birth": "Дата рождения",
            "gender": "Пол",
            # Контактные данные
            "phone_number": "Телефон",
            # Номера карт
            "card_number": "Номер карты",
            "card_number_IP": "Номер карты (ИП)",
            "card_number_OMS": "Номер карты (ОМС)",
            # Адрес
            "area": "Субъект РФ",
            "locality": "Населенный пункт",
            "city": "Город",
            "district": "Район",
            "street": "Улица",
            "home": "Дом",
            "building": "Строение/корпус",
            "apartment": "Квартира",
            # Паспортные данные
            "passport_series": "Серия паспорта",
            "passport_number": "Номер паспорта",
            "passport_issue_date": "Дата выдачи паспорта",
            "who_issued_the_passport": "Кем выдан",
            # Страхование
            "polis_oms": "Полис ОМС",
            "snils": "СНИЛС",
            "insurance_company": "Страховая компания",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Форматируем даты для HTML5 input type="date"
        if self.instance and self.instance.date_of_birth:
            # Конвертируем дату в формат YYYY-MM-DD для HTML5 input
            self.initial["date_of_birth"] = self.instance.date_of_birth.strftime(
                "%Y-%m-%d"
            )

        if self.instance and self.instance.passport_issue_date:
            self.initial["passport_issue_date"] = (
                self.instance.passport_issue_date.strftime("%Y-%m-%d")
            )


class PatientSearchForm(forms.Form):
    """Форма для поиска пациентов"""

    search = forms.CharField(
        required=False,
        label="Поиск пациента",
        widget=forms.TextInput(
            attrs={
                "placeholder": "ФИО, телефон или номер карты...",
                "class": "form-control",
                "autocomplete": "off",
            }
        ),
    )

    def clean_search(self):
        """Очистка поискового запроса"""
        search = self.cleaned_data.get("search", "").strip()
        if len(search) < 2 and search:
            raise ValidationError("Введите хотя бы 2 символа для поиска")
        return search


class BaseReserveForm(StyleFormMixin, ModelForm):
    """Базовая форма для резервных записей"""

    def clean_date_of_birth(self):
        """Валидация даты рождения"""
        date_of_birth = self.cleaned_data.get("date_of_birth")
        if date_of_birth and date_of_birth > timezone.now().date():
            raise ValidationError("Дата рождения не может быть в будущем")
        return date_of_birth


class ReservePatientCreateForm(BaseReserveForm):
    """Форма для создания записи в резерве с улучшенной функциональностью"""

    class Meta:
        model = ReservePatient
        fields = [
            "surname",
            "first_name",
            "last_name",
            "phone_number",
            "date_of_birth",
            "comment",
        ]
        widgets = {
            "date_of_birth": forms.DateInput(
                attrs={"type": "date", "class": "form-control"}
            ),
            "phone_number": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "+7 (___) ___-__-__",
                    "id": "id_phone_number",
                }
            ),
            "comment": forms.Textarea(
                attrs={
                    "rows": 2,
                    "class": "form-control",
                    "placeholder": "Комментарий для администратора...",
                }
            ),
        }
        labels = {
            "surname": "Фамилия *",
            "first_name": "Имя *",
            "last_name": "Отчество",
            "phone_number": "Телефон *",
            "date_of_birth": "Дата рождения *",
            "comment": "Комментарий",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Помечаем обязательные поля
        self.fields["surname"].required = True
        self.fields["first_name"].required = True
        self.fields["phone_number"].required = True
        self.fields["date_of_birth"].required = True

        # Добавляем CSS классы
        for field_name in ["surname", "first_name", "last_name", "phone_number"]:
            self.fields[field_name].widget.attrs["class"] = "form-control"

    def clean_phone_number(self):
        """Валидация и форматирование номера телефона"""
        phone = self.cleaned_data.get("phone_number", "").strip()

        if not phone:
            raise ValidationError("Это поле обязательно для заполнения")

        # Удаляем все нецифровые символы кроме +
        phone_clean = "".join(c for c in phone if c.isdigit() or c == "+")

        # Форматируем номер
        if phone_clean.startswith("8"):
            phone_clean = "+7" + phone_clean[1:]
        elif phone_clean.startswith("7"):
            phone_clean = "+" + phone_clean
        elif phone_clean.startswith("9") and len(phone_clean) == 10:
            phone_clean = "+7" + phone_clean

        # Проверяем формат +7XXXXXXXXXX
        if not phone_clean.startswith("+7"):
            raise ValidationError("Номер должен начинаться с +7")

        if len(phone_clean) != 12:
            raise ValidationError("Номер должен содержать 12 символов (включая +7)")

        return phone_clean


class ReservePatientUpdateForm(BaseReserveForm):
    """Форма для редактирования записи в резерве"""

    class Meta:
        model = ReservePatient
        fields = [
            "surname",
            "first_name",
            "last_name",
            "phone_number",
            "date_of_birth",
            "comment",
        ]
        widgets = {
            "date_of_birth": forms.DateInput(
                attrs={"type": "date", "class": "datepicker"}
            ),
            "phone_number": forms.TextInput(
                attrs={"placeholder": "+7 (___) ___-__-__", "class": "phone-input"}
            ),
            "comment": forms.Textarea(attrs={"rows": 2}),
        }
