import json
from datetime import datetime

from django.db import models
from django.http import JsonResponse
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from patients.models import Patient
from patients.services import CardNumberService
from users.permissions.decorators import (
    medical_admin_or_admin_required,
    medical_staff_required,
)


def _parse_date_of_birth(date_of_birth):
    """Преобразует дату рождения из строки в date"""
    if not date_of_birth:
        return None

    try:
        if "T" in date_of_birth:
            return datetime.fromisoformat(date_of_birth.replace("Z", "+00:00")).date()

        for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"):
            try:
                return datetime.strptime(date_of_birth, fmt).date()
            except ValueError:
                continue
    except (ValueError, TypeError):
        return None

    return None


@require_http_methods(["POST"])
@medical_staff_required
def check_patient_api(request):
    """API для проверки существования пациента (оригинальный рабочий вариант)"""
    try:
        data = json.loads(request.body)
        surname = data.get("surname", "").strip()
        first_name = data.get("first_name", "").strip()
        last_name = data.get("last_name", "").strip()
        date_of_birth = data.get("date_of_birth", "")

        if not surname or not first_name:
            return JsonResponse(
                {"error": "Фамилия и имя обязательны для проверки"}, status=400
            )

        # Поиск пациента (оригинальная логика)
        query = Patient.objects.filter(
            surname__iexact=surname, first_name__iexact=first_name
        )

        if last_name:
            query = query.filter(last_name__iexact=last_name)

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
                        "surname": existing_patient.surname,
                        "first_name": existing_patient.first_name,
                        "last_name": existing_patient.last_name or "",
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


@require_http_methods(["POST"])
@medical_staff_required
def check_patient_blacklist_api(request):
    """API для точной проверки черного списка по ФИО и, при необходимости, по дате рождения"""
    try:
        data = json.loads(request.body)
        surname = data.get("surname", "").strip()
        first_name = data.get("first_name", "").strip()
        last_name = data.get("last_name", "").strip()
        date_of_birth = data.get("date_of_birth", "")

        if not all([surname, first_name, last_name]):
            return JsonResponse(
                {
                    "error": "Для проверки черного списка необходимо указать фамилию, имя и отчество"
                },
                status=400,
            )

        matches = list(
            Patient.objects.filter(
                surname__iexact=surname,
                first_name__iexact=first_name,
                last_name__iexact=last_name,
            ).order_by("date_of_birth", "id")
        )

        if not matches:
            return JsonResponse(
                {
                    "found": False,
                    "multiple_matches": False,
                    "is_blacklisted": False,
                }
            )

        resolved_matches = matches
        date_obj = _parse_date_of_birth(date_of_birth)
        if len(matches) > 1 and date_obj:
            filtered_matches = [
                patient for patient in matches if patient.date_of_birth == date_obj
            ]
            if filtered_matches:
                resolved_matches = filtered_matches

        if len(resolved_matches) == 1:
            patient = resolved_matches[0]
            return JsonResponse(
                {
                    "found": True,
                    "multiple_matches": False,
                    "is_blacklisted": patient.is_blacklisted,
                    "comment": patient.blacklist_comment if patient.is_blacklisted else "",
                    "patient": {
                        "id": patient.id,
                        "full_name": patient.get_full_name(),
                        "date_of_birth": (
                            patient.date_of_birth.strftime("%d.%m.%Y")
                            if patient.date_of_birth
                            else ""
                        ),
                    },
                }
            )

        return JsonResponse(
            {
                "found": True,
                "multiple_matches": True,
                "is_blacklisted": False,
                "match_count": len(resolved_matches),
                "message": "Найдено несколько пациентов с таким ФИО. Для точной проверки используйте дату рождения.",
                "patients": [
                    {
                        "id": patient.id,
                        "full_name": patient.get_full_name(),
                        "date_of_birth": (
                            patient.date_of_birth.strftime("%d.%m.%Y")
                            if patient.date_of_birth
                            else ""
                        ),
                        "card_number": patient.card_number,
                        "is_blacklisted": patient.is_blacklisted,
                    }
                    for patient in resolved_matches
                ],
            }
        )

    except json.JSONDecodeError:
        return JsonResponse({"error": "Неверный формат JSON"}, status=400)
    except Exception as e:
        return JsonResponse({"error": f"Ошибка сервера: {str(e)}"}, status=500)


