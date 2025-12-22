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

    @staticmethod
    def validate_additional_service(appointment_type, additional_service):
        """Валидация дополнительной услуги"""
        if appointment_type == "additional" and not additional_service:
            raise ValidationError(
                'При выборе опции "Добавить вторую услугу" необходимо указать вторую услугу'
            )

    @staticmethod
    def validate_pishchelev_for_all_services(doctor, services, time_slots):
        """
        Валидация ограничений Пищелева для всех услуг в цепочке
        services: список объектов MedicalService или их ID
        time_slots: список объектов TimeSlot
        """
        if not doctor or not str(doctor).lower().find("пищелев") != -1:
            return

        for i, (service, time_slot) in enumerate(zip(services, time_slots)):
            if not service or not time_slot:
                continue

            # Получаем объект услуги если передан ID
            if isinstance(service, (int, str)):
                try:
                    service_obj = MedicalService.objects.get(id=service)
                except MedicalService.DoesNotExist:
                    continue
            else:
                service_obj = service

            # Проверяем ограничения
            from timetable.utils import validate_pishchelev_restrictions

            try:
                validate_pishchelev_restrictions(doctor, service_obj, time_slot)
            except ValidationError as e:
                raise ValidationError(
                    f"Ошибка для записи #{i + 1} (услуга: {service_obj.name}): {str(e)}"
                )
