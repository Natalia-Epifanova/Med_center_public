# appointments/utils_for_caches.py
from django.core.cache import cache
from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.db.models import Prefetch, Q

from appointments.constants import CACHE_KEYS, CACHE_TIMEOUTS, PROCEDURAL_CABINET_NUMBER
from timetable.models import (
    BloodTest,
    BloodTestCategory,
    Cabinet,
    Doctor,
    MedicalService,
    TimeSlot,
)


# 1. Функции для процедурного кабинета (уже есть)
def get_procedural_cabinet():
    """
    Получить объект процедурного кабинета с кэшированием.
    Кабинет редко меняется, поэтому кэшируем на долгое время.
    """
    cache_key = CACHE_KEYS["PROCEDURAL_CABINET"]
    procedural_cabinet = cache.get(cache_key)

    if not procedural_cabinet:
        try:
            procedural_cabinet = Cabinet.objects.get(number=PROCEDURAL_CABINET_NUMBER)
            cache.set(
                cache_key, procedural_cabinet, CACHE_TIMEOUTS["PROCEDURAL_CABINET"]
            )
        except Cabinet.DoesNotExist:
            raise ObjectDoesNotExist(
                f"Процедурный кабинет с номером {PROCEDURAL_CABINET_NUMBER} не найден. "
                "Пожалуйста, проверьте настройки базы данных."
            )

    return procedural_cabinet


def clear_procedural_cabinet_cache():
    """Очистить кэш процедурного кабинета (вызывать при изменении кабинета)"""
    cache_key = CACHE_KEYS["PROCEDURAL_CABINET"]
    cache.delete(cache_key)


def is_procedural_cabinet(cabinet):
    """Проверить, является ли кабинет процедурным"""
    return cabinet.number == PROCEDURAL_CABINET_NUMBER


# 2. Функции для кэширования услуг врача
def get_cached_doctor_services(doctor, include_current_service=None):
    """
    Получить QuerySet услуг врача с кэшированием В АЛФАВИТНОМ ПОРЯДКЕ.
    """
    if not doctor:
        return MedicalService.objects.filter(is_active=True).order_by("name")

    # Ключ кэша
    if include_current_service:
        cache_key = (
            CACHE_KEYS["DOCTOR_SERVICES"].format(doctor_id=doctor.id)
            + f"_with_current_{include_current_service.id}"
        )
    else:
        cache_key = CACHE_KEYS["DOCTOR_SERVICES"].format(doctor_id=doctor.id)

    service_ids = cache.get(cache_key)

    if service_ids is None:
        provided_categories = doctor.provided_services
        excluded_service_ids = doctor.excluded_services.values_list("id", flat=True)

        # СОРТИРОВКА В ЗАПРОСЕ
        services_queryset = (
            MedicalService.objects.filter(
                category__in=provided_categories, is_active=True
            )
            .exclude(id__in=excluded_service_ids)
            .order_by("name")  # ← ВАЖНО: сортировка здесь
        )

        if include_current_service:
            services_queryset = (
                MedicalService.objects.filter(
                    Q(id=include_current_service.id)
                    | Q(category__in=provided_categories, is_active=True)
                )
                .exclude(
                    Q(id__in=excluded_service_ids) & ~Q(id=include_current_service.id)
                )
                .distinct()
                .order_by("name")  # ← И здесь тоже
            )

        service_ids = list(services_queryset.values_list("id", flat=True))
        cache.set(cache_key, service_ids, CACHE_TIMEOUTS["DOCTOR_SERVICES"])

    # КРИТИЧЕСКИ ВАЖНО: сохранить порядок из БД
    # Используем Django's Field Lookup для сохранения порядка
    preserved_order = models.Case(
        *[models.When(id=id_val, then=pos) for pos, id_val in enumerate(service_ids)]
    )

    services = MedicalService.objects.filter(
        id__in=service_ids, is_active=True
    ).order_by(
        preserved_order
    )  # ← Сохраняем порядок из кэша

    return services


