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
    """API для поиска пациентов с поиском по дате рождения (простая версия)"""
    try:
        search_query = request.GET.get("q", "").strip()

        if len(search_query) < 2:
            return JsonResponse(
                {"error": "Введите хотя бы 2 символа для поиска"}, status=400
            )

        from django.db import connection
        from django.db.models import Q

        # Начинаем с пустого queryset
        patients = Patient.objects.none()

        print(f"Поиск: '{search_query}'")

        # 1. Пробуем найти по точной дате в разных форматах
        date_formats = ["%d.%m.%Y", "%Y-%m-%d", "%d.%m.%y", "%Y%m%d", "%d%m%Y"]

        for fmt in date_formats:
            try:
                date_obj = datetime.strptime(search_query, fmt).date()
                print(f"Найдена дата в формате {fmt}: {date_obj}")
                patients = Patient.objects.filter(date_of_birth=date_obj)[:10]
                if patients.exists():
                    print(f"Найдено по точной дате: {patients.count()}")
                    break
            except ValueError:
                continue

        # 2. Если не нашли по точной дате, ищем по текстовым полям
        if not patients.exists():
            print("Ищем по текстовым полям и частичным датам")

            # Создаем базовый queryset для текстового поиска
            text_search = Patient.objects.filter(
                Q(surname__icontains=search_query)
                | Q(first_name__icontains=search_query)
                | Q(last_name__icontains=search_query)
                | Q(phone_number__icontains=search_query)
                | Q(card_number__icontains=search_query)
            )

            # 3. ДОБАВЛЯЕМ: поиск по дате рождения через аннотацию
            from django.db.models import CharField, Value
            from django.db.models.functions import Cast, Concat

            try:
                # Преобразуем дату в строку для поиска
                if search_query.replace(".", "").replace("-", "").isdigit():
                    # Для SQLite
                    if connection.vendor == "sqlite":
                        date_search = Patient.objects.extra(
                            where=["strftime('%%d.%%m.%%Y', date_of_birth) LIKE %s"],
                            params=[f"%{search_query}%"],
                        )
                    # Для PostgreSQL
                    elif connection.vendor == "postgresql":
                        date_search = Patient.objects.extra(
                            where=["to_char(date_of_birth, 'DD.MM.YYYY') LIKE %s"],
                            params=[f"%{search_query}%"],
                        )
                    # Для MySQL
                    else:
                        date_search = Patient.objects.extra(
                            where=["DATE_FORMAT(date_of_birth, '%%d.%%m.%%Y') LIKE %s"],
                            params=[f"%{search_query}%"],
                        )

                    # Объединяем результаты
                    patients = (text_search | date_search).distinct()[:10]
                    print(f"Найдено по тексту и дате: {patients.count()}")
                else:
                    patients = text_search[:10]
                    print(f"Найдено только по тексту: {patients.count()}")

            except Exception as db_error:
                print(f"Ошибка поиска по дате: {db_error}")
                patients = text_search[:10]

        # 4. Формируем ответ
        patients_list = []
        for patient in patients:
            patients_list.append(
                {
                    "id": patient.id,
                    "surname": patient.surname,
                    "first_name": patient.first_name,
                    "last_name": patient.last_name or "",
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
        import traceback

        print(f"Ошибка при поиске: {e}")
        print(traceback.format_exc())
        return JsonResponse({"error": f"Ошибка при поиске: {str(e)}"}, status=500)
