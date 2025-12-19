import json
from datetime import datetime

from django.db.models import Prefetch
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .models import BloodTest, BloodTestCategory, TimeSlot, Cabinet


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
                print(f"Error in check_procedural_availability (inner): {str(e)}")
                return JsonResponse(
                    {"error": f"Внутренняя ошибка: {str(e)}"}, status=500
                )

        except json.JSONDecodeError:
            return JsonResponse({"error": "Неверный формат JSON"}, status=400)
        except Exception as e:
            print(f"Error in check_procedural_availability: {str(e)}")
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
