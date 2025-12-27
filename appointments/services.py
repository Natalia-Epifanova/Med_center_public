from django import forms
from django.core.exceptions import ValidationError
from django.db import transaction

from appointments.models import Appointment, AppointmentChain
from appointments.utils import get_cached_doctor_services, get_procedural_cabinet
from timetable.models import Cabinet, Doctor, MedicalService, TimeSlot


class AppointmentChainService:
    """Сервис для работы с цепочками записей к разным врачам"""

    @staticmethod
    def validate_additional_appointment(
        doctor, service, time_slot, current_appointment_id=None
    ):
        """Валидация данных дополнительной записи"""
        errors = []

        available_services = get_cached_doctor_services(doctor)
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
        procedural_cabinet = get_procedural_cabinet()
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
            procedural_cabinet = get_procedural_cabinet()

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

    @staticmethod
    def initialize_service_queryset(form, doctor, current_service=None):
        """Инициализирует queryset услуг для формы с учетом врача"""
        from timetable.utils import get_doctor_services

        if doctor:
            services = get_doctor_services(doctor, current_service)
            form.fields["service"].queryset = services

            # Также обновляем queryset для additional_service если есть такое поле
            if "additional_service" in form.fields:
                form.fields["additional_service"].queryset = services

            return True
        else:
            form.fields["service"].queryset = MedicalService.objects.none()
            if "additional_service" in form.fields:
                form.fields["additional_service"].queryset = (
                    MedicalService.objects.none()
                )
            return False

    @staticmethod
    def get_doctor_for_form(form_instance):
        """Получает объект врача для формы из разных источников"""
        # Пытаемся получить врача в порядке приоритета
        if hasattr(form_instance, "time_slot") and form_instance.time_slot:
            return form_instance.time_slot.doctor
        elif hasattr(form_instance, "doctor") and form_instance.doctor:
            return form_instance.doctor
        elif (
            hasattr(form_instance, "current_appointment")
            and form_instance.current_appointment
        ):
            return form_instance.current_appointment.doctor
        return None


