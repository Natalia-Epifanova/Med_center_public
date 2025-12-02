from django.db import transaction
from django.core.exceptions import ValidationError
from .models import TimeSlot, Appointment, Cabinet, Doctor
from patients.models import Patient
from .validators import PatientValidator, AppointmentValidator
from datetime import datetime, timedelta


class PatientService:
    """Сервис для работы с пациентами"""

    @staticmethod
    @transaction.atomic
    def get_or_create_patient(patient_data):
        """Создание или поиск пациента"""
        surname = patient_data.get("surname")
        first_name = patient_data.get("first_name")
        date_of_birth = patient_data.get("date_of_birth")

        # Валидация обязательных полей
        PatientValidator.validate_patient_required_fields(surname, first_name)

        # Поиск существующего пациента
        if surname and first_name and date_of_birth:
            existing_patient = Patient.objects.filter(
                surname__iexact=surname,
                first_name__iexact=first_name,
                date_of_birth=date_of_birth,
            ).first()

            if existing_patient:
                return existing_patient, False

        # Создание нового пациента
        patient = Patient.objects.create(**patient_data)
        return patient, True

    @staticmethod
    def clean_patient_data(patient_data):
        """Очистка и валидация данных пациента"""
        cleaned_data = patient_data.copy()

        # Валидация телефона
        if cleaned_data.get("phone_number"):
            cleaned_data["phone_number"] = PatientValidator.validate_phone_number(
                cleaned_data["phone_number"]
            )

        return cleaned_data


class AppointmentService:
    """Сервис для работы с записями на прием"""

    @staticmethod
    @transaction.atomic
    def create_procedural_appointment(main_appointment):
        """Создание записи в процедурном кабинете"""
        procedural_cabinet = Cabinet.objects.get(number=6)
        nurse_doctor = (
            Doctor.objects.filter(specialization="nurse").first()
            or main_appointment.doctor
        )

        # Проверка конфликтов
        conflicting_slots = TimeSlot.get_conflicting_slots(
            date=main_appointment.time_slot.date,
            start_time=main_appointment.time_slot.start_time,
            end_time=main_appointment.time_slot.end_time,
            cabinet=procedural_cabinet,
        ).filter(appointments__isnull=False)

        if conflicting_slots.exists():
            raise ValidationError(
                "Выбранное время в процедурном кабинете уже занято. "
                "Пожалуйста, выберите другое время."
            )

        # Создание слота
        procedural_slot = TimeSlot.objects.create(
            date=main_appointment.time_slot.date,
            cabinet=procedural_cabinet,
            doctor=nurse_doctor,
            start_time=main_appointment.time_slot.start_time,
            end_time=main_appointment.time_slot.end_time,
            slot_type="working",
            description="Процедурный кабинет",
        )

        # Создание записи
        procedural_appointment = Appointment.objects.create(
            time_slot=procedural_slot,
            patient=main_appointment.patient,
            service=main_appointment.service,
            insurance_type=main_appointment.insurance_type,
            status=main_appointment.status,
            comment=main_appointment.doctor.surname,
            is_consecutive=True,
            previous_appointment=main_appointment,
        )

        return procedural_appointment

    @staticmethod
    def can_create_procedural_appointment(main_appointment):
        """Проверка возможности создания процедурной записи"""
        try:
            procedural_cabinet = Cabinet.objects.get(number=6)

            occupied_conflicting_slots = TimeSlot.get_conflicting_slots(
                date=main_appointment.time_slot.date,
                start_time=main_appointment.time_slot.start_time,
                end_time=main_appointment.time_slot.end_time,
                cabinet=procedural_cabinet,
            ).filter(appointments__isnull=False)

            return not occupied_conflicting_slots.exists()

        except Exception:
            return False

    @staticmethod
    def create_consecutive_appointment(
        main_appointment, appointment_type, next_slot, additional_service=None
    ):
        """Создание последовательной записи"""
        if appointment_type == "additional":
            return Appointment(
                time_slot=next_slot,
                patient=main_appointment.patient,
                service=additional_service,
                insurance_type=main_appointment.insurance_type,
                status=main_appointment.status,
                is_consecutive=True,
                previous_appointment=main_appointment,
                comment=f"Последовательная запись к {main_appointment.service.name}",
            )
        elif appointment_type == "two_slots":
            return Appointment(
                time_slot=next_slot,
                patient=main_appointment.patient,
                service=main_appointment.service,
                insurance_type=main_appointment.insurance_type,
                status=main_appointment.status,
                is_consecutive=True,
                previous_appointment=main_appointment,
                occupies_two_slots=True,
                comment=f"Продолжение услуги {main_appointment.service.name} (занято 2 слота)",
            )
        return None


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


from datetime import datetime, timedelta
from django.db import transaction
from django.contrib import messages
from .models import TimeSlot


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
