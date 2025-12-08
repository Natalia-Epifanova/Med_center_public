from django.core.exceptions import ValidationError


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