def get_cached_doctor_services_for_api(doctor):
    """
    Получить услуги врача в формате для API с кэшированием.
    """
    cache_key = CACHE_KEYS["DOCTOR_SERVICES_API"].format(doctor_id=doctor.id)
    services_data = cache.get(cache_key)

    if services_data is None:
        # Получаем QuerySet услуг
        services = get_cached_doctor_services(doctor)

        # Преобразуем в словари для API
        services_data = []
        for service in services:
            services_data.append(
                {
                    "id": service.id,
                    "name": service.name,
                    "price": float(service.price),
                    "category": service.category,
                    "category_display": service.get_category_display(),
                    "description": service.description or "",
                }
            )

        cache.set(cache_key, services_data, CACHE_TIMEOUTS["DOCTOR_SERVICES_API"])

    return services_data


def clear_doctor_services_cache(doctor_id=None, include_current_service_id=None):
    """
    Очистить кэш услуг врача.

    Args:
        doctor_id: ID врача (если None - очистить все)
        include_current_service_id: ID текущей услуги (для составного ключа)
    """
    if doctor_id:
        # Очищаем основной кэш
        cache_key = CACHE_KEYS["DOCTOR_SERVICES"].format(doctor_id=doctor_id)
        cache.delete(cache_key)

        # Очищаем API кэш
        api_key = CACHE_KEYS["DOCTOR_SERVICES_API"].format(doctor_id=doctor_id)
        cache.delete(api_key)

        # Если указана текущая услуга, очищаем составной ключ
        if include_current_service_id:
            composite_key = (
                CACHE_KEYS["DOCTOR_SERVICES"].format(doctor_id=doctor_id)
                + f"_with_current_{include_current_service_id}"
            )
            cache.delete(composite_key)
    else:
        # В реальном приложении лучше использовать версионирование ключей
        # или префикс для массового удаления
        # Пока просто пропускаем массовую очистку
        pass


def get_doctor_services_detailed_for_forms(doctor, current_service=None):
    """
    Получить услуги врача для форм с дополнительной информацией.
    Эта функция используется для инициализации форм.
    """
    services = get_cached_doctor_services(doctor, current_service)

    # Для форм может потребоваться дополнительная информация
    services_list = []
    for service in services:
        services_list.append(
            {
                "id": service.id,
                "name": service.name,
                "price": float(service.price),
                "category": service.category,
                "is_current": current_service and service.id == current_service.id,
            }
        )

    return services_list


# 3. Функция для очистки всех кэшей врача (при изменении данных)
def clear_all_doctor_caches():
    """Очистить все кэши, связанные с врачами"""
    # В реальном приложении нужно использовать паттерн "префикс" или "версия"
    # Для простоты оставляем так
    pass


def get_cached_blood_tests():
    """
    Получить анализы крови с категориями с кэшированием.
    Используется для форм и API.
    """
    cache_key = CACHE_KEYS["BLOOD_TESTS"]
    categories_data = cache.get(cache_key)

    if categories_data is None:
        # Получаем данные из БД
        categories = (
            BloodTestCategory.objects.filter(is_active=True)
            .prefetch_related(
                Prefetch("tests", queryset=BloodTest.objects.all().order_by("name"))
            )
            .order_by("order")
        )

        # Преобразуем в структуру для кэширования
        categories_data = []
        for category in categories:
            tests_data = []
            for test in category.tests.all():
                tests_data.append(
                    {
                        "id": test.id,
                        "code": test.code,
                        "name": test.name,
                        "biomaterial": test.biomaterial,
                        "biomaterial_display": test.get_biomaterial_display(),
                        "price": float(test.price),
                        "execution_time": test.execution_time,
                        "category_id": category.id,
                        "category_name": category.name,
                    }
                )

            categories_data.append(
                {"id": category.id, "name": category.name, "tests": tests_data}
            )

        # Кэшируем на 2 часа
        cache.set(cache_key, categories_data, CACHE_TIMEOUTS["BLOOD_TESTS"])

    return categories_data


def clear_blood_tests_cache():
    """Очистить кэш анализов крови"""
    cache_key = CACHE_KEYS["BLOOD_TESTS"]
    cache.delete(cache_key)


