from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json
from datetime import datetime
from .models import Patient, TimeSlot


@csrf_exempt
@require_http_methods(["POST"])
def check_patient_api(request):
    """API для проверки существования пациента"""
    try:
        data = json.loads(request.body)
        surname = data.get("surname", "").strip()
        first_name = data.get("first_name", "").strip()
        date_of_birth = data.get("date_of_birth", "")

        if not surname or not first_name:
            return JsonResponse(
                {"error": "Фамилия и имя обязательны для проверки"}, status=400
            )

        # Поиск пациента
        query = Patient.objects.filter(
            surname__iexact=surname, first_name__iexact=first_name
        )

        if date_of_birth:
            query = query.filter(date_of_birth=date_of_birth)

        existing_patient = query.first()

        if existing_patient:
            return JsonResponse(
                {
                    "exists": True,
                    "patient": {
                        "id": existing_patient.id,
                        "full_name": existing_patient.get_full_name(),
                        "card_number": existing_patient.card_number,
                        "phone_number": existing_patient.phone_number,
                        "date_of_birth": (
                            existing_patient.date_of_birth.isoformat()
                            if existing_patient.date_of_birth
                            else None
                        ),
                    },
                }
            )
        else:
            return JsonResponse({"exists": False})

    except Exception as e:
        return JsonResponse({"error": f"Ошибка сервера: {str(e)}"}, status=500)


@csrf_exempt
def get_available_slots(request):
    """API для получения доступных слотов"""
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            doctor_id = data.get("doctor_id")
            date = data.get("date")
            current_slot_id = data.get("current_slot_id")
            current_appointment_id = data.get("current_appointment_id")

            if not doctor_id or not date:
                return JsonResponse(
                    {"error": "Не указаны doctor_id или date"}, status=400
                )

            # Преобразование даты
            try:
                appointment_date = datetime.strptime(date, "%Y-%m-%d").date()
            except ValueError:
                return JsonResponse(
                    {"error": "Неверный формат даты. Ожидается YYYY-MM-DD"}, status=400
                )

            # Получение слотов
            all_slots = (
                TimeSlot.objects.filter(
                    doctor_id=doctor_id, date=appointment_date, slot_type="working"
                )
                .select_related("cabinet", "doctor")
                .order_by("start_time")
            )

            # Фильтрация доступных слотов
            available_slots = []
            for slot in all_slots:
                is_free = not slot.appointments.exists()
                is_current_appointment = (
                    current_appointment_id
                    and slot.appointments.filter(id=current_appointment_id).exists()
                )
                is_current_slot = str(slot.id) == str(current_slot_id)

                if is_free or is_current_appointment or is_current_slot:
                    available_slots.append(
                        {
                            "id": slot.id,
                            "time": f"{slot.start_time.strftime('%H:%M')}-{slot.end_time.strftime('%H:%M')}",
                            "cabinet": f"Каб. {slot.cabinet.number}",
                            "is_current": is_current_slot,
                        }
                    )

            return JsonResponse({"slots": available_slots})

        except Exception as e:
            return JsonResponse({"error": f"Ошибка сервера: {str(e)}"}, status=500)

    return JsonResponse({"error": "Метод не разрешен"}, status=405)


@csrf_exempt
def check_procedural_availability(request):
    """API для проверки доступности процедурного кабинета"""
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            date = data.get("date")
            start_time = data.get("start_time")
            end_time = data.get("end_time")
            current_appointment_id = data.get("current_appointment_id")

            if not date or not start_time or not end_time:
                return JsonResponse(
                    {"error": "Не указаны date, start_time или end_time"}, status=400
                )

            # Преобразуем строки в объекты
            try:
                appointment_date = datetime.strptime(date, "%Y-%m-%d").date()
                start_time_obj = datetime.strptime(start_time, "%H:%M:%S").time()
                end_time_obj = datetime.strptime(end_time, "%H:%M:%S").time()
            except ValueError as e:
                return JsonResponse(
                    {"error": f"Неверный формат времени: {str(e)}"}, status=400
                )

            # Находим процедурный кабинет
            procedural_cabinet = Cabinet.objects.get(number=6)

            # Ищем занятые конфликтующие слоты
            occupied_conflicting_slots = TimeSlot.get_conflicting_slots(
                date=appointment_date,
                start_time=start_time_obj,
                end_time=end_time_obj,
                cabinet=procedural_cabinet,
            ).filter(appointments__isnull=False)

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
                                "time": f"{slot.start_time}-{slot.end_time}",
                                "patient": (
                                    slot.appointments.first().patient.get_full_name()
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

        except Exception as e:
            return JsonResponse({"error": f"Ошибка сервера: {str(e)}"}, status=500)

    return JsonResponse({"error": "Метод не разрешен"}, status=405)
