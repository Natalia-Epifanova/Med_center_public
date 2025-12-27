from django.core.exceptions import ValidationError

from timetable.models import MedicalService


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
