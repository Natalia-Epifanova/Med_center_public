import json
import logging
from datetime import datetime

import datetime
from appointments.services import AppointmentChainService, AppointmentService
from appointments.utils_for_caches import (
    get_cached_active_doctors,
    get_cached_blood_tests,
    get_cached_doctor_services,
    get_cached_doctor_slots_for_api,
    get_procedural_cabinet,
)
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.exceptions import ObjectDoesNotExist
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_http_methods, require_POST
from timetable.models import BloodTestCategory, Doctor, MedicalService, TimeSlot
from timetable.services import get_blood_test_price_on_date, get_service_price_on_date

logger = logging.getLogger(__name__)


@require_http_methods(["POST"])
@login_required
def get_doctor_services_api(request):
    """API для получения услуг врача"""
    user_id = getattr(request.user, "id", None)
    username = getattr(request.user, "username", "unknown")

    try:
        data = json.loads(request.body)
        doctor_id = data.get("doctor_id")
        date_str = data.get("date")
        time_slot_id = data.get("time_slot_id")

        logger.info(
            "Запрос услуг врача: user_id=%s username=%s doctor_id=%s date=%s time_slot_id=%s",
            user_id,
            username,
            doctor_id,
            date_str,
            time_slot_id,
        )

        target_date = None
        if date_str:
            try:
                target_date = datetime.date.fromisoformat(date_str)
            except ValueError:
                logger.warning(
                    "Некорректная дата в get_doctor_services_api: user_id=%s doctor_id=%s date=%s",
                    user_id,
                    doctor_id,
                    date_str,
                )
                target_date = None

        if not doctor_id:
            logger.warning(
                "Не передан doctor_id в get_doctor_services_api: user_id=%s username=%s",
                user_id,
                username,
            )
            return JsonResponse({"error": "Не указан doctor_id"}, status=400)

        doctor = Doctor.objects.get(id=doctor_id)
        services = get_cached_doctor_services(doctor)
        time_slot = None

        if time_slot_id:
            time_slot = TimeSlot.objects.filter(id=time_slot_id, doctor=doctor).first()

        services = AppointmentService.filter_services_for_time_slot(services, time_slot)

        services_data = []
        for service in services:
            price_value = (
                get_service_price_on_date(service, target_date)
                if target_date
                else service.price
            )
            services_data.append(
                {
                    "id": service.id,
                    "name": service.name,
                    "price": float(price_value),
                    "category": service.category,
                    "duration": (
                        service.duration if hasattr(service, "duration") else None
                    ),
                }
            )

        logger.info(
            "Услуги врача успешно получены: user_id=%s doctor_id=%s services_count=%s",
            user_id,
            doctor_id,
            len(services_data),
        )

        return JsonResponse(
            {
                "success": True,
                "services": services_data,
                "doctor": {
                    "id": doctor.id,
                    "name": f"{doctor.surname} {doctor.first_name[0]}.{doctor.last_name[0]}.",
                    "specialization": doctor.get_specialization_display(),
                },
            }
        )

    except Doctor.DoesNotExist:
        logger.warning(
            "Врач не найден в get_doctor_services_api: user_id=%s doctor_id=%s",
            user_id,
            request.POST.get("doctor_id") if hasattr(request, "POST") else None,
        )
        return JsonResponse({"error": "Врач не найден"}, status=404)

    except json.JSONDecodeError:
        logger.warning(
            "Некорректный JSON в get_doctor_services_api: user_id=%s body=%s",
            user_id,
            request.body[:500],
        )
        return JsonResponse({"error": "Неверный формат JSON"}, status=400)

    except Exception:
        logger.exception(
            "Ошибка в get_doctor_services_api: user_id=%s username=%s",
            user_id,
            username,
        )
        return JsonResponse({"error": "Внутренняя ошибка сервера"}, status=500)


