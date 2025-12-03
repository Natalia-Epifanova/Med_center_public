from datetime import datetime, timedelta
from django.db import transaction
from django.contrib import messages
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
        """
        Копирует расписание с одной даты на другую
        """
        try:
            with transaction.atomic():
                # Получаем слоты для копирования
                source_slots = TimeSlot.objects.filter(date=source_date)

                # Фильтруем по типу копирования
                if copy_type == "by_cabinet" and cabinets:
                    source_slots = source_slots.filter(cabinet__in=cabinet)
                elif copy_type == "by_doctor" and doctors:
                    source_slots = source_slots.filter(doctor__in=doctors)

                # Обрабатываем конфликты на целевой дате
                target_slots_count = TimeSlot.objects.filter(date=target_date).count()

                if target_slots_count > 0:
                    if conflict_resolution == "delete_and_create":
                        # Удаляем все слоты на целевой дате
                        deleted_count = TimeSlot.objects.filter(
                            date=target_date
                        ).delete()[0]
                        if request:
                            messages.info(
                                request,
                                f"Удалено {deleted_count} слотов на целевой дате",
                            )
                    elif conflict_resolution == "override":
                        # Удаляем только те слоты, которые будем заменять
                        for slot in source_slots:
                            TimeSlot.objects.filter(
                                date=target_date,
                                cabinet=slot.cabinet,
                                doctor=slot.doctor,
                                start_time=slot.start_time,
                                end_time=slot.end_time,
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

                    # Проверяем конфликты перед сохранением
                    if not new_slot.is_time_available(cabinet=new_slot.cabinet):
                        if conflict_resolution != "override":
                            skipped_count += 1
                            continue

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

    @staticmethod
    def copy_weekly_pattern(
        start_date, end_date, pattern_days, user=None, request=None
    ):
        """
        Копирует расписание по шаблону недели
        pattern_days: список дней недели (0-понедельник, 6-воскресенье)
        """
        try:
            results = []
            current_date = start_date

            while current_date <= end_date:
                if current_date.weekday() in pattern_days:
                    # Копируем с ближайшего понедельника (или другого дня недели)
                    source_date = current_date - timedelta(days=current_date.weekday())

                    # Проверяем, есть ли расписание на источник
                    if TimeSlot.objects.filter(date=source_date).exists():
                        result = CopyScheduleService.copy_schedule(
                            source_date=source_date,
                            target_date=current_date,
                            copy_type="all",
                            conflict_resolution="skip",
                            user=user,
                            request=request,
                        )
                        results.append({"date": current_date, "result": result})

                current_date += timedelta(days=1)

            return {
                "success": True,
                "results": results,
                "total_days_processed": len(results),
            }

        except Exception as e:
            return {"success": False, "error": str(e)}
