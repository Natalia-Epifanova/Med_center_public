from django import forms
from django.forms import ModelForm

from patients.models import Patient
from timetable.mixins import StyleFormMixin


class PatientForm(StyleFormMixin, ModelForm):
    """Форма для создания/редактирования пациента при записи"""

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
            "date_of_birth": forms.DateInput(attrs={"type": "date"}),
        }
        labels = {
            "surname": "Фамилия",
            "first_name": "Имя",
            "last_name": "Отчество",
            "phone_number": "Телефон",
            "card_number": "Номер карты",
            "date_of_birth": "Дата рождения",
        }


class PatientFullForm(StyleFormMixin, ModelForm):
    """Форма для полного редактирования пациента (все поля)"""

    class Meta:
        model = Patient
        fields = [
            "surname",
            "first_name",
            "last_name",
            "phone_number",
            "card_number",
            "card_number_IP",
            "date_of_birth",
            "gender",
            "area",
            "locality",
            "city",
            "district",
            "street",
            "home",
            "building",
            "apartment",
            "passport_series",
            "passport_number",
            "passport_issue_date",
            "who_issued_the_passport",
            "polis_oms",
            "snils",
            "insurance_company",
        ]
        widgets = {
            "date_of_birth": forms.DateInput(attrs={"type": "date"}),
            "passport_issue_date": forms.DateInput(attrs={"type": "date"}),
        }
        labels = {
            "surname": "Фамилия*",
            "first_name": "Имя*",
            "last_name": "Отчество",
            "phone_number": "Телефон",
            "card_number": "Номер карты",
            "card_number_IP": "Номер карты (ИП)",
            "date_of_birth": "Дата рождения",
            "gender": "Пол",
            "area": "Субъект РФ",
            "locality": "Населенный пункт",
            "city": "Город",
            "district": "Район",
            "street": "Улица",
            "home": "Дом",
            "building": "Строение/корпус",
            "apartment": "Квартира",
            "passport_series": "Паспор серия",
            "passport_number": "Паспорт номер",
            "passport_issue_date": "Дата выдачи паспорта",
            "who_issued_the_passport": "Кем выдан",
            "polis_oms": "Полис ОМС",
            "snils": "СНИЛС",
            "insurance_company": "Страховая компания",
        }
