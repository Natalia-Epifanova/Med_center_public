from datetime import datetime, timedelta

from django.http import JsonResponse
from django.views.decorators.http import require_GET

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
