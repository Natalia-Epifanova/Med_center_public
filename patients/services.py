from typing import Any, Dict, Optional, Tuple

from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Max
from phonenumber_field.phonenumber import PhoneNumber

from patients.models import Patient


class PatientService:
    """Сервис для работы с пациентами с поддержкой PhoneNumberField"""

    @staticmethod
    @transaction.atomic
    def get_or_create_patient(patient_data: Dict[str, Any]) -> Tuple[Patient, bool]:
        """Создание или поиск пациента"""
        # Очистка данных
        cleaned_data = PatientService.clean_patient_data(patient_data)

        surname = cleaned_data.get("surname")
        first_name = cleaned_data.get("first_name")
        date_of_birth = cleaned_data.get("date_of_birth")
        last_name = cleaned_data.get("last_name", "")

        # Валидация обязательных полей
        if not surname or not first_name:
            raise ValidationError("Фамилия и имя обязательны")

        # Поиск существующего пациента
        query = Patient.objects.filter(
            surname__iexact=surname,
            first_name__iexact=first_name,
        )

        if last_name:
            query = query.filter(last_name__iexact=last_name)
        else:
            query = query.filter(
                models.Q(last_name="") | models.Q(last_name__isnull=True)
            )

        if date_of_birth:
            query = query.filter(date_of_birth=date_of_birth)

        existing_patient = query.first()

        if existing_patient:
            return existing_patient, False

        # Создание нового пациента
        patient = Patient.objects.create(**cleaned_data)
        return patient, True

    @staticmethod
    def clean_patient_data(patient_data: Dict[str, Any]) -> Dict[str, Any]:
        """Очистка данных пациента для новой модели"""
        cleaned_data = patient_data.copy()

        # Обработка телефона (поддержка PhoneNumberField)
        phone = cleaned_data.get("phone_number")
        if phone:
            if isinstance(phone, str):
                # Очистка строки телефона
                phone_clean = "".join(c for c in phone if c.isdigit() or c == "+")
                if phone_clean and not phone_clean.startswith("+"):
                    if phone_clean.startswith("8"):
                        phone_clean = "+7" + phone_clean[1:]
                    elif phone_clean.startswith("7"):
                        phone_clean = "+" + phone_clean
                    else:
                        phone_clean = "+7" + phone_clean
                cleaned_data["phone_number"] = phone_clean

        # Конвертация пустых строк в None для числовых полей
        numeric_fields = ["card_number", "card_number_IP", "card_number_OMS"]
        for field in numeric_fields:
            if field in cleaned_data and cleaned_data[field] == "":
                cleaned_data[field] = None

        # Конвертация пустых строк в пустые строки (не None) для текстовых полей
        text_fields = [
            "last_name",
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
            "who_issued_the_passport",
            "polis_oms",
            "snils",
            "insurance_company",
        ]

        for field in text_fields:
            if field in cleaned_data:
                if cleaned_data[field] is None:
                    cleaned_data[field] = ""
                else:
                    cleaned_data[field] = str(cleaned_data[field]).strip()

        return cleaned_data


class CardNumberService:
    """Сервис для работы с номерами карт пациентов"""

    @staticmethod
    def get_max_card_number():
        """Получить максимальный номер карты"""
        max_number = Patient.objects.aggregate(max_card_number=Max("card_number"))[
            "max_card_number"
        ]

        return max_number or 0

    @staticmethod
    def get_next_card_number():
        """Получить следующий доступный номер карты"""
        max_number = CardNumberService.get_max_card_number()

        # Если нет ни одного номера, начинаем с 1
        if max_number is None:
            return 1

        # Находим следующий свободный номер
        next_number = max_number + 1

        # Проверяем, не занят ли этот номер (на всякий случай)
        # и ищем следующий свободный
        while Patient.objects.filter(card_number=next_number).exists():
            next_number += 1

        return next_number
