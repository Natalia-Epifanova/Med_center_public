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
            "polis_oms",
            "snils",
            "insurance_company",
        ]
        widgets = {
            "date_of_birth": forms.DateInput(attrs={"type": "date"}),
            "address": forms.Textarea(attrs={"rows": 3}),
        }
        labels = {
            "surname": "Фамилия*",
            "first_name": "Имя*",
            "last_name": "Отчество",
            "phone_number": "Телефон",
            "card_number": "Номер карты",
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
            "polis_oms": "Полис ОМС",
            "snils": "СНИЛС",
            "insurance_company": "Страховая компания",
        }
