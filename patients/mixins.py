from django import forms
from django.contrib import messages
from django.contrib.auth.mixins import UserPassesTestMixin
from django.shortcuts import redirect


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
