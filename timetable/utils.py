from datetime import datetime, timedelta
from django.db import transaction
from django import forms
from .models import TimeSlot, MedicalService, MedicalServiceCategory


def create_time_slots(
    date,
    cabinet,
    doctor,
    start_time,
    end_time,
    interval,
    slot_type="working",
    description="",
):
    """Утилита для создания временных слотов"""
    created_slots = []
    current_time = start_time

    while current_time < end_time:
        end_time_slot = (
            datetime.combine(date, current_time) + timedelta(minutes=interval)
        ).time()
        if end_time_slot > end_time:
            break

        slot = TimeSlot(
            date=date,
            cabinet=cabinet,
            doctor=doctor,
            start_time=current_time,
            end_time=end_time_slot,
            slot_type=slot_type,
            description=description,
        )
        created_slots.append(slot)
        current_time = end_time_slot

    return created_slots


def save_slots_with_conflict_check(slots):
    """Сохранение слотов с проверкой конфликтов"""
    saved_count = 0
    for slot in slots:
        conflicting_slots = TimeSlot.objects.filter(
            date=slot.date,
            cabinet=slot.cabinet,
            start_time__lt=slot.end_time,
            end_time__gt=slot.start_time,
        )
        if not conflicting_slots.exists():
            slot.save()
            saved_count += 1
    return saved_count


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
    insoles_keywords = ["стель", "стелек", "manufacture_of_insoles"]
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
                f"на 20-минутные интервалы принимает ТОЛЬКО на изготовление стелек. "
                f"Выберите услугу 'Изготовление стелек' или выберите 30-минутный интервал."
            )
            raise forms.ValidationError(error_msg)


def get_doctor_services(doctor, include_current_service=None):
    """Получает услуги, доступные для врача"""
    from django.db.models import Q

    if not doctor:
        return MedicalService.objects.filter(is_active=True)

    # Получаем категории услуг, которые оказывает врач
    provided_categories = doctor.provided_services

    # Получаем исключенные услуги
    excluded_service_ids = doctor.excluded_services.values_list("id", flat=True)

    # Фильтруем услуги по категориям врача и исключаем недоступные
    services_queryset = MedicalService.objects.filter(
        category__in=provided_categories, is_active=True
    ).exclude(id__in=excluded_service_ids)

    # Включаем текущую услугу если указана
    if include_current_service:
        services_queryset = (
            MedicalService.objects.filter(
                Q(id=include_current_service.id)
                | Q(category__in=provided_categories, is_active=True)
            )
            .exclude(Q(id__in=excluded_service_ids) & ~Q(id=include_current_service.id))
            .distinct()
        )

    return services_queryset