def get_cached_blood_test(test_id):
    """
    Получить конкретный анализ крови по ID.
    Использует общий кэш анализов.
    """
    all_tests_data = get_cached_blood_tests()

    for category in all_tests_data:
        for test in category["tests"]:
            if test["id"] == test_id:
                return test

    return None


def get_cached_active_doctors():
    """
    Получить список активных врачей с кэшированием.
    Возвращает список словарей с основными данными врачей.
    """
    cache_key = CACHE_KEYS["ACTIVE_DOCTORS"]
    doctors_data = cache.get(cache_key)

    if doctors_data is None:
        try:
            # Получаем всех врачей

            doctors = Doctor.objects.all().order_by("surname")

            # Преобразуем в структуру для кэширования
            doctors_data = []
            for doctor in doctors:
                # Получаем русское название специализации
                specialization_display = doctor.get_specialization_display()

                # Формируем полное имя для отображения
                full_name_display = (
                    f"{doctor.surname} {doctor.first_name[0]}.{doctor.last_name[0]}."
                )

                # Формируем строку для отображения в выпадающем списке
                # ТОЧНО ТАК ЖЕ как было раньше в JS:
                display_name = f"{doctor.surname} {doctor.first_name[0]}.{doctor.last_name[0]}. ({specialization_display})"

                doctors_data.append(
                    {
                        "id": doctor.id,
                        "surname": doctor.surname,
                        "first_name": doctor.first_name,
                        "last_name": doctor.last_name,
                        "full_name": full_name_display,
                        "display_name": display_name,  # Ключевое поле для отображения
                        "specialization": doctor.specialization,
                        "specialization_display": specialization_display,
                        "provided_services": (
                            list(doctor.provided_services)
                            if hasattr(doctor, "provided_services")
                            else []
                        ),
                    }
                )

            # Кэшируем на 30 минут
            cache.set(cache_key, doctors_data, CACHE_TIMEOUTS["ACTIVE_DOCTORS"])

            print(f"Cached {len(doctors_data)} doctors")

        except Exception as e:
            print(f"Error in get_cached_active_doctors: {e}")
            doctors_data = []
            cache.set(cache_key, doctors_data, 60)

    return doctors_data


def clear_active_doctors_cache():
    """Очистить кэш списка врачей"""
    cache_key = CACHE_KEYS["ACTIVE_DOCTORS"]
    cache.delete(cache_key)


def get_cached_doctor_by_id(doctor_id):
    """
    Получить данные врача по ID из кэша.
    """
    doctors_data = get_cached_active_doctors()

    for doctor in doctors_data:
        if doctor["id"] == doctor_id:
            return doctor

    return None


def get_cached_doctor_slots(doctor_id, date, exclude_slot_ids=None):
    """
    Получить слоты врача на дату с кэшированием.

    Args:
        doctor_id: ID врача
        date: дата в формате YYYY-MM-DD или datetime.date
        exclude_slot_ids: список ID слотов для исключения

    Returns:
        QuerySet слотов врача
    """
    if exclude_slot_ids is None:
        exclude_slot_ids = []

    # Приводим дату к строке для ключа кэша
    if hasattr(date, "strftime"):
        date_str = date.strftime("%Y-%m-%d")
    else:
        date_str = str(date)

    cache_key = CACHE_KEYS["DOCTOR_SLOTS"].format(doctor_id=doctor_id, date=date_str)

    slot_ids = cache.get(cache_key)

    if slot_ids is None:
        try:
            # Получаем слоты из БД
            from timetable.models import TimeSlot

            slots = TimeSlot.objects.filter(
                doctor_id=doctor_id, date=date_str, slot_type="working"
            ).order_by("start_time")

            # Кэшируем ID слотов
            slot_ids = list(slots.values_list("id", flat=True))
            cache.set(cache_key, slot_ids, CACHE_TIMEOUTS["DOCTOR_SLOTS"])

        except Exception as e:
            print(f"Error getting doctor slots: {e}")
            slot_ids = []
            cache.set(cache_key, slot_ids, 60)  # 1 минута при ошибке

    # Получаем объекты
    from timetable.models import TimeSlot

    slots = TimeSlot.objects.filter(id__in=slot_ids).order_by("start_time")

    # Исключаем слоты если нужно
    if exclude_slot_ids:
        slots = slots.exclude(id__in=exclude_slot_ids)

    return slots


