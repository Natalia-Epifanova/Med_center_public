import json
from datetime import datetime

from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Prefetch
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from appointments.services import AppointmentChainService
from appointments.utils_for_caches import (
    get_cached_active_doctors,
    get_cached_blood_tests,
    get_cached_doctor_services,
    get_cached_doctor_slots_for_api,
    get_procedural_cabinet,
)
from timetable.models import (
    BloodTest,
    BloodTestCategory,
    Doctor,
    MedicalService,
    TimeSlot,
)


@csrf_exempt
@require_http_methods(["POST"])
@login_required
def get_doctor_services_api(request):
    """API для получения услуг врача"""
    try:
        data = json.loads(request.body)
        doctor_id = data.get("doctor_id")

        if not doctor_id:
            return JsonResponse({"error": "Не указан doctor_id"}, status=400)

        doctor = Doctor.objects.get(id=doctor_id)
        services = get_cached_doctor_services(doctor)

        services_data = []
        for service in services:
            services_data.append(
                {
                    "id": service.id,
                    "name": service.name,
                    "price": float(service.price),
                    "category": service.category,
                    "duration": (
                        service.duration if hasattr(service, "duration") else None
                    ),
                }
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
        return JsonResponse({"error": "Врач не найден"}, status=404)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
@login_required
def get_available_slots_for_doctor_api(request):
    """API для получения доступных слотов врача для цепочек записей"""
    try:
        data = json.loads(request.body)
        doctor_id = data.get("doctor_id")
        date = data.get("date")
        booked_slots = data.get("booked_slots", [])  # Сюда придет [currentSlotId]

        if not doctor_id or not date:
            return JsonResponse({"error": "Не указаны doctor_id или date"}, status=400)

        slots_data = get_cached_doctor_slots_for_api(
            doctor_id=doctor_id, date=date, booked_slots=booked_slots
        )

        return JsonResponse(
            {
                "success": True,
                "slots": slots_data,
                "count": len(slots_data),
            }
        )

    except Exception as e:
        print(f"Error in get_available_slots_for_doctor_api: {str(e)}")
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
@login_required
def validate_additional_appointment_api(request):
    """API для валидации данных дополнительной записи"""
    try:
        data = json.loads(request.body)

        doctor_id = data.get("doctor_id")
        service_id = data.get("service_id")
        time_slot_id = data.get("time_slot_id")
        current_appointment_id = data.get("current_appointment_id")

        if not all([doctor_id, service_id, time_slot_id]):
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

        return JsonResponse(
            {
                "success": len(errors) == 0,
                "errors": errors,
                "is_valid": len(errors) == 0,
            }
        )

    except ObjectDoesNotExist as e:
        return JsonResponse({"error": f"Объект не найден: {str(e)}"}, status=404)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
@login_required
def get_available_doctors_api(request):
    """API для получения списка доступных врачей"""
    try:
        doctors_data = get_cached_active_doctors()

        return JsonResponse(
            {"success": True, "doctors": doctors_data, "count": len(doctors_data)}
        )

    except Exception as e:
        print(f"ERROR in get_available_doctors_api: {str(e)}")
        import traceback

        traceback.print_exc()
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
@require_POST
@login_required
def api_get_next_slot(request):
    """API для получения следующего временного слота"""
    try:
        data = json.loads(request.body)
        doctor_id = data.get("doctor_id")
        date = data.get("date")
        current_slot_id = data.get("current_slot_id")

        if not all([doctor_id, date, current_slot_id]):
            return JsonResponse(
                {"success": False, "error": "Missing required parameters"}, status=400
            )

        # Получаем текущий слот
        try:
            current_slot = TimeSlot.objects.get(
                id=current_slot_id, doctor_id=doctor_id, date=date
            )
        except TimeSlot.DoesNotExist:
            return JsonResponse(
                {"success": False, "error": "Current slot not found"}, status=404
            )

        # Находим следующий слот по времени начала
        next_slots = TimeSlot.objects.filter(
            doctor_id=doctor_id,
            date=date,
            start_time__gt=current_slot.start_time,
        ).order_by("start_time")

        if next_slots.exists():
            next_slot = next_slots.first()
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
        else:
            return JsonResponse({"success": True, "next_slot": None})

    except Exception as e:

        return JsonResponse(
            {"success": False, "error": str(e)},
            status=500,
        )


@csrf_exempt
@login_required
def check_procedural_availability(request):
    """API для проверки доступности процедурного кабинета"""
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            date = data.get("date")
            time_slot_id = data.get("time_slot_id")
            current_appointment_id = data.get("current_appointment_id")

            # ДОБАВЛЯЕМ: возможность проверить время без time_slot_id
            start_time = data.get("start_time")
            end_time = data.get("end_time")

            if not date:
                return JsonResponse({"error": "Не указана дата"}, status=400)

            try:
                appointment_date = datetime.strptime(date, "%Y-%m-%d").date()

                # Находим процедурный кабинет (кабинет №6)
                procedural_cabinet = get_procedural_cabinet()

                # Если указан time_slot_id, используем его
                if time_slot_id:
                    time_slot = TimeSlot.objects.get(id=time_slot_id)

                    # Проверяем, что дата слота совпадает
                    if time_slot.date != appointment_date:
                        return JsonResponse(
                            {
                                "is_available": False,
                                "error": "Дата слота не совпадает с указанной датой",
                            }
                        )

                    start_time = time_slot.start_time
                    end_time = time_slot.end_time
                elif start_time and end_time:
                    # Или используем переданные время начала и окончания
                    try:
                        start_time = datetime.strptime(start_time, "%H:%M").time()
                        end_time = datetime.strptime(end_time, "%H:%M").time()
                    except ValueError:
                        return JsonResponse(
                            {"error": "Неверный формат времени"}, status=400
                        )
                else:
                    return JsonResponse(
                        {
                            "error": "Не указано время (либо time_slot_id, либо start_time и end_time)"
                        },
                        status=400,
                    )

                # Ищем занятые слоты в процедурном кабинете в это время
                occupied_conflicting_slots = (
                    TimeSlot.objects.filter(
                        date=appointment_date,
                        cabinet=procedural_cabinet,
                        appointments__isnull=False,  # Только занятые слоты
                    )
                    .filter(
                        # Проверяем пересечение времени
                        start_time__lt=end_time,  # начало слота < конец нашего времени
                        end_time__gt=start_time,  # конец слота > начало нашего времени
                    )
                    .distinct()
                )

                # Если есть текущая запись, исключаем ее из проверки
                if current_appointment_id:
                    occupied_conflicting_slots = occupied_conflicting_slots.exclude(
                        appointments__id=current_appointment_id
                    )

                is_available = not occupied_conflicting_slots.exists()

                return JsonResponse(
                    {
                        "is_available": is_available,
                        "occupied_slots": (
                            [
                                {
                                    "id": slot.id,
                                    "time": f"{slot.start_time.strftime('%H:%M')}-{slot.end_time.strftime('%H:%M')}",
                                    "patient": (
                                        slot.appointments.first().patient.full_name()
                                        if slot.appointments.exists()
                                        else "Неизвестно"
                                    ),
                                }
                                for slot in occupied_conflicting_slots
                            ]
                            if not is_available
                            else []
                        ),
                    }
                )

            except TimeSlot.DoesNotExist:
                return JsonResponse({"error": "Слот не найден"}, status=404)
            except ValueError as e:
                return JsonResponse(
                    {"error": f"Неверный формат даты: {str(e)}"}, status=400
                )
            except Exception as e:
                return JsonResponse(
                    {"error": f"Внутренняя ошибка: {str(e)}"}, status=500
                )

        except json.JSONDecodeError:
            return JsonResponse({"error": "Неверный формат JSON"}, status=400)
        except Exception as e:
            return JsonResponse({"error": f"Ошибка сервера: {str(e)}"}, status=500)

    return JsonResponse({"error": "Метод не разрешен"}, status=405)


def get_blood_tests(request):
    """API для получения анализов крови с категориями"""
    categories_data = get_cached_blood_tests()
    return JsonResponse({"categories": categories_data})


@login_required
@require_GET
def check_slot_lock(request, slot_id):
    """AJAX endpoint для проверки блокировки слота"""
    try:
        cache_key = f"slot_lock_{slot_id}"
        cached_lock = cache.get(cache_key)

        if cached_lock:
            return JsonResponse(
                {
                    "is_locked": True,
                    "locked_by": cached_lock.get(
                        "user_display_name", cached_lock.get("user", "неизвестный")
                    ),
                    "lock_time": cached_lock.get("time"),
                }
            )
        else:
            return JsonResponse({"is_locked": False})

    except Exception as e:
        return JsonResponse({"is_locked": False, "error": str(e)})
