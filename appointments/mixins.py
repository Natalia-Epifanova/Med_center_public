# patients/mixins.py
import json

from django import forms

from appointments.constants import APPOINTMENT_CHAIN_CHOICES


class PatientFieldsMixin:
    """Миксин добавляет поля пациента к форме"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._add_patient_fields()

    def _add_patient_fields(self):
        """Добавление полей пациента с русскими метками"""
        self.fields.update(
            {
                "surname": forms.CharField(
                    max_length=50,
                    label="Фамилия*",
                    widget=forms.TextInput(attrs={"placeholder": "Введите фамилию"}),
                ),
                "first_name": forms.CharField(
                    max_length=20,
                    label="Имя*",
                    widget=forms.TextInput(attrs={"placeholder": "Введите имя"}),
                ),
                "last_name": forms.CharField(
                    max_length=30,
                    required=False,
                    label="Отчество",
                    widget=forms.TextInput(attrs={"placeholder": "Введите отчество"}),
                ),
                "phone_number": forms.CharField(
                    max_length=12,
                    required=False,
                    label="Телефон",
                    widget=forms.TextInput(
                        attrs={
                            "placeholder": "+79501234567",
                            "pattern": "^\\+7\\d{10}$",
                            "title": "Формат: +7XXXXXXXXXX (12 символов)",
                        }
                    ),
                ),
                "card_number": forms.IntegerField(
                    required=False,
                    label="Номер карты",
                    widget=forms.NumberInput(
                        attrs={"placeholder": "Номер карты пациента"}
                    ),
                ),
                "date_of_birth": forms.DateField(
                    required=False,
                    label="Дата рождения",
                    widget=forms.DateInput(attrs={"type": "date"}),
                ),
            }
        )

    # ДОБАВЛЯЕМ НОВЫЙ МЕТОД
    def get_patient_data(self):
        """Извлекает данные пациента из формы"""
        if hasattr(self, "cleaned_data"):
            data_source = self.cleaned_data
        else:
            data_source = self.data if hasattr(self, "data") else {}

        return {
            "surname": data_source.get("surname", "").strip(),
            "first_name": data_source.get("first_name", "").strip(),
            "last_name": data_source.get("last_name", "").strip(),
            "phone_number": data_source.get("phone_number", "").strip(),
            "card_number": data_source.get("card_number"),
            "date_of_birth": data_source.get("date_of_birth"),
        }


class AppointmentFormMixin:
    """Миксин с общими методами для форм записей"""

    APPOINTMENT_CHOICES = APPOINTMENT_CHAIN_CHOICES

    def get_appointment_type_display(self, value):
        """Получить отображаемое название типа записи"""
        choices_dict = dict(self.APPOINTMENT_CHOICES)
        return choices_dict.get(value, value)
