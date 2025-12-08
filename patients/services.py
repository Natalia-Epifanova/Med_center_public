from django.db import transaction

from patients.models import Patient
from patients.validators import PatientValidator


class PatientService:
    """Сервис для работы с пациентами"""

    @staticmethod
    @transaction.atomic
    def get_or_create_patient(patient_data):
        """Создание или поиск пациента"""
        surname = patient_data.get("surname")
        first_name = patient_data.get("first_name")
        date_of_birth = patient_data.get("date_of_birth")

        # Валидация обязательных полей
        PatientValidator.validate_patient_required_fields(surname, first_name)

        # Поиск существующего пациента
        if surname and first_name and date_of_birth:
            existing_patient = Patient.objects.filter(
                surname__iexact=surname,
                first_name__iexact=first_name,
                date_of_birth=date_of_birth,
            ).first()

            if existing_patient:
                return existing_patient, False

        # Создание нового пациента
        patient = Patient.objects.create(**patient_data)
        return patient, True

    @staticmethod
    def clean_patient_data(patient_data):
        """Очистка и валидация данных пациента"""
        cleaned_data = patient_data.copy()

        # Валидация телефона
        if cleaned_data.get("phone_number"):
            cleaned_data["phone_number"] = PatientValidator.validate_phone_number(
                cleaned_data["phone_number"]
            )

        return cleaned_data