class ProceduralAppointmentService:
    """Сервис для работы с процедурными записями"""

    @staticmethod
    def get_procedural_cabinet():
        """Получает процедурный кабинет (№6)"""
        try:
            return Cabinet.objects.get(number=6)
        except Cabinet.DoesNotExist:
            raise ValidationError("Процедурный кабинет №6 не найден в системе")

    @staticmethod
    def get_nurse_doctor():
        """Получает врача-медсестру или возвращает врача по умолчанию"""
        nurse_doctor = Doctor.objects.filter(specialization="nurse").first()
        return nurse_doctor

    @staticmethod
    def create_or_get_procedural_slot(date, start_time, end_time, doctor=None):
        """Создает или находит существующий слот в процедурном кабинете"""
        procedural_cabinet = ProceduralAppointmentService.get_procedural_cabinet()
        nurse_doctor = ProceduralAppointmentService.get_nurse_doctor() or doctor

        time_slot = TimeSlot.objects.filter(
            date=date,
            cabinet=procedural_cabinet,
            doctor=nurse_doctor,
            start_time=start_time,
            end_time=end_time,
            slot_type="working",
        ).first()

        if not time_slot:
            time_slot = TimeSlot.objects.create(
                date=date,
                cabinet=procedural_cabinet,
                doctor=nurse_doctor,
                start_time=start_time,
                end_time=end_time,
                slot_type="working",
                description="Процедурный кабинет - индивидуальная запись",
            )

        return time_slot

    @staticmethod
    def create_procedural_appointment(main_appointment):
        """Создание записи в процедурном кабинете для основной записи"""
        from .models import Appointment

        procedural_cabinet = ProceduralAppointmentService.get_procedural_cabinet()
        nurse_doctor = (
            ProceduralAppointmentService.get_nurse_doctor() or main_appointment.doctor
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
            procedural_cabinet = ProceduralAppointmentService.get_procedural_cabinet()

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
    def update_procedural_appointment(main_appointment, existing_procedural):
        """Обновляет существующую процедурную запись на новое время"""
        procedural_cabinet = ProceduralAppointmentService.get_procedural_cabinet()
        nurse_doctor = (
            ProceduralAppointmentService.get_nurse_doctor() or main_appointment.doctor
        )

        # Проверяем, нужно ли создавать новый слот или использовать существующий
        new_procedural_slot = TimeSlot.objects.filter(
            date=main_appointment.time_slot.date,
            cabinet=procedural_cabinet,
            start_time=main_appointment.time_slot.start_time,
            end_time=main_appointment.time_slot.end_time,
            slot_type="working",
        ).first()

        if not new_procedural_slot:
            # Создаем новый слот в процедурном кабинете
            new_procedural_slot = TimeSlot.objects.create(
                date=main_appointment.time_slot.date,
                cabinet=procedural_cabinet,
                doctor=nurse_doctor,
                start_time=main_appointment.time_slot.start_time,
                end_time=main_appointment.time_slot.end_time,
                slot_type="working",
                description=f"Процедурный кабинет - {main_appointment.doctor.surname}",
            )

        # Обновляем процедурную запись
        existing_procedural.time_slot = new_procedural_slot
        existing_procedural.service = main_appointment.service
        existing_procedural.insurance_type = main_appointment.insurance_type
        existing_procedural.status = main_appointment.status
        existing_procedural.comment = main_appointment.doctor.surname

        # ВАЖНО: Сохраняем сумму
        if not existing_procedural.price_at_appointment:
            existing_procedural.price_at_appointment = existing_procedural.service.price
        existing_procedural.total_with_blood_tests = (
            existing_procedural.price_at_appointment
        )

        existing_procedural.save()
        return existing_procedural

    @staticmethod
    def create_procedural_for_appointment(appointment, main_appointment=None):
        """Создает процедурную запись для указанной записи"""
        from .models import AppointmentChain

        if not ProceduralAppointmentService.can_create_procedural_appointment(
            appointment
        ):
            return None

        procedural_appointment = (
            ProceduralAppointmentService.create_procedural_appointment(appointment)
        )

        if procedural_appointment:
            if not procedural_appointment.price_at_appointment:
                procedural_appointment.price_at_appointment = (
                    procedural_appointment.service.price
                )
            procedural_appointment.total_with_blood_tests = (
                procedural_appointment.price_at_appointment
            )
            procedural_appointment.save()

            # Определяем главную запись для связи
            chain_main = main_appointment if main_appointment else appointment

            # Создаем связь в цепочке
            AppointmentChain.objects.create(
                main_appointment=chain_main,
                related_appointment=procedural_appointment,
                chain_type=AppointmentChain.ChainType.PROCEDURAL,
                order=1,
            )

            return procedural_appointment

        return None


class ConsecutiveAppointmentService:
    """Сервис для работы с последовательными записями у одного врача"""

    @staticmethod
    @transaction.atomic
    def create_consecutive_appointment(
        main_appointment,
        appointment_chain_type,
        additional_service=None,
        needs_procedural_additional=False,
    ):
        """Создание последовательной записи у того же врача"""
        from django.core.exceptions import ValidationError

        next_slot = main_appointment.time_slot.get_next_consecutive_slot()

        if not next_slot:
            raise ValidationError(
                "Нет следующего временного слота для последовательной записи"
            )

        if not next_slot.is_available():
            raise ValidationError("Следующий временной слот уже занят")

        try:
            if appointment_chain_type == "additional":
                if not additional_service:
                    raise ValidationError(
                        "Для дополнительной услуги необходимо выбрать услугу"
                    )

                # Проверяем, нужно ли создать процедурную запись
                if needs_procedural_additional:
                    # Проверяем доступность процедурного кабинета
                    if not ProceduralAppointmentService.can_create_procedural_appointment(
                        main_appointment  # Проверяем для основной записи, так как время то же
                    ):
                        raise ValidationError(
                            "Выбранное время в процедурном кабинете уже занято. "
                            "Невозможно создать процедурную запись для второй услуги."
                        )

                # Создаем последовательную запись
                consecutive_appointment = Appointment.objects.create(
                    time_slot=next_slot,
                    patient=main_appointment.patient,
                    service=additional_service,
                    insurance_type=main_appointment.insurance_type,
                    status=main_appointment.status,
                    is_consecutive=True,
                    comment=f"Последовательная запись к {main_appointment.service.name}",
                    chain_type=Appointment.ChainType.SAME_DOCTOR,
                )

                # Сохраняем цену (используем общий метод)
                ConsecutiveAppointmentService._save_appointment_price(
                    consecutive_appointment
                )

                # Создаем связь в цепочке
                AppointmentChain.objects.create(
                    main_appointment=main_appointment,
                    related_appointment=consecutive_appointment,
                    chain_type=AppointmentChain.ChainType.SAME_DOCTOR_ADDITIONAL,
                    order=1,
                )

                # СОЗДАЕМ ПРОЦЕДУРНУЮ ЗАПИСЬ ЕСЛИ НУЖНО
                if needs_procedural_additional:

                    # Создаем процедурную запись через сервис
                    procedural_appointment = (
                        ProceduralAppointmentService.create_procedural_for_appointment(
                            consecutive_appointment,
                            main_appointment=consecutive_appointment,
                        )
                    )

                    if procedural_appointment:
                        # Сохраняем цену процедурной записи (используем общий метод)
                        ConsecutiveAppointmentService._save_appointment_price(
                            procedural_appointment
                        )

                return consecutive_appointment

            elif appointment_chain_type == "two_slots":
                consecutive_appointment = Appointment.objects.create(
                    time_slot=next_slot,
                    patient=main_appointment.patient,
                    service=main_appointment.service,
                    insurance_type=main_appointment.insurance_type,
                    status=main_appointment.status,
                    is_consecutive=True,
                    occupies_two_slots=True,
                    comment=f"Продолжение услуги {main_appointment.service.name} (занято 2 слота)",
                    chain_type=Appointment.ChainType.SAME_DOCTOR,
                )

                # Сохраняем цену (используем общий метод)
                ConsecutiveAppointmentService._save_appointment_price(
                    consecutive_appointment
                )

                # Создаем связь в цепочке
                AppointmentChain.objects.create(
                    main_appointment=main_appointment,
                    related_appointment=consecutive_appointment,
                    chain_type=AppointmentChain.ChainType.SAME_DOCTOR_TWO_SLOTS,
                    order=1,
                )

                return consecutive_appointment

            else:
                raise ValidationError(
                    f"Неизвестный тип последовательной записи: {appointment_chain_type}"
                )

        except ValidationError:
            # Пробрасываем ValidationError дальше
            raise
        except Exception as e:
            raise ValidationError(
                f"Ошибка при создании последовательной записи: {str(e)}"
            )

    @staticmethod
    def _save_appointment_price(appointment):
        """
        Сохраняет цену для записи на прием.

        Args:
            appointment (Appointment): Объект записи на прием
        """
        # Сохраняем цену услуги на момент записи, если еще не сохранена
        if not appointment.price_at_appointment:
            appointment.price_at_appointment = appointment.service.price

        # Устанавливаем общую сумму (пока без анализов крови)
        appointment.total_with_blood_tests = appointment.price_at_appointment

        # Сохраняем изменения
        appointment.save()


class CommonAppointmentService:
    """Общие методы для работы с записями (обычными и процедурными)"""

    @staticmethod
    def validate_additional_appointments(appointments_list, exclude_doctor_id=None):
        """Валидация дополнительных записей (общий метод)"""

        errors = []

        for i, appointment_data in enumerate(appointments_list, start=1):
            try:
                doctor = Doctor.objects.get(id=appointment_data["doctor_id"])
                service = MedicalService.objects.get(id=appointment_data["service_id"])
                time_slot = TimeSlot.objects.get(id=appointment_data["time_slot_id"])

                # ИСПРАВЛЕНИЕ: Используем существующую функцию
                available_services = get_cached_doctor_services(doctor)
                if not available_services.filter(id=service.id).exists():
                    errors.append(
                        f"Ошибка в записи #{i}: Услуга '{service.name}' недоступна врачу {doctor.surname}"
                    )

                # Проверяем доступность слота
                if not time_slot.is_available():
                    errors.append(
                        f"Ошибка в записи #{i}: Время {time_slot.start_time} у врача {doctor.surname} уже занято"
                    )

                # Проверка исключения врача
                if exclude_doctor_id and doctor.id == exclude_doctor_id:
                    errors.append(
                        f"Ошибка в записи #{i}: Нельзя создать запись к тому же врачу"
                    )

            except (
                Doctor.DoesNotExist,
                MedicalService.DoesNotExist,
                TimeSlot.DoesNotExist,
            ) as e:
                errors.append(f"Ошибка в записи #{i}: {str(e)}")

        return errors
