from django import forms
from django.core.exceptions import ValidationError
from django.db import transaction

from appointments.models import Appointment, AppointmentChain
from timetable.models import Cabinet, Doctor, TimeSlot, MedicalService


class AppointmentChainService:
    """Сервис для работы с цепочками записей к разным врачам"""

    @staticmethod
    def validate_additional_appointment(
        doctor, service, time_slot, current_appointment_id=None
    ):
        """Валидация данных дополнительной записи"""
        errors = []

        # Проверка, что услуга доступна врачу
        from timetable.utils import get_doctor_services

        available_services = get_doctor_services(doctor)
        if not available_services.filter(id=service.id).exists():
            errors.append(f"Услуга '{service.name}' недоступна врачу {doctor.surname}")

        # Проверка доступности слота
        if not time_slot.is_available(exclude_appointment_id=current_appointment_id):
            errors.append(f"Время {time_slot.start_time} уже занято")

        # Проверка, что слот принадлежит врачу
        if time_slot.doctor != doctor:
            errors.append("Выбранный слот не принадлежит указанному врачу")

        return errors

    @staticmethod
    @transaction.atomic
    def create_chain_from_form(main_appointment, additional_appointments_data):
        """Создает цепочку записей на основе данных формы"""
        created_appointments = []

        for i, appointment_data in enumerate(additional_appointments_data, start=1):
            try:
                # Получаем объекты
                doctor = Doctor.objects.get(id=appointment_data["doctor_id"])
                service = MedicalService.objects.get(id=appointment_data["service_id"])
                time_slot = TimeSlot.objects.get(id=appointment_data["time_slot_id"])
                comment = appointment_data.get("comment", "")

                # Создаем запись
                appointment = Appointment.objects.create(
                    time_slot=time_slot,
                    patient=main_appointment.patient,
                    service=service,
                    insurance_type=main_appointment.insurance_type,
                    status=main_appointment.status,
                    comment=comment or f"Связанная запись с #{main_appointment.id}",
                    chain_type=Appointment.ChainType.MULTIPLE_DOCTORS,
                )

                # Сохраняем цену
                appointment.price_at_appointment = service.price
                appointment.total_with_blood_tests = service.price
                appointment.save()

                # Создаем связь
                AppointmentChain.objects.create(
                    main_appointment=main_appointment,
                    related_appointment=appointment,
                    chain_type=AppointmentChain.ChainType.ANOTHER_DOCTOR,
                    order=i,
                )

                created_appointments.append(appointment)

            except Exception as e:
                # Откатываем все созданные записи при ошибке
                for app in created_appointments:
                    app.delete()
                raise forms.ValidationError(
                    f"Ошибка создания дополнительной записи #{i}: {str(e)}"
                )

        # Обновляем тип цепочки основной записи
        if created_appointments:
            main_appointment.chain_type = Appointment.ChainType.MULTIPLE_DOCTORS
            main_appointment.save()

        return created_appointments

    @staticmethod
    def get_available_doctors(exclude_doctor=None):
        """Получить список доступных врачей (исключая текущего если нужно)"""
        doctors = Doctor.objects.filter(is_active=True).order_by("surname")

        if exclude_doctor:
            doctors = doctors.exclude(id=exclude_doctor.id)

        return doctors


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

    @staticmethod
    def get_available_slots_for_doctor(doctor, date, exclude_slot_id=None):
        """Получить доступные слоты для врача на указанную дату"""
        from timetable.models import TimeSlot

        # Получаем все рабочие слоты врача на дату
        slots = TimeSlot.objects.filter(
            doctor=doctor, date=date, slot_type="working"
        ).order_by("start_time")

        # Фильтруем доступные слоты
        available_slots = []
        for slot in slots:
            # Проверяем доступность с исключением
            if slot.is_available(exclude_slot_id=exclude_slot_id):
                available_slots.append(slot)

        return available_slots
