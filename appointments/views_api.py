import json
from datetime import datetime

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Prefetch
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST

from appointments.services import AppointmentChainService, AppointmentService
from timetable.models import (
    BloodTest,
    BloodTestCategory,
    Cabinet,
    Doctor,
    MedicalService,
    TimeSlot,
)
from timetable.utils import get_doctor_services


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
        services = get_doctor_services(doctor)

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
        booked_slots = data.get("booked_slots", [])
        main_appointment_time = data.get("main_appointment_time")
        main_appointment_date = data.get("main_appointment_date")

        if not doctor_id or not date:
            return JsonResponse({"error": "Не указаны doctor_id или date"}, status=400)

        doctor = Doctor.objects.get(id=doctor_id)
        target_date = datetime.strptime(date, "%Y-%m-%d").date()

        slots = TimeSlot.objects.filter(
            doctor=doctor, date=target_date, slot_type="working"
        ).order_by("start_time")

        available_slots = []
        for slot in slots:
            # Проверяем доступность
            is_available = slot.is_available()

            # Проверяем, не входит ли в забронированные слоты
            is_booked = str(slot.id) in booked_slots if booked_slots else False

            # Проверяем пересечение с основной записью
            is_intersecting = False
            if main_appointment_time and date == main_appointment_date:
                main_start_str = main_appointment_time.get("start_time")
                main_end_str = main_appointment_time.get("end_time")

                if main_start_str and main_end_str:
                    try:
                        # Конвертируем строки времени в datetime.time
                        main_start = datetime.strptime(
                            main_start_str, "%H:%M:%S"
                        ).time()
                        main_end = datetime.strptime(main_end_str, "%H:%M:%S").time()

                        # Проверяем пересечение (включая полное совпадение)
                        # Два интервала пересекаются, если:
                        # slot.start_time < main_end И slot.end_time > main_start
                        is_intersecting = (
                            slot.start_time < main_end and main_start < slot.end_time
                        )

                        # Если время точно совпадает - это тоже пересечение
                        if slot.start_time == main_start and slot.end_time == main_end:
                            is_intersecting = True

                    except ValueError:
                        # Если ошибка парсинга времени, игнорируем проверку
                        pass

            # Слот доступен если:
            # 1. Доступен И не забронирован И не пересекается с основной записью (если та же дата)
            if is_available and not is_booked and not is_intersecting:
                available_slots.append(slot)

        slots_data = []
        for slot in available_slots:
            slots_data.append(
                {
                    "id": slot.id,
                    "time": f"{slot.start_time.strftime('%H:%M')}-{slot.end_time.strftime('%H:%M')}",
                    "cabinet": f"Каб. {slot.cabinet.number}",
                    "start_time": slot.start_time.strftime("%H:%M:%S"),
                    "end_time": slot.end_time.strftime("%H:%M:%S"),
                    "cabinet_number": slot.cabinet.number,
                }
            )

        return JsonResponse(
            {
                "success": True,
                "slots": slots_data,
                "count": len(slots_data),
            }
        )

    except Doctor.DoesNotExist:
        return JsonResponse({"error": "Врач не найден"}, status=404)
    except Exception as e:
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
    """API для получения списка доступных врачей (исключая основного)"""
    try:
        data = json.loads(request.body)
        exclude_doctor_id = data.get("exclude_doctor_id")

        doctors = Doctor.objects.order_by("surname")

        if exclude_doctor_id:
            doctors = doctors.exclude(id=exclude_doctor_id)

        doctors_data = []
        for doctor in doctors:
            doctors_data.append(
                {
                    "id": doctor.id,
                    "surname": doctor.surname,
                    "first_name": doctor.first_name,
                    "last_name": doctor.last_name,
                    "specialization": doctor.get_specialization_display(),
                }
            )

        return JsonResponse(
            {"success": True, "doctors": doctors_data, "count": len(doctors_data)}
        )

    except Exception as e:
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

            if not date or not time_slot_id:
                return JsonResponse(
                    {"error": "Не указаны date или time_slot_id"}, status=400
                )

            try:
                # Получаем слот по ID
                time_slot = TimeSlot.objects.get(id=time_slot_id)
                appointment_date = datetime.strptime(date, "%Y-%m-%d").date()

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

                # Находим процедурный кабинет (кабинет №6)
                try:
                    procedural_cabinet = Cabinet.objects.get(number=6)
                except Cabinet.DoesNotExist:
                    return JsonResponse(
                        {"error": "Процедурный кабинет (кабинет №6) не найден"},
                        status=404,
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
    categories = (
        BloodTestCategory.objects.filter(is_active=True)
        .prefetch_related(Prefetch("tests", queryset=BloodTest.objects.all()))
        .order_by("order")
    )

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
                    "category_id": category.id,  # ДОБАВЛЯЕМ ЭТО ПОЛЕ
                    "category_name": category.name,  # И ЭТО ТОЖЕ
                }
            )

        categories_data.append(
            {"id": category.id, "name": category.name, "tests": tests_data}
        )

    return JsonResponse({"categories": categories_data})
