from django.core.exceptions import ValidationError


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
