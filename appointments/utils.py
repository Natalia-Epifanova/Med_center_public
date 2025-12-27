# appointments/utils.py
from django.core.cache import cache
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q, Prefetch

from appointments.constants import CACHE_KEYS, CACHE_TIMEOUTS, PROCEDURAL_CABINET_NUMBER
from timetable.models import (
    Cabinet,
    MedicalService,
    BloodTestCategory,
    BloodTest,
    Doctor,
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
    Получить QuerySet услуг врача с кэшированием.

    Args:
        doctor: объект врача
        include_current_service: текущая услуга (для включения в queryset)

    Returns:
        QuerySet услуг врача
    """
    if not doctor:
        return MedicalService.objects.filter(is_active=True)

    # Ключ кэша: либо обычный, либо с включением текущей услуги
    if include_current_service:
        cache_key = (
            CACHE_KEYS["DOCTOR_SERVICES"].format(doctor_id=doctor.id)
            + f"_with_current_{include_current_service.id}"
        )
    else:
        cache_key = CACHE_KEYS["DOCTOR_SERVICES"].format(doctor_id=doctor.id)

    service_ids = cache.get(cache_key)

    if service_ids is None:
        # Используем существующую логику из Doctor.get_available_services()
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
                .exclude(
                    Q(id__in=excluded_service_ids) & ~Q(id=include_current_service.id)
                )
                .distinct()
            )

        # Кэшируем ID услуг
        service_ids = list(services_queryset.values_list("id", flat=True))
        cache.set(cache_key, service_ids, CACHE_TIMEOUTS["DOCTOR_SERVICES"])

    # Получаем объекты по ID
    services = MedicalService.objects.filter(id__in=service_ids, is_active=True)

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
            from timetable.models import Doctor

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
