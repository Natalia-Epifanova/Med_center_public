from django.db.models import Prefetch
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json
from datetime import datetime
from .models import TimeSlot, BloodTestCategory, BloodTest
from patients.models import Patient


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
@require_http_methods(["POST"])
def get_available_slots(request):
    """API для получения доступных слотов для редактирования записи"""
    try:
        data = json.loads(request.body)
        doctor_id = data.get("doctor_id")
        date = data.get("date")
        current_slot_id = data.get("current_slot_id")
        current_appointment_id = data.get("current_appointment_id")

        print(
            f"API request - doctor_id: {doctor_id}, date: {date}, current_slot_id: {current_slot_id}, current_appointment_id: {current_appointment_id}"
        )

        if not doctor_id or not date:
            return JsonResponse({"error": "Не указаны doctor_id или date"}, status=400)

        # Преобразование даты
        try:
            appointment_date = datetime.strptime(date, "%Y-%m-%d").date()
        except ValueError:
            return JsonResponse(
                {"error": "Неверный формат даты. Ожидается YYYY-MM-DD"}, status=400
            )

        # Получение всех рабочих слотов врача на указанную дату
        all_slots = (
            TimeSlot.objects.filter(
                doctor_id=doctor_id, date=appointment_date, slot_type="working"
            )
            .select_related("cabinet", "doctor")
            .prefetch_related("appointments")
            .order_by("start_time")
        )

        print(
            f"Found {all_slots.count()} total slots for doctor {doctor_id} on {appointment_date}"
        )

        # Фильтрация доступных слотов
        available_slots = []
        for slot in all_slots:
            # Проверяем, занят ли слот
            is_occupied = slot.appointments.exists()

            # Проверяем, является ли этот слот текущим слотом редактируемой записи
            is_current_slot = str(slot.id) == str(current_slot_id)

            # Проверяем, принадлежит ли занятость текущей редактируемой записи
            is_occupied_by_current = False
            if is_occupied and current_appointment_id:
                current_appointment = slot.appointments.filter(
                    id=current_appointment_id
                ).first()
                is_occupied_by_current = current_appointment is not None

            # Слот доступен если:
            # 1. Он не занят ИЛИ
            # 2. Это текущий слот записи ИЛИ
            # 3. Он занят текущей редактируемой записью
            if (not is_occupied) or is_current_slot or is_occupied_by_current:
                available_slots.append(
                    {
                        "id": slot.id,
                        "time": f"{slot.start_time.strftime('%H:%M')}-{slot.end_time.strftime('%H:%M')}",
                        "cabinet": f"Каб. {slot.cabinet.number}",
                        "is_current": is_current_slot,
                        "start_time": slot.start_time.strftime("%H:%M:%S"),
                        "end_time": slot.end_time.strftime("%H:%M:%S"),
                    }
                )
                print(
                    f"Added slot {slot.id}: {slot.start_time}-{slot.end_time} (current: {is_current_slot})"
                )

        print(f"Returning {len(available_slots)} available slots")

        return JsonResponse(
            {
                "slots": available_slots,
                "debug": {
                    "total_slots": all_slots.count(),
                    "available_slots": len(available_slots),
                    "doctor_id": doctor_id,
                    "date": date,
                    "current_slot_id": current_slot_id,
                    "current_appointment_id": current_appointment_id,
                },
            }
        )

    except Exception as e:
        print(f"Error in api_get_available_slots: {str(e)}")
        return JsonResponse({"error": f"Ошибка сервера: {str(e)}"}, status=500)


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