@require_http_methods(["POST"])
@login_required
def get_available_slots_for_doctor_api(request):
    """API для получения доступных слотов врача для цепочек записей"""
    user_id = getattr(request.user, "id", None)
    username = getattr(request.user, "username", "unknown")

    try:
        data = json.loads(request.body)
        doctor_id = data.get("doctor_id")
        date = data.get("date")
        booked_slots = data.get("booked_slots", [])

        logger.info(
            "Запрос доступных слотов врача: user_id=%s username=%s doctor_id=%s date=%s booked_slots=%s",
            user_id,
            username,
            doctor_id,
            date,
            booked_slots,
        )

        if not doctor_id or not date:
            logger.warning(
                "Не указаны doctor_id или date в get_available_slots_for_doctor_api: user_id=%s doctor_id=%s date=%s",
                user_id,
                doctor_id,
                date,
            )
            return JsonResponse({"error": "Не указаны doctor_id или date"}, status=400)

        slots_data = get_cached_doctor_slots_for_api(
            doctor_id=doctor_id, date=date, booked_slots=booked_slots
        )

        logger.info(
            "Доступные слоты успешно получены: user_id=%s doctor_id=%s date=%s slots_count=%s",
            user_id,
            doctor_id,
            date,
            len(slots_data),
        )

        return JsonResponse(
            {
                "success": True,
                "slots": slots_data,
                "count": len(slots_data),
            }
        )

    except json.JSONDecodeError:
        logger.warning(
            "Некорректный JSON в get_available_slots_for_doctor_api: user_id=%s body=%s",
            user_id,
            request.body[:500],
        )
        return JsonResponse(
            {"success": False, "error": "Неверный формат JSON"}, status=400
        )

    except Exception:
        logger.exception(
            "Ошибка в get_available_slots_for_doctor_api: user_id=%s username=%s",
            user_id,
            username,
        )
        return JsonResponse(
            {"success": False, "error": "Внутренняя ошибка сервера"}, status=500
        )


@require_http_methods(["POST"])
@login_required
def validate_additional_appointment_api(request):
    """API для валидации данных дополнительной записи"""
    user_id = getattr(request.user, "id", None)
    username = getattr(request.user, "username", "unknown")

    try:
        data = json.loads(request.body)

        doctor_id = data.get("doctor_id")
        service_id = data.get("service_id")
        time_slot_id = data.get("time_slot_id")
        current_appointment_id = data.get("current_appointment_id")

        logger.info(
            "Валидация дополнительной записи: user_id=%s username=%s doctor_id=%s service_id=%s time_slot_id=%s current_appointment_id=%s",
            user_id,
            username,
            doctor_id,
            service_id,
            time_slot_id,
            current_appointment_id,
        )

        if not all([doctor_id, service_id, time_slot_id]):
            logger.warning(
                "Не все обязательные поля переданы в validate_additional_appointment_api: user_id=%s doctor_id=%s service_id=%s time_slot_id=%s",
                user_id,
                doctor_id,
                service_id,
                time_slot_id,
            )
            return JsonResponse(
                {"error": "Не все обязательные поля заполнены"}, status=400
            )

        doctor = Doctor.objects.get(id=doctor_id)
        service = MedicalService.objects.get(id=service_id)
        time_slot = TimeSlot.objects.get(id=time_slot_id)

        errors = AppointmentChainService.validate_additional_appointment(
            doctor=doctor,
            service=service,
            time_slot=time_slot,
            current_appointment_id=current_appointment_id,
        )

        if errors:
            logger.warning(
                "Дополнительная запись не прошла валидацию: user_id=%s doctor_id=%s service_id=%s time_slot_id=%s errors=%s",
                user_id,
                doctor_id,
                service_id,
                time_slot_id,
                errors,
            )
        else:
            logger.info(
                "Дополнительная запись прошла валидацию: user_id=%s doctor_id=%s service_id=%s time_slot_id=%s",
                user_id,
                doctor_id,
                service_id,
                time_slot_id,
            )

        return JsonResponse(
            {
                "success": len(errors) == 0,
                "errors": errors,
                "is_valid": len(errors) == 0,
            }
        )

    except ObjectDoesNotExist as e:
        logger.warning(
            "Объект не найден в validate_additional_appointment_api: user_id=%s error=%s",
            user_id,
            str(e),
        )
        return JsonResponse({"error": f"Объект не найден: {str(e)}"}, status=404)

    except json.JSONDecodeError:
        logger.warning(
            "Некорректный JSON в validate_additional_appointment_api: user_id=%s body=%s",
            user_id,
            request.body[:500],
        )
        return JsonResponse({"error": "Неверный формат JSON"}, status=400)

    except Exception:
        logger.exception(
            "Ошибка в validate_additional_appointment_api: user_id=%s username=%s",
            user_id,
            username,
        )
        return JsonResponse({"error": "Внутренняя ошибка сервера"}, status=500)


