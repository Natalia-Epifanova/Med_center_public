import json
from datetime import datetime, timedelta

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from timetable.models import TimeSlot
from users.permissions.decorators import admin_required


@require_GET
@admin_required
def week_schedule_preview(request):
    """API для предпросмотра копирования недели"""
    try:
        source_date_str = request.GET.get("source")
        target_date_str = request.GET.get("target")
        days_str = request.GET.get("days", "")

        if not all([source_date_str, target_date_str, days_str]):
            return JsonResponse({"success": False, "error": "Missing parameters"})

        source_date = datetime.strptime(source_date_str, "%Y-%m-%d").date()
        target_date = datetime.strptime(target_date_str, "%Y-%m-%d").date()
        days = [int(day) for day in days_str.split(",") if day]

        days_data = []
        for day in days:
            source_day = source_date + timedelta(days=day)
            target_day = target_date + timedelta(days=day)

            slot_count = TimeSlot.objects.filter(date=source_day).count()
            existing_slots = TimeSlot.objects.filter(date=target_day).count()

            days_data.append(
                {
                    "day": day,
                    "source_date": source_day.isoformat(),
                    "target_date": target_day.isoformat(),
                    "slot_count": slot_count,
                    "existing_slots": existing_slots,
                    "has_schedule": slot_count > 0,
                }
            )

        return JsonResponse(
            {
                "success": True,
                "days": days_data,
                "source_week": source_date.isoformat(),
                "target_week": target_date.isoformat(),
                "total_slots": sum(day["slot_count"] for day in days_data),
            }
        )

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})


@login_required
@require_POST
@admin_required  # если у вас есть такой декоратор
def delete_all_doctor_slots(request):
    """Удаление всех слотов врача в определенном кабинете на день"""
    try:
        data = json.loads(request.body)
        doctor_id = data.get("doctor_id")
        cabinet_id = data.get("cabinet_id")
        date_str = data.get("date")

        if not all([doctor_id, cabinet_id, date_str]):
            return JsonResponse({"error": "Не все параметры указаны"}, status=400)

        # Преобразуем дату
        date = timezone.datetime.strptime(date_str, "%Y-%m-%d").date()

        # Проверяем, что дата не в прошлом (опционально)
        if date < timezone.now().date() and not request.user.is_superuser:
            return JsonResponse(
                {"error": "Нельзя удалять слоты на прошедшие даты"}, status=403
            )

        # Находим и удаляем все слоты
        slots = TimeSlot.objects.filter(
            doctor_id=doctor_id,
            cabinet_id=cabinet_id,
            date=date,
            slot_type="working",  # можно удалить эту строку, если нужно удалять и перерывы
        )

        deleted_count = slots.count()

        # Проверяем, есть ли активные записи на эти слоты
        from appointments.models import Appointment

        appointments = Appointment.objects.filter(
            time_slot__in=slots, status__in=["scheduled", "confirmed"]
        )

        if appointments.exists():
            return JsonResponse(
                {
                    "error": f"Нельзя удалить слоты с активными записями ({appointments.count()} записей)"
                },
                status=400,
            )

        # Удаляем слоты
        slots.delete()

        return JsonResponse(
            {
                "success": True,
                "deleted_count": deleted_count,
                "message": f"Удалено {deleted_count} слотов",
            }
        )

    except json.JSONDecodeError:
        return JsonResponse({"error": "Неверный формат данных"}, status=400)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
