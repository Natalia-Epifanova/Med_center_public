from datetime import datetime, timedelta

from django.db import transaction

from timetable.models import TimeSlot


def create_time_slots(
    date,
    cabinet,
    doctor,
    start_time,
    end_time,
    interval,
    slot_type="working",
    description="",
):
    """Утилита для создания временных слотов"""
    created_slots = []
    current_time = start_time

    while current_time < end_time:
        end_time_slot = (
            datetime.combine(date, current_time) + timedelta(minutes=interval)
        ).time()
        if end_time_slot > end_time:
            break

        slot = TimeSlot(
            date=date,
            cabinet=cabinet,
            doctor=doctor,
            start_time=current_time,
            end_time=end_time_slot,
            slot_type=slot_type,
            description=description,
        )
        created_slots.append(slot)
        current_time = end_time_slot

    return created_slots


def save_slots_with_conflict_check(slots):
    """Сохранение слотов с проверкой конфликтов"""
    saved_count = 0
    for slot in slots:
        conflicting_slots = TimeSlot.objects.filter(
            date=slot.date,
            cabinet=slot.cabinet,
            start_time__lt=slot.end_time,
            end_time__gt=slot.start_time,
        )
        if not conflicting_slots.exists():
            slot.save()
            saved_count += 1
    return saved_count