@require_http_methods(["POST"])
@login_required
def get_available_doctors_api(request):
    """API для получения списка доступных врачей"""
    user_id = getattr(request.user, "id", None)
    username = getattr(request.user, "username", "unknown")

    try:
        logger.info(
            "Запрос списка доступных врачей: user_id=%s username=%s",
            user_id,
            username,
        )

        doctors_data = get_cached_active_doctors()

        logger.info(
            "Список доступных врачей успешно получен: user_id=%s doctors_count=%s",
            user_id,
            len(doctors_data),
        )

        return JsonResponse(
            {"success": True, "doctors": doctors_data, "count": len(doctors_data)}
        )

    except Exception:
        logger.exception(
            "Ошибка в get_available_doctors_api: user_id=%s username=%s",
            user_id,
            username,
        )
        return JsonResponse({"error": "Внутренняя ошибка сервера"}, status=500)


@require_POST
@login_required
def api_get_next_slot(request):
    """API для получения следующего временного слота"""
    user_id = getattr(request.user, "id", None)
    username = getattr(request.user, "username", "unknown")

    try:
        data = json.loads(request.body)
        doctor_id = data.get("doctor_id")
        date = data.get("date")
        current_slot_id = data.get("current_slot_id")

        logger.info(
            "Запрос следующего слота: user_id=%s username=%s doctor_id=%s date=%s current_slot_id=%s",
            user_id,
            username,
            doctor_id,
            date,
            current_slot_id,
        )

        if not all([doctor_id, date, current_slot_id]):
            logger.warning(
                "Не все параметры переданы в api_get_next_slot: user_id=%s doctor_id=%s date=%s current_slot_id=%s",
                user_id,
                doctor_id,
                date,
                current_slot_id,
            )
            return JsonResponse(
                {"success": False, "error": "Missing required parameters"}, status=400
            )

        try:
            current_slot = TimeSlot.objects.get(
                id=current_slot_id, doctor_id=doctor_id, date=date
            )
        except TimeSlot.DoesNotExist:
            logger.warning(
                "Текущий слот не найден в api_get_next_slot: user_id=%s doctor_id=%s date=%s current_slot_id=%s",
                user_id,
                doctor_id,
                date,
                current_slot_id,
            )
            return JsonResponse(
                {"success": False, "error": "Current slot not found"}, status=404
            )

        next_slots = TimeSlot.objects.filter(
            doctor_id=doctor_id,
            date=date,
            start_time__gt=current_slot.start_time,
        ).order_by("start_time")

        if next_slots.exists():
            next_slot = next_slots.first()

            logger.info(
                "Следующий слот найден: user_id=%s doctor_id=%s date=%s current_slot_id=%s next_slot_id=%s",
                user_id,
                doctor_id,
                date,
                current_slot_id,
                next_slot.id,
            )

            return JsonResponse(
                {
                    "success": True,
                    "next_slot": {
                        "id": next_slot.id,
                        "start_time": next_slot.start_time.strftime("%H:%M"),
                        "end_time": next_slot.end_time.strftime("%H:%M"),
                        "cabinet": next_slot.cabinet.number,
                    },
                }
            )

        logger.info(
            "Следующий слот не найден: user_id=%s doctor_id=%s date=%s current_slot_id=%s",
            user_id,
            doctor_id,
            date,
            current_slot_id,
        )
        return JsonResponse({"success": True, "next_slot": None})

    except json.JSONDecodeError:
        logger.warning(
            "Некорректный JSON в api_get_next_slot: user_id=%s body=%s",
            user_id,
            request.body[:500],
        )
        return JsonResponse(
            {"success": False, "error": "Неверный формат JSON"}, status=400
        )

    except Exception:
        logger.exception(
            "Ошибка в api_get_next_slot: user_id=%s username=%s",
            user_id,
            username,
        )
        return JsonResponse(
            {"success": False, "error": "Внутренняя ошибка сервера"},
            status=500,
        )