def get_cached_doctor_slots_for_api(doctor_id, date, booked_slots=None):
    """
    Получить слоты врача в формате для API с кэшированием.
    Возвращает только свободные слоты (или текущий слот если он в booked_slots).
    """
    if booked_slots is None:
        booked_slots = []

    # Приводим дату к строке
    if hasattr(date, "strftime"):
        date_str = date.strftime("%Y-%m-%d")
    else:
        date_str = str(date)

    # Ключ кэша теперь включает booked_slots для корректного кэширования
    booked_slots_sorted = sorted(booked_slots)
    cache_key = (
        CACHE_KEYS["DOCTOR_SLOTS_DETAILED"].format(doctor_id=doctor_id, date=date_str)
        + f"_booked_{'_'.join(booked_slots_sorted)}"
    )

    slots_data = cache.get(cache_key)

    if slots_data is None:
        # Получаем ВСЕ слоты врача на дату
        all_slots = TimeSlot.objects.filter(
            doctor_id=doctor_id, date=date_str, slot_type="working"
        ).order_by("start_time")

        # Преобразуем в словари и проверяем доступность
        slots_data = []
        for slot in all_slots:
            slot_id_str = str(slot.id)

            # Проверяем, свободен ли слот
            is_free = slot.is_available()

            # Слот доступен если:
            # 1. Он свободен ИЛИ
            # 2. Это наш текущий слот (в booked_slots)
            if is_free or slot_id_str in booked_slots:
                # Формируем строку времени
                time_display = f"{slot.start_time.strftime('%H:%M')}-{slot.end_time.strftime('%H:%M')}"

                # Получаем описание слота (если есть)
                slot_description = getattr(slot, "description", "") or ""

                # Если есть описание - добавляем его к времени
                if slot_description:
                    time_with_description = f"{time_display} - {slot_description}"
                else:
                    time_with_description = time_display

                slots_data.append(
                    {
                        "id": slot.id,
                        "start_time": slot.start_time.strftime("%H:%M:%S"),
                        "end_time": slot.end_time.strftime("%H:%M:%S"),
                        "time": time_with_description,  # Только время и описание
                        "cabinet": f"Каб. {slot.cabinet.number}",
                        "cabinet_number": slot.cabinet.number,
                        "is_available": True,
                        "is_current": slot_id_str in booked_slots,
                        "description": slot_description,
                    }
                )

        # Кэшируем только свободные слоты (или текущий)
        cache.set(cache_key, slots_data, CACHE_TIMEOUTS["DOCTOR_SLOTS_DETAILED"])

    return slots_data


def clear_doctor_slots_cache(doctor_id=None, date=None):
    """
    Очистить кэш слотов врача.

    Args:
        doctor_id: ID врача (если None - очистить все)
        date: дата (если None - очистить все даты)
    """
    if doctor_id and date:
        # Очистить конкретную дату
        if hasattr(date, "strftime"):
            date_str = date.strftime("%Y-%m-%d")
        else:
            date_str = str(date)

        cache_key = CACHE_KEYS["DOCTOR_SLOTS"].format(
            doctor_id=doctor_id, date=date_str
        )
        cache.delete(cache_key)

        detailed_key = CACHE_KEYS["DOCTOR_SLOTS_DETAILED"].format(
            doctor_id=doctor_id, date=date_str
        )
        cache.delete(detailed_key)

    elif doctor_id:
        # Очистить все даты для врача (сложнее)
        # В реальном приложении используйте паттерн префиксов
        pass
    else:
        # Очистить все (в продакшене не использовать)
        pass


def invalidate_slots_cache_on_appointment_change(sender, instance, **kwargs):
    """
    Сигнал для очистки кэша слотов при изменении записи.
    """
    if hasattr(instance, "time_slot") and instance.time_slot:
        doctor_id = instance.time_slot.doctor_id
        date = instance.time_slot.date
        clear_doctor_slots_cache(doctor_id, date)
