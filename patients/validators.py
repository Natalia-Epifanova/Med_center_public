from django.core.exceptions import ValidationError


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