def get_blood_tests(request):
    """API для получения анализов крови с категориями"""
    try:
        logger.info("Запрос списка анализов крови")
        target_date = None
        date_value = request.GET.get("date")
        if date_value:
            target_date = datetime.datetime.strptime(date_value, "%Y-%m-%d").date()

        if target_date:
            categories = (
                BloodTestCategory.objects.filter(is_active=True)
                .prefetch_related("tests")
                .order_by("order")
            )
            categories_data = []
            for category in categories:
                tests_data = []
                for test in category.tests.all().order_by("name"):
                    tests_data.append(
                        {
                            "id": test.id,
                            "code": test.code,
                            "name": test.name,
                            "biomaterial": test.biomaterial,
                            "biomaterial_display": test.get_biomaterial_display(),
                            "price": float(
                                get_blood_test_price_on_date(test, target_date)
                            ),
                            "execution_time": test.execution_time,
                            "category_id": category.id,
                            "category_name": category.name,
                        }
                    )
                categories_data.append(
                    {"id": category.id, "name": category.name, "tests": tests_data}
                )
        else:
            categories_data = get_cached_blood_tests()
        logger.info(
            "Список анализов крови успешно получен: categories_count=%s",
            len(categories_data),
        )
        return JsonResponse({"categories": categories_data})
    except Exception:
        logger.exception("Ошибка в get_blood_tests")
        return JsonResponse({"error": "Внутренняя ошибка сервера"}, status=500)


@login_required
@require_GET
def check_slot_lock(request, slot_id):
    """AJAX endpoint для проверки блокировки слота"""
    user_id = getattr(request.user, "id", None)
    username = getattr(request.user, "username", "unknown")

    try:
        logger.info(
            "Проверка блокировки слота: user_id=%s username=%s slot_id=%s",
            user_id,
            username,
            slot_id,
        )

        cache_key = f"slot_lock_{slot_id}"
        cached_lock = cache.get(cache_key)

        if cached_lock:
            logger.info(
                "Слот заблокирован: user_id=%s slot_id=%s locked_by=%s",
                user_id,
                slot_id,
                cached_lock.get(
                    "user_display_name", cached_lock.get("user", "неизвестный")
                ),
            )
            return JsonResponse(
                {
                    "is_locked": True,
                    "locked_by": cached_lock.get(
                        "user_display_name", cached_lock.get("user", "неизвестный")
                    ),
                    "lock_time": cached_lock.get("time"),
                }
            )

        logger.info("Слот не заблокирован: user_id=%s slot_id=%s", user_id, slot_id)
        return JsonResponse({"is_locked": False})

    except Exception:
        logger.exception(
            "Ошибка в check_slot_lock: user_id=%s username=%s slot_id=%s",
            user_id,
            username,
            slot_id,
        )
        return JsonResponse({"is_locked": False, "error": "Внутренняя ошибка сервера"})


