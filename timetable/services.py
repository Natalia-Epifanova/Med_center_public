from django.db import transaction
from django.core.exceptions import ValidationError
from .models import Patient, TimeSlot, Appointment, Cabinet, Doctor
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
