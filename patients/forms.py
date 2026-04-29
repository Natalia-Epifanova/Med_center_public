from django import forms
from django.core.exceptions import ValidationError
from django.db import models
from django.forms import ModelForm
from django.utils import timezone
import re

from patients.models import Patient, ReservePatient, WaitlistPatient
from timetable.mixins import StyleFormMixin
from timetable.models import Doctor


class BasePatientForm(StyleFormMixin, ModelForm):
    """Базовая форма для пациента с общей логикой"""

    SNILS_DIGITS_LENGTH = 11
    SNILS_FORMATTED_LENGTH = 14
    OMS_POLICY_LENGTH = 16

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

        polis_oms = (cleaned_data.get("polis_oms") or "").strip()
        if polis_oms:
            polis_oms_digits = "".join(char for char in polis_oms if char.isdigit())
            if len(polis_oms_digits) != self.OMS_POLICY_LENGTH:
                self.add_error(
                    "polis_oms",
                    f"Полис ОМС должен содержать {self.OMS_POLICY_LENGTH} цифр",
                )
            else:
                cleaned_data["polis_oms"] = polis_oms_digits

        snils = (cleaned_data.get("snils") or "").strip()
        if snils:
            snils_digits = "".join(char for char in snils if char.isdigit())
            if len(snils_digits) != self.SNILS_DIGITS_LENGTH:
                self.add_error(
                    "snils",
                    f"СНИЛС должен содержать {self.SNILS_DIGITS_LENGTH} цифр",
                )
            elif not re.fullmatch(r"\d{3}-\d{3}-\d{3} \d{2}", snils):
                self.add_error(
                    "snils",
                    "СНИЛС должен быть в формате XXX-XXX-XXX YY",
                )
            else:
                cleaned_data["snils"] = (
                    f"{snils_digits[:3]}-{snils_digits[3:6]}-"
                    f"{snils_digits[6:9]} {snils_digits[9:]}"
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
            "email",
            "trusted_person",
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
            "email": "Email",
            "trusted_person": "Доверенное лицо",
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

        self.fields["polis_oms"].widget.attrs.update(
            {
                "maxlength": str(self.OMS_POLICY_LENGTH),
                "inputmode": "numeric",
                "placeholder": "16 цифр",
            }
        )
        self.fields["snils"].widget.attrs.update(
            {
                "maxlength": str(self.SNILS_FORMATTED_LENGTH),
                "placeholder": "XXX-XXX-XXX YY",
            }
        )


class PatientBlacklistForm(StyleFormMixin, ModelForm):
    """Форма для добавления пациента в черный список и снятия с него"""

    class Meta:
        model = Patient
        fields = ["is_blacklisted", "blacklist_comment"]
        widgets = {
            "is_blacklisted": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
            "blacklist_comment": forms.Textarea(
                attrs={
                    "rows": 4,
                    "class": "form-control",
                    "placeholder": "Укажите причину добавления пациента в черный список...",
                }
            ),
        }
        labels = {
            "is_blacklisted": "Пациент в черном списке",
            "blacklist_comment": "Комментарий для черного списка",
        }

    def clean(self):
        cleaned_data = super().clean()
        is_blacklisted = cleaned_data.get("is_blacklisted")
        blacklist_comment = (cleaned_data.get("blacklist_comment") or "").strip()

        if is_blacklisted and not blacklist_comment:
            self.add_error(
                "blacklist_comment",
                "Укажите причину добавления пациента в черный список",
            )

        if not is_blacklisted:
            cleaned_data["blacklist_comment"] = ""

        return cleaned_data


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
            "date_of_birth": "Дата рождения",
            "comment": "Комментарий",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Помечаем обязательные поля
        self.fields["surname"].required = True
        self.fields["first_name"].required = True
        self.fields["phone_number"].required = True
        self.fields["date_of_birth"].required = False

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
    """Форма ТОЛЬКО для редактирования комментария в резервной записи"""

    class Meta:
        model = ReservePatient
        fields = ["comment"]  # ТОЛЬКО комментарий!

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Делаем все поля READONLY кроме комментария
        self._set_readonly_fields()

    def _set_readonly_fields(self):
        """Делает все поля кроме комментария только для чтения"""
        for field_name in [
            "surname",
            "first_name",
            "last_name",
            "phone_number",
            "date_of_birth",
        ]:
            if field_name in self.fields:
                self.fields[field_name].widget.attrs["readonly"] = True
                self.fields[field_name].widget.attrs[
                    "class"
                ] = "form-control-plaintext bg-light"
                self.fields[field_name].required = False

    def clean(self):
        """Очистка данных - игнорируем readonly поля"""
        cleaned_data = super().clean()
        # Возвращаем только комментарий и ID
        return {"comment": cleaned_data.get("comment", "")}


# patients/forms.py (добавить к существующим формам)


# patients/forms.py - исправленная форма
class WaitlistPatientForm(StyleFormMixin, ModelForm):
    """Форма для добавления пациента в лист ожидания"""

    class Meta:
        model = WaitlistPatient
        fields = [
            "doctor",
            "surname",
            "first_name",
            "last_name",
            "phone_number",
            "date_of_birth",
            "comment",
            # УБИРАЕМ СТАТУС
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
                    "rows": 3,
                    "class": "form-control",
                    "placeholder": "Комментарий для администратора...",
                }
            ),
            "doctor": forms.Select(attrs={"class": "form-select"}),
        }
        labels = {
            "doctor": "Врач *",
            "surname": "Фамилия *",
            "first_name": "Имя *",
            "last_name": "Отчество",
            "phone_number": "Телефон *",
            "date_of_birth": "Дата рождения",
            "comment": "Комментарий",
            # УБИРАЕМ СТАТУС
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Помечаем обязательные поля
        self.fields["doctor"].required = True
        self.fields["surname"].required = True
        self.fields["first_name"].required = True
        self.fields["phone_number"].required = True

        # Добавляем классы ко всем полям
        for field_name in self.fields:
            if field_name not in ["comment"]:  # Убираем статус
                if "class" not in self.fields[field_name].widget.attrs:
                    self.fields[field_name].widget.attrs["class"] = "form-control"

        # УБИРАЕМ НАСТРОЙКУ СТАТУСА

        # Для врача устанавливаем queryset
        if "doctor" in self.fields:
            self.fields["doctor"].queryset = Doctor.objects.all().order_by(
                "surname", "first_name"
            )

        # ФОРМАТИРУЕМ ДАТУ ДЛЯ HTML5 INPUT
        if self.instance and self.instance.date_of_birth:
            # Конвертируем дату в формат YYYY-MM-DD для HTML5 input type="date"
            self.initial["date_of_birth"] = self.instance.date_of_birth.strftime(
                "%Y-%m-%d"
            )

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

    def clean(self):
        """Общая валидация формы"""
        cleaned_data = super().clean()

        # Проверяем, не является ли пациент уже в листе ожидания
        surname = cleaned_data.get("surname")
        first_name = cleaned_data.get("first_name")
        phone_number = cleaned_data.get("phone_number")
        doctor = cleaned_data.get("doctor")

        if all([surname, first_name, phone_number, doctor]):
            query = WaitlistPatient.objects.filter(
                surname__iexact=surname,
                first_name__iexact=first_name,
                phone_number=phone_number,
                doctor=doctor,
            )

            if self.instance and self.instance.pk:
                query = query.exclude(pk=self.instance.pk)

            if query.exists():
                self.add_error(
                    "__all__",
                    "Этот пациент уже находится в листе ожидания у выбранного врача",
                )

        return cleaned_data
