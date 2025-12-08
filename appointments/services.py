from django.core.exceptions import ValidationError
from django.db import transaction

from appointments.models import Appointment
from timetable.models import Cabinet, Doctor, TimeSlot


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