@login_required
def check_procedural_availability(request):
    """API для проверки доступности процедурного кабинета"""
    user_id = getattr(request.user, "id", None)
    username = getattr(request.user, "username", "unknown")

    if request.method == "POST":
        try:
            data = json.loads(request.body)
            date = data.get("date")
            time_slot_id = data.get("time_slot_id")
            current_appointment_id = data.get("current_appointment_id")
            start_time = data.get("start_time")
            end_time = data.get("end_time")

            logger.info(
                "Проверка доступности процедурного кабинета: user_id=%s username=%s date=%s time_slot_id=%s current_appointment_id=%s start_time=%s end_time=%s",
                user_id,
                username,
                date,
                time_slot_id,
                current_appointment_id,
                start_time,
                end_time,
            )

            if not date:
                logger.warning(
                    "Не указана дата в check_procedural_availability: user_id=%s",
                    user_id,
                )
                return JsonResponse({"error": "Не указана дата"}, status=400)

            try:
                appointment_date = datetime.datetime.strptime(date, "%Y-%m-%d").date()
                procedural_cabinet = get_procedural_cabinet()

                if time_slot_id:
                    time_slot = TimeSlot.objects.get(id=time_slot_id)

                    if time_slot.date != appointment_date:
                        logger.warning(
                            "Дата слота не совпадает с датой запроса: user_id=%s time_slot_id=%s slot_date=%s request_date=%s",
                            user_id,
                            time_slot_id,
                            time_slot.date,
                            appointment_date,
                        )
                        return JsonResponse(
                            {
                                "is_available": False,
                                "error": "Дата слота не совпадает с указанной датой",
                            }
                        )

                    start_time = time_slot.start_time
                    end_time = time_slot.end_time

                elif start_time and end_time:
                    try:
                        start_time = datetime.datetime.strptime(
                            start_time, "%H:%M"
                        ).time()
                        end_time = datetime.datetime.strptime(end_time, "%H:%M").time()
                    except ValueError:
                        logger.warning(
                            "Неверный формат времени в check_procedural_availability: user_id=%s start_time=%s end_time=%s",
                            user_id,
                            start_time,
                            end_time,
                        )
                        return JsonResponse(
                            {"error": "Неверный формат времени"}, status=400
                        )
                else:
                    logger.warning(
                        "Не передано время для проверки процедурного кабинета: user_id=%s date=%s time_slot_id=%s start_time=%s end_time=%s",
                        user_id,
                        date,
                        time_slot_id,
                        start_time,
                        end_time,
                    )
                    return JsonResponse(
                        {
                            "error": "Не указано время (либо time_slot_id, либо start_time и end_time)"
                        },
                        status=400,
                    )

                occupied_conflicting_slots = (
                    TimeSlot.objects.filter(
                        date=appointment_date,
                        cabinet=procedural_cabinet,
                        appointments__isnull=False,
                    )
                    .filter(
                        start_time__lt=end_time,
                        end_time__gt=start_time,
                    )
                    .distinct()
                )

                if current_appointment_id:
                    occupied_conflicting_slots = occupied_conflicting_slots.exclude(
                        appointments__id=current_appointment_id
                    )

                is_available = not occupied_conflicting_slots.exists()

                occupied_slots_data = (
                    [
                        {
                            "id": slot.id,
                            "time": f"{slot.start_time.strftime('%H:%M')}-{slot.end_time.strftime('%H:%M')}",
                            "patient": (
                                slot.appointments.first().patient.full_name
                                if slot.appointments.exists()
                                else "Неизвестно"
                            ),
                        }
                        for slot in occupied_conflicting_slots
                    ]
                    if not is_available
                    else []
                )

                logger.info(
                    "Результат проверки процедурного кабинета: user_id=%s date=%s is_available=%s occupied_count=%s",
                    user_id,
                    date,
                    is_available,
                    len(occupied_slots_data),
                )

                return JsonResponse(
                    {
                        "is_available": is_available,
                        "occupied_slots": occupied_slots_data,
                    }
                )

            except TimeSlot.DoesNotExist:
                logger.warning(
                    "Слот не найден в check_procedural_availability: user_id=%s time_slot_id=%s",
                    user_id,
                    time_slot_id,
                )
                return JsonResponse({"error": "Слот не найден"}, status=404)

            except ValueError as e:
                logger.warning(
                    "Неверный формат даты в check_procedural_availability: user_id=%s date=%s error=%s",
                    user_id,
                    date,
                    str(e),
                )
                return JsonResponse(
                    {"error": f"Неверный формат даты: {str(e)}"}, status=400
                )

            except Exception:
                logger.exception(
                    "Внутренняя ошибка в check_procedural_availability: user_id=%s username=%s",
                    user_id,
                    username,
                )
                return JsonResponse({"error": "Внутренняя ошибка сервера"}, status=500)

        except json.JSONDecodeError:
            logger.warning(
                "Некорректный JSON в check_procedural_availability: user_id=%s body=%s",
                user_id,
                request.body[:500],
            )
            return JsonResponse({"error": "Неверный формат JSON"}, status=400)

        except Exception:
            logger.exception(
                "Ошибка сервера в check_procedural_availability: user_id=%s username=%s",
                user_id,
                username,
            )
            return JsonResponse({"error": "Ошибка сервера"}, status=500)

    logger.warning(
        "Недопустимый метод в check_procedural_availability: user_id=%s method=%s",
        user_id,
        request.method,
    )
    return JsonResponse({"error": "Метод не разрешен"}, status=405)