@require_http_methods(["GET"])
@medical_staff_required
def search_patients_api(request):
    """API для поиска пациентов с поиском по дате рождения"""
    try:
        search_query = request.GET.get("q", "").strip()

        if len(search_query) < 2:
            return JsonResponse(
                {"error": "Введите хотя бы 2 символа для поиска"}, status=400
            )

        from django.db.models import Q

        # Разбиваем поисковый запрос на слова
        search_words = search_query.split()

        # Начинаем с базового queryset
        query = Q()

        # Создаем условия для поиска по каждому слову
        for word in search_words:
            word_query = Q(
                Q(surname__icontains=word)
                | Q(first_name__icontains=word)
                | Q(last_name__icontains=word)
                | Q(phone_number__icontains=word)
                | Q(card_number__icontains=word)
                | Q(card_number_IP__icontains=word)
                | Q(card_number_OMS__icontains=word)
            )

            # 1. Поиск по полной дате в формате дд.мм.гггг
            try:
                date_obj = datetime.strptime(word, "%d.%m.%Y").date()
                word_query |= Q(date_of_birth=date_obj)
            except ValueError:
                pass

            # 2. Поиск по частичным датам с 2 точками (дд.мм.гг, дд.мм.г, дд.мм.ггг)
            if word.count(".") == 2:
                parts = word.split(".")

                # Проверяем, что все три части - числа
                if len(parts) == 3 and all(p.isdigit() for p in parts):
                    try:
                        day = int(parts[0])
                        month = int(parts[1])
                        year_part = parts[2]

                        # Проверяем день и месяц на валидность
                        if 1 <= day <= 31 and 1 <= month <= 12:
                            # Проверяем разные варианты года
                            if len(year_part) == 4:
                                # Полный год (гггг)
                                year = int(year_part)
                                if 1900 <= year <= 2100:
                                    word_query |= Q(
                                        date_of_birth__day=day,
                                        date_of_birth__month=month,
                                        date_of_birth__year=year,
                                    )
                            elif len(year_part) <= 3:
                                # Частичный год (г, гг, ггг) - ищем через LIKE
                                # Для PostgreSQL используем to_char
                                pattern = f"{year_part}%"
                                patients = Patient.objects.extra(
                                    where=[
                                        "EXTRACT(DAY FROM date_of_birth) = %s AND "
                                        "EXTRACT(MONTH FROM date_of_birth) = %s AND "
                                        "to_char(date_of_birth, 'YYYY') LIKE %s"
                                    ],
                                    params=[day, month, pattern],
                                )
                                word_query |= Q(id__in=patients.values("id"))
                    except (ValueError, IndexError):
                        pass

            # 3. Поиск по формату "день.месяц" (04.03)
            elif "." in word and word.count(".") == 1:
                parts = word.split(".")
                if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                    try:
                        day = int(parts[0])
                        month = int(parts[1])
                        if 1 <= day <= 31 and 1 <= month <= 12:
                            word_query |= Q(
                                date_of_birth__day=day, date_of_birth__month=month
                            )
                    except ValueError:
                        pass

            # 4. Поиск по году (4 цифры или 1-3 цифры)
            if word.isdigit() and len(word) <= 4:
                # Для полного года (4 цифры)
                if len(word) == 4:
                    try:
                        year = int(word)
                        if 1900 <= year <= 2100:
                            word_query |= Q(date_of_birth__year=year)
                    except ValueError:
                        pass
                # Для части года (1-3 цифры) - ищем год, который начинается с этих цифр
                else:
                    patients = Patient.objects.extra(
                        where=["to_char(date_of_birth, 'YYYY') LIKE %s"],
                        params=[f"{word}%"],
                    )
                    word_query |= Q(id__in=patients.values("id"))

            # 5. Поиск по месяцу (число 1-12)
            if word.isdigit() and 1 <= int(word) <= 12:
                word_query |= Q(date_of_birth__month=int(word))

            # 6. Поиск по дню (число 1-31)
            if word.isdigit() and 1 <= int(word) <= 31:
                word_query |= Q(date_of_birth__day=int(word))

            # 7. Простой поиск по вхождению в строковое представление даты
            # (для случаев когда не распознали как дату, но есть цифры)
            if any(char.isdigit() for char in word):
                # Ищем вхождение слова в строку формата "дд.мм.гггг"
                patients = Patient.objects.extra(
                    where=["to_char(date_of_birth, 'DD.MM.YYYY') LIKE %s"],
                    params=[f"%{word}%"],
                )
                word_query |= Q(id__in=patients.values("id"))

            # Добавляем условия в основной запрос
            if word_query:
                query &= word_query

        # Если нет условий
        if query == Q():
            query = Q(surname__icontains=search_query) | Q(
                first_name__icontains=search_query
            )

        # Выполняем поиск
        patients = Patient.objects.filter(query).distinct()

        # Подсчитываем общее количество
        total_count = patients.count()

        # Берем результаты с разумным ограничением
        patients = patients[:200]

        # Формируем ответ
        patients_list = []
        for patient in patients:
            patients_list.append(
                {
                    "id": patient.id,
                    "surname": patient.surname,
                    "first_name": patient.first_name,
                    "last_name": patient.last_name or "",
                    "full_name": patient.get_full_name(),
                    "detail_url": reverse(
                        "patients:patient_detail", kwargs={"pk": patient.id}
                    ),
                    "update_url": reverse(
                        "patients:patient_update", kwargs={"pk": patient.id}
                    ),
                    "card_number": patient.card_number,
                    "card_number_IP": patient.card_number_IP,
                    "card_number_OMS": patient.card_number_OMS,
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
                "total_count": total_count,
                "patients": patients_list,
            }
        )

    except Exception as e:
        import traceback

        print(f"Ошибка при поиске: {e}")
        print(traceback.format_exc())
        return JsonResponse({"error": f"Ошибка при поиске: {str(e)}"}, status=500)


@medical_admin_or_admin_required
def get_max_card_number(request):
    """API для получения максимального номера карты"""
    card_type = request.GET.get("type", "regular")

    max_number = CardNumberService.get_max_card_number(card_type)
    return JsonResponse(
        {
            "max_card_number": max_number,
            "next_number": max_number + 1 if max_number else 1,
            "card_type": card_type,
        }
    )


@medical_admin_or_admin_required
def generate_new_card_number(request, card_type="regular"):
    """API для генерации нового номера карты указанного типа"""
    valid_types = ["regular", "ip", "oms"]

    if card_type not in valid_types:
        return JsonResponse(
            {
                "error": f"Неверный тип карты. Допустимые значения: {', '.join(valid_types)}"
            },
            status=400,
        )

    new_number = CardNumberService.get_next_card_number(card_type)

    # Определяем русское название типа карты для сообщения
    type_names = {"regular": "обычной карты", "ip": "карты ИП", "oms": "карты ОМС"}

    return JsonResponse(
        {
            "new_card_number": new_number,
            "card_type": card_type,
            "message": f"Сгенерирован новый номер {type_names[card_type]}: {new_number}",
        }
    )
