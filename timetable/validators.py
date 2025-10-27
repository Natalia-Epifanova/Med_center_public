from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.db.models import Q
from .models import TimeSlot, Appointment
from patients.models import Patient


class PatientValidator:
    """Валидатор данных пациента"""

    @staticmethod
    def validate_phone_number(phone_number):
        """Валидация номера телефона"""
        if not phone_number:
            return phone_number

        cleaned_phone = phone_number.replace(" ", "").replace("-", "")

        if not cleaned_phone.startswith("+7"):
            raise ValidationError("Номер телефона должен начинаться с +7")

        if len(cleaned_phone) != 12:
            raise ValidationError("Номер телефона должен содержать 12 символов")

        if not cleaned_phone[1:].isdigit():
            raise ValidationError("После +7 должны быть только цифры")

        return cleaned_phone

    @staticmethod
    def validate_patient_required_fields(surname, first_name):
        """Валидация обязательных полей пациента"""
        if not surname or not first_name:
            raise ValidationError("Фамилия и имя пациента обязательны для заполнения")


class AppointmentValidator:
    """Валидатор записей на прием"""

    @staticmethod
    def validate_consecutive_slot(time_slot, current_time_slot=None):
        """Валидация доступности следующего слота"""
        next_slot = time_slot.get_next_consecutive_slot()

        if not next_slot:
            raise ValidationError(
                "Следующий временной слот недоступен для последовательной записи"
            )

        if not next_slot.is_available() and next_slot != current_time_slot:
            raise ValidationError("Следующий временной слот уже занят другим пациентом")

        return next_slot

    @staticmethod
    def validate_additional_service(appointment_type, additional_service):
        """Валидация дополнительной услуги"""
        if appointment_type == "additional" and not additional_service:
            raise ValidationError(
                'При выборе опции "Добавить вторую услугу" необходимо указать вторую услугу'
            )


class TimeSlotValidator:
    """Валидатор временных слотов"""

    @staticmethod
    def validate_single_slot(start_time, end_time):
        """Валидация одиночного слота"""
        if not start_time or not end_time:
            raise ValidationError(
                "Для одиночного слота необходимо указать время начала и окончания"
            )

        if start_time >= end_time:
            raise ValidationError("Время начала должно быть раньше времени окончания")

    @staticmethod
    def validate_multiple_slots(start_time, end_time, interval):
        """Валидация множественных слотов"""
        if not start_time or not end_time:
            raise ValidationError(
                "Для нескольких слотов необходимо указать время начала и окончания"
            )

        if start_time >= end_time:
            raise ValidationError("Время начала должно быть раньше времени окончания")

        if not interval or interval <= 0:
            raise ValidationError("Интервал должен быть положительным числом")
