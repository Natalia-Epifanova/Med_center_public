import json
from datetime import datetime

from django.db import models
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from patients.models import Patient


@csrf_exempt
@require_http_methods(["POST"])
def check_patient_api(request):
    """API для проверки существования пациента (оригинальный рабочий вариант)"""
    try:
        data = json.loads(request.body)
        surname = data.get("surname", "").strip()
        first_name = data.get("first_name", "").strip()
        date_of_birth = data.get("date_of_birth", "")

        if not surname or not first_name:
            return JsonResponse(
                {"error": "Фамилия и имя обязательны для проверки"}, status=400
            )

        # Поиск пациента (оригинальная логика)
        query = Patient.objects.filter(
            surname__iexact=surname, first_name__iexact=first_name
        )

        if date_of_birth:
            # Преобразуем строку даты
            try:
                # Поддерживаем разные форматы
                if "T" in date_of_birth:  # ISO формат
                    date_obj = datetime.fromisoformat(
                        date_of_birth.replace("Z", "+00:00")
                    ).date()
                else:
                    # Пробуем разные форматы
                    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"):
                        try:
                            date_obj = datetime.strptime(date_of_birth, fmt).date()
                            break
                        except ValueError:
                            continue
                    else:
                        date_obj = None

                if date_obj:
                    query = query.filter(date_of_birth=date_obj)
            except (ValueError, TypeError):
                # Если дата в неправильном формате, игнорируем ее при поиске
                pass

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
                            existing_patient.date_of_birth.strftime("%d.%m.%Y")
                            if existing_patient.date_of_birth
                            else None
                        ),
                    },
                }
            )
        else:
            return JsonResponse({"exists": False})

    except json.JSONDecodeError:
        return JsonResponse({"error": "Неверный формат JSON"}, status=400)
    except Exception as e:
        return JsonResponse({"error": f"Ошибка сервера: {str(e)}"}, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def search_patients_api(request):
    """API для поиска пациентов по ФИО или номеру карты (оригинальный вариант)"""
    try:
        search_query = request.GET.get("q", "").strip()

        if len(search_query) < 2:
            return JsonResponse(
                {"error": "Введите хотя бы 2 символа для поиска"}, status=400
            )

        # Ищем пациентов (оригинальная логика поиска)
        patients = Patient.objects.filter(
            models.Q(surname__icontains=search_query)
            | models.Q(first_name__icontains=search_query)
            | models.Q(phone_number__icontains=search_query)
            | models.Q(card_number__icontains=search_query)
        )[
            :10
        ]  # Ограничиваем результаты

        # Формируем ответ в старом формате
        patients_list = []
        for patient in patients:
            patients_list.append(
                {
                    "id": patient.id,
                    "full_name": patient.get_full_name(),
                    "card_number": patient.card_number,
                    "phone_number": patient.phone_number,
                    "date_of_birth": (
                        patient.date_of_birth.strftime("%d.%m.%Y")
                        if patient.date_of_birth
                        else ""
                    ),
                }
            )

        return JsonResponse(
            {
                "count": len(patients_list),
                "patients": patients_list,
            }
        )

    except Exception as e:
        return JsonResponse({"error": f"Ошибка при поиске: {str(e)}"}, status=500)
