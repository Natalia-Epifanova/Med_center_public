from datetime import datetime

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json

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
        patients = Patient.objects.filter(
            surname__iexact=surname, first_name__iexact=first_name
        )

        if date_of_birth:
            patients = patients.filter(date_of_birth=date_of_birth)

        existing_patient = patients.first()

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
    """API для получения доступных слотов врача на конкретную дату"""
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            doctor_id = data.get("doctor_id")
            date = data.get("date")
            current_slot_id = data.get("current_slot_id")
            current_appointment_id = data.get("current_appointment_id")

            print(
                f"API received: doctor_id={doctor_id}, date={date}, current_slot_id={current_slot_id}, current_appointment_id={current_appointment_id}"
            )

            if not doctor_id or not date:
                return JsonResponse(
                    {"error": "Не указаны doctor_id или date"}, status=400
                )

            # Преобразуем строку даты в объект date
            try:
                appointment_date = datetime.strptime(date, "%Y-%m-%d").date()
            except ValueError as e:
                return JsonResponse(
                    {"error": f"Неверный формат даты: {date}. Ожидается YYYY-MM-DD"},
                    status=400,
                )

            # Получаем все рабочие слоты врача на указанную дату
            all_slots = (
                TimeSlot.objects.filter(
                    doctor_id=doctor_id, date=appointment_date, slot_type="working"
                )
                .select_related("cabinet", "doctor")
                .order_by("start_time")
            )

            print(
                f"Found {all_slots.count()} slots for doctor {doctor_id} on {appointment_date}"
            )

            # Собираем доступные слоты
            available_slots = []

            for slot in all_slots:
                # Проверяем, свободен ли слот
                is_free = not slot.appointments.exists()

                # Или это текущая запись (если редактируем)
                is_current_appointment = False
                if current_appointment_id:
                    is_current_appointment = slot.appointments.filter(
                        id=current_appointment_id
                    ).exists()

                # Или это текущий слот (даже если он занят)
                is_current_slot = str(slot.id) == str(current_slot_id)

                print(
                    f"Slot {slot.id}: free={is_free}, current_appt={is_current_appointment}, current_slot={is_current_slot}"
                )

                if is_free or is_current_appointment or is_current_slot:
                    available_slots.append(slot)

            # Формируем данные для ответа
            slots_data = []
            for slot in available_slots:
                slots_data.append(
                    {
                        "id": slot.id,
                        "time": f"{slot.start_time.strftime('%H:%M')}-{slot.end_time.strftime('%H:%M')}",
                        "cabinet": f"Каб. {slot.cabinet.number}",
                        "is_current": str(slot.id) == str(current_slot_id),
                    }
                )

            print(f"Returning {len(slots_data)} available slots")
            return JsonResponse({"slots": slots_data})

        except Exception as e:
            import traceback

            error_traceback = traceback.format_exc()
            print(f"API Error: {str(e)}")
            print(f"Traceback: {error_traceback}")
            return JsonResponse(
                {
                    "error": f"Ошибка сервера: {str(e)}",
                    "traceback": error_traceback,
                },
                status=500,
            )

    return JsonResponse({"error": "Метод не разрешен"}, status=405)
