from datetime import datetime, timedelta

from django.contrib import messages
from django.db import transaction

from .models import TimeSlot


class TimeSlotService:
    """Сервис для работы с временными слотами"""

    @staticmethod
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
        """Создание временных слотов"""

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

    @staticmethod
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


class CopyScheduleService:
    """Сервис для копирования расписания"""

    @staticmethod
    def copy_weekly_schedule(
        source_week_start,
        target_week_start,
        days_to_copy,
        copy_type="all",
        cabinets=None,
        doctors=None,
        conflict_resolution="skip",
        user=None,
        request=None,
    ):
        """
        Копирует расписание с одной недели на другую по выбранным дням

        Пример:
        - source_week_start = 2025-12-08 (Пн)
        - target_week_start = 2026-01-12 (Пн)
        - days_to_copy = [0, 2, 4] (Пн, Ср, Пт)

        Результат:
        - Копирует Пн 2025-12-08 → Пн 2026-01-12
        - Копирует Ср 2025-12-10 → Ср 2026-01-14
        - Копирует Пт 2025-12-12 → Пт 2026-01-16
        """
        try:
            with transaction.atomic():
                created_count = 0
                skipped_count = 0
                days_copied = 0

                for day_offset in days_to_copy:
                    # Вычисляем даты для конкретного дня недели
                    source_date = source_week_start + timedelta(days=day_offset)
                    target_date = target_week_start + timedelta(days=day_offset)

                    # Проверяем, есть ли расписание на источник
                    if not TimeSlot.objects.filter(date=source_date).exists():
                        continue

                    # Копируем с одного дня на другой
                    day_result = CopyScheduleService.copy_schedule(
                        source_date=source_date,
                        target_date=target_date,
                        copy_type=copy_type,
                        cabinets=cabinets,
                        doctors=doctors,
                        conflict_resolution=conflict_resolution,
                        user=user,
                        request=request,
                    )

                    if day_result["success"]:
                        created_count += day_result.get("created_count", 0)
                        skipped_count += day_result.get("skipped_count", 0)
                        days_copied += 1

                return {
                    "success": True,
                    "created_count": created_count,
                    "skipped_count": skipped_count,
                    "days_copied": days_copied,
                    "source_week": source_week_start,
                    "target_week": target_week_start,
                    "days_copied_list": days_to_copy,
                }

        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def copy_schedule(
        source_date,
        target_date,
        copy_type="all",
        cabinets=None,
        doctors=None,
        conflict_resolution="skip",
        user=None,
        request=None,
    ):
        """Копирует расписание с одной даты на другую"""
        try:
            with transaction.atomic():
                # Получаем слоты для копирования
                source_slots = TimeSlot.objects.filter(date=source_date)

                # Фильтруем по типу копирования
                if copy_type == "by_cabinet" and cabinets:
                    source_slots = source_slots.filter(cabinet__in=cabinets)
                elif copy_type == "by_doctor" and doctors:
                    source_slots = source_slots.filter(doctor__in=doctors)

                # Обрабатываем конфликты на целевой дате
                if conflict_resolution == "override":
                    # Удаляем существующие слоты для этих врачей/кабинетов
                    for slot in source_slots:
                        TimeSlot.objects.filter(
                            date=target_date,
                            cabinet=slot.cabinet,
                            doctor=slot.doctor,
                            start_time__lt=slot.end_time,
                            end_time__gt=slot.start_time,
                        ).delete()

                # Создаем копии слотов
                created_count = 0
                skipped_count = 0

                for source_slot in source_slots:
                    # Проверяем, существует ли уже такой слот
                    if conflict_resolution == "skip":
                        existing_slot = TimeSlot.objects.filter(
                            date=target_date,
                            cabinet=source_slot.cabinet,
                            doctor=source_slot.doctor,
                            start_time=source_slot.start_time,
                            end_time=source_slot.end_time,
                        ).exists()

                        if existing_slot:
                            skipped_count += 1
                            continue

                    # Проверяем, нет ли пересечений
                    conflicting_slots = TimeSlot.objects.filter(
                        date=target_date,
                        cabinet=source_slot.cabinet,
                        doctor=source_slot.doctor,
                        start_time__lt=source_slot.end_time,
                        end_time__gt=source_slot.start_time,
                    ).exists()

                    if conflicting_slots:
                        skipped_count += 1
                        continue

                    # Создаем новый слот
                    new_slot = TimeSlot(
                        date=target_date,
                        cabinet=source_slot.cabinet,
                        doctor=source_slot.doctor,
                        start_time=source_slot.start_time,
                        end_time=source_slot.end_time,
                        slot_type=source_slot.slot_type,
                        description=source_slot.description,
                    )

                    new_slot.save()
                    created_count += 1

                # Копируем комментарий дня
                from .models import DayComment

                try:
                    source_comment = DayComment.objects.get(date=source_date)
                    DayComment.objects.update_or_create(
                        date=target_date, defaults={"comment": source_comment.comment}
                    )
                except DayComment.DoesNotExist:
                    pass

                return {
                    "success": True,
                    "created_count": created_count,
                    "skipped_count": skipped_count,
                    "source_slots_count": source_slots.count(),
                }

        except Exception as e:
            return {"success": False, "error": str(e)}
