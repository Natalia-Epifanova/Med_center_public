import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist

from appointments.services import AppointmentChainService, AppointmentService
from timetable.models import Doctor, MedicalService, TimeSlot
from timetable.utils import get_doctor_services

from timetable.models import Doctor, MedicalService, TimeSlot

# Если есть сервисы, импортируем их
try:
    from appointments.services import AppointmentChainService, AppointmentService
except ImportError:
    AppointmentChainService = None
    AppointmentService = None

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
    """API для получения доступных слотов врача"""
    try:
        data = json.loads(request.body)
        doctor_id = data.get("doctor_id")
        date = data.get("date")
        exclude_slot_id = data.get("exclude_slot_id")

        if not doctor_id or not date:
            return JsonResponse({"error": "Не указаны doctor_id или date"}, status=400)

        doctor = Doctor.objects.get(id=doctor_id)

        # ВАЖНО: Проверьте, что метод get_available_slots_for_doctor существует
        try:
            if AppointmentService and hasattr(
                AppointmentService, "get_available_slots_for_doctor"
            ):
                slots = AppointmentService.get_available_slots_for_doctor(
                    doctor=doctor, date=date, exclude_slot_id=exclude_slot_id
                )
            else:
                # Альтернативная реализация
                from django.db.models import Q
                from datetime import datetime

                target_date = datetime.strptime(date, "%Y-%m-%d").date()

                slots = (
                    TimeSlot.objects.filter(
                        doctor=doctor, date=target_date, slot_type="working"
                    )
                    .filter(
                        Q(appointments__isnull=True) | Q(id=exclude_slot_id)
                        if exclude_slot_id
                        else Q(appointments__isnull=True)
                    )
                    .order_by("start_time")
                )

        except Exception as service_error:
            print(f"Error using AppointmentService: {service_error}")
            # Простая реализация
            from django.db.models import Q
            from datetime import datetime

            target_date = datetime.strptime(date, "%Y-%m-%d").date()

            slots = (
                TimeSlot.objects.filter(
                    doctor=doctor, date=target_date, slot_type="working"
                )
                .filter(
                    Q(appointments__isnull=True) | Q(id=exclude_slot_id)
                    if exclude_slot_id
                    else Q(appointments__isnull=True)
                )
                .order_by("start_time")
            )

        slots_data = []
        for slot in slots:
            slots_data.append(
                {
                    "id": slot.id,
                    "time": f"{slot.start_time.strftime('%H:%M')}-{slot.end_time.strftime('%H:%M')}",
                    "cabinet": f"Каб. {slot.cabinet.number}",
                    "start_time": slot.start_time.strftime("%H:%M:%S"),
                    "end_time": slot.end_time.strftime("%H:%M:%S"),
                    "cabinet_number": slot.cabinet.number,
                    "cabinet_name": slot.cabinet.name_of_cabinet or "",
                }
            )

        return JsonResponse(
            {
                "success": True,
                "slots": slots_data,
                "doctor": {"id": doctor.id, "name": doctor.surname},
                "date": date,
                "count": len(slots_data),
            }
        )

    except Doctor.DoesNotExist:
        return JsonResponse({"error": "Врач не найден"}, status=404)
    except ValueError as e:
        return JsonResponse({"error": f"Неверный формат даты: {str(e)}"}, status=400)
    except Exception as e:
        # ДЛЯ ОТЛАДКИ
        import traceback

        error_details = traceback.format_exc()
        print(f"Error in get_available_slots_for_doctor_api: {e}")
        print(f"Traceback: {error_details}")

        return JsonResponse(
            {
                "success": False,
                "error": str(e),
                "details": "Ошибка при загрузке слотов",
            },
            status=500,
        )


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
