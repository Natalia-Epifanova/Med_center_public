from datetime import datetime

from django import forms

from timetable.models import MedicalServiceCategory


def is_doctor_pishchelev(doctor):
    """Проверяет, является ли врач Пищелевым П.В."""
    if not doctor:
        return False

    # Более гибкая проверка
    is_pishchelev = (
        doctor.surname.lower() == "пищелёв"
        and doctor.first_name.startswith("П")
        and doctor.last_name.startswith("В")
    )

    return is_pishchelev


def get_slot_duration_minutes(time_slot):
    """Вычисляет длительность слота в минутах"""
    if isinstance(time_slot.start_time, str):
        start = datetime.strptime(time_slot.start_time, "%H:%M:%S").time()
    else:
        start = time_slot.start_time

    if isinstance(time_slot.end_time, str):
        end = datetime.strptime(time_slot.end_time, "%H:%M:%S").time()
    else:
        end = time_slot.end_time

    start_minutes = start.hour * 60 + start.minute
    end_minutes = end.hour * 60 + end.minute

    return end_minutes - start_minutes


def is_insoles_service(service):
    """Проверяет, является ли услуга изготовлением стелек"""
    # Проверяем по категории
    if service.category == MedicalServiceCategory.MANUFACTURE_OF_INSOLES:
        return True

    # Дополнительная проверка по названию
    insoles_keywords = ["плантон", "плантонграфия", "manufacture_of_insoles"]
    service_name_lower = service.name.lower()

    return any(keyword in service_name_lower for keyword in insoles_keywords)


def validate_pishchelev_restrictions(doctor, service, time_slot):
    """Валидация ограничений для врача Пищелева П.В."""

    if is_doctor_pishchelev(doctor):
        slot_duration = get_slot_duration_minutes(time_slot)

        # Для 20-минутных слотов разрешены только услуги изготовления стелек
        if slot_duration == 20 and not is_insoles_service(service):
            error_msg = (
                f"Врач {doctor.surname} {doctor.first_name[0]}.{doctor.last_name[0]}. "
                f"на 20-минутные интервалы принимает ТОЛЬКО на плантонграфию. "
                f"Выберите услугу 'Плантонграфия' или выберите 30-минутный интервал."
            )
            raise forms.ValidationError(error_msg)
