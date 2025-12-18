from django.db import transaction

from appointments.forms.base import AppointmentBaseForm
from appointments.models import Appointment, AppointmentBloodTest, AppointmentChain
from appointments.services import (
    AppointmentService,
    ProceduralAppointmentService,
    ConsecutiveAppointmentService,
)
from patients.services import PatientService
from timetable.models import BloodTest, MedicalService, TimeSlot, Doctor
import json
from django import forms
from django.utils import timezone
from django.core.exceptions import ValidationError


class AppointmentForm(AppointmentBaseForm):
    """Форма создания записи с возможностью изменения времени"""

    # Добавляем поля для изменения времени
    allow_time_change = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.HiddenInput(attrs={"id": "id_allow_time_change"}),
        label="Разрешить изменение времени",
    )
    new_time_slot_id = forms.IntegerField(
        required=False,
        widget=forms.HiddenInput(attrs={"id": "id_new_time_slot_id"}),
        label="Новый временной слот",
    )
    new_appointment_date = forms.DateField(
        required=False,
        widget=forms.HiddenInput(attrs={"id": "id_new_appointment_date"}),
        label="Новая дата приема",
    )
    needs_procedural_additional = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.HiddenInput(attrs={"id": "id_needs_procedural_additional"}),
        label="Процедурный кабинет для второй услуги",
    )

    def __init__(self, *args, **kwargs):
        self.time_slot = kwargs.pop("time_slot", None)
        self.doctor = kwargs.pop("doctor", None)
        super().__init__(*args, **kwargs)

        # УСТАНАВЛИВАЕМ QUERYSET ДЛЯ УСЛУГ через сервис
        from appointments.services import AppointmentService

        # Инициализируем поля с текущими значениями
        if self.time_slot:
            self.fields["new_time_slot_id"].initial = self.time_slot.id
            self.fields["new_appointment_date"].initial = self.time_slot.date

        # Определяем врача для использования
        doctor_to_use = self.doctor or (
            self.time_slot.doctor if self.time_slot else None
        )
        # Используем сервис для инициализации queryset
        AppointmentService.initialize_service_queryset(self, doctor_to_use)

        # ДЛЯ ОТЛАДКИ (можно оставить или удалить)
        if doctor_to_use:
            print(
                f"DEBUG: Found {self.fields['service'].queryset.count()} services for doctor {doctor_to_use}"
            )
        else:
            print("DEBUG: No doctor provided to form")

    def clean(self):
        cleaned_data = super().clean()

        # Проверяем, разрешено ли изменение времени
        allow_time_change = cleaned_data.get("allow_time_change")
        new_time_slot_id = cleaned_data.get("new_time_slot_id")

        if allow_time_change and new_time_slot_id:
            try:
                # Получаем новый слот
                new_time_slot = TimeSlot.objects.get(id=new_time_slot_id)

                # Проверяем доступность
                if not new_time_slot.is_available():
                    raise forms.ValidationError(
                        "Выбранный временной слот уже занят. Пожалуйста, выберите другой слот."
                    )

                # Проверяем, что слот принадлежит тому же врачу
                if self.doctor and new_time_slot.doctor != self.doctor:
                    raise forms.ValidationError(
                        "Выбранный слот не принадлежит текущему врачу."
                    )

                # Сохраняем объект слота для использования в save()
                cleaned_data["new_time_slot"] = new_time_slot

            except TimeSlot.DoesNotExist:
                raise forms.ValidationError("Выбранный временной слот не существует")

        return cleaned_data

    @transaction.atomic
    def save(self, commit=True):
        """Сохраняет запись с транзакционной безопасностью"""
        # Создание/поиск пациента
        patient_data = self.get_patient_data()
        patient, created = PatientService.get_or_create_patient(patient_data)

        # Создание записи
        appointment = super().save(commit=False)
        appointment.patient = patient

        # Определяем, какой слот использовать
        allow_time_change = self.cleaned_data.get("allow_time_change", False)
        new_time_slot = self.cleaned_data.get("new_time_slot")

        if allow_time_change and new_time_slot:
            appointment.time_slot = new_time_slot
        else:
            appointment.time_slot = self.time_slot

        # Устанавливаем, что это основная запись в цепочке
        appointment.is_chain_main = True

        # Определяем тип цепочки
        appointment_chain_type = self.cleaned_data.get("appointment_chain_type")
        if appointment_chain_type == "additional":
            appointment.chain_type = Appointment.ChainType.SAME_DOCTOR
        elif appointment_chain_type == "two_slots":
            appointment.chain_type = Appointment.ChainType.SAME_DОCTOR
            appointment.occupies_two_slots = True
        elif appointment_chain_type in ["another_doctor", "multiple"]:
            appointment.chain_type = Appointment.ChainType.MULTIPLE_DOCTORS
        else:
            appointment.chain_type = Appointment.ChainType.SINGLE

        self._set_appointment_price(appointment)

        # Сохраняем общую сумму из формы (если есть)
        total_sum = self.cleaned_data.get("total_sum")
        if total_sum:
            appointment.total_with_blood_tests = total_sum

        if commit:
            try:
                # ВАЖНО: Сначала сохраняем основную запись
                appointment.save()
                print(f"DEBUG: Основная запись создана, ID={appointment.id}")

                # Проверка процедурной записи для ОСНОВНОЙ записи
                if self.cleaned_data.get("needs_procedural"):
                    if not ProceduralAppointmentService.can_create_procedural_appointment(
                        appointment
                    ):
                        raise forms.ValidationError(
                            "Невозможно создать запись: выбранное время в процедурном кабинете уже занято."
                        )
                    procedural_appointment = (
                        ProceduralAppointmentService.create_procedural_appointment(
                            appointment
                        )
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
                        print(
                            f"DEBUG: Процедурная запись для основной создана, ID={procedural_appointment.id}"
                        )

                # Обработка последовательных записей к тому же врачу
                appointment_chain_type = self.cleaned_data.get("appointment_chain_type")
                if appointment_chain_type in ["additional", "two_slots"]:
                    # ПЕРЕДАЕМ needs_procedural_additional В СЕРВИС
                    needs_procedural_additional = self.cleaned_data.get(
                        "needs_procedural_additional", False
                    )
                    print(
                        f"DEBUG: Создание последовательной записи с needs_procedural_additional={needs_procedural_additional}"
                    )

                    self._handle_consecutive_appointments(
                        appointment,
                        appointment_chain_type,
                        needs_procedural_additional,  # ПЕРЕДАЕМ ФЛАГ
                    )

                # Обработка дополнительных записей к другим врачам
                if appointment_chain_type in ["another_doctor", "multiple"]:
                    self._handle_additional_appointments(appointment)

            except forms.ValidationError:
                # Пробрасываем ValidationError дальше
                raise
            except Exception as e:
                if "unique_doctor_time_slot" in str(e):
                    raise forms.ValidationError(
                        "Невозможно создать запись: выбранное время уже занято другим пациентом. "
                        "Пожалуйста, обновите страницу и выберите другое время."
                    )
                elif "duplicate key" in str(e).lower():
                    raise forms.ValidationError(
                        "Невозможно создать запись: произошел конфликт расписания. "
                        "Пожалуйста, обновите страницу и попробуйте снова."
                    )
                else:
                    # Добавляем отладочную информацию
                    import traceback

                    print(f"DEBUG: Неожиданная ошибка при создании записи:")
                    print(traceback.format_exc())
                    raise forms.ValidationError(
                        f"Неожиданная ошибка при создании записи: {str(e)}"
                    )

        return appointment

    def _set_appointment_price(self, appointment, service=None):
        """Устанавливает цену услуги для записи"""
        if not appointment.price_at_appointment:
            if service:
                appointment.price_at_appointment = service.price
            elif appointment.service:
                appointment.price_at_appointment = appointment.service.price

        # Устанавливаем итоговую сумму
        if not appointment.total_with_blood_tests:
            appointment.total_with_blood_tests = appointment.price_at_appointment

    def _handle_consecutive_appointments(
        self,
        main_appointment,
        appointment_chain_type,
        needs_procedural_additional=False,
    ):
        """Обработка последовательных записей к тому же врачу"""
        if appointment_chain_type in ["additional", "two_slots"]:
            try:
                # Используем сервис для создания последовательной записи
                consecutive_appointment = ConsecutiveAppointmentService.create_consecutive_appointment(
                    main_appointment=main_appointment,
                    appointment_chain_type=appointment_chain_type,
                    additional_service=self.cleaned_data.get("additional_service"),
                    needs_procedural_additional=needs_procedural_additional,  # ПЕРЕДАЕМ ФЛАГ
                )

                print(
                    f"DEBUG: Последовательная запись создана успешно, ID={consecutive_appointment.id}"
                )

                # ПРОВЕРЯЕМ, СОЗДАНА ЛИ ПРОЦЕДУРНАЯ ЗАПИСЬ
                if needs_procedural_additional:
                    # Проверяем, есть ли связанная процедурная запись
                    procedural_exists = AppointmentChain.objects.filter(
                        main_appointment=consecutive_appointment,
                        chain_type=AppointmentChain.ChainType.PROCEDURAL,
                    ).exists()

                    if procedural_exists:
                        print(f"DEBUG: Процедурная запись создана для второй услуги")
                    else:
                        print(
                            f"DEBUG: Предупреждение: процедурная запись не создана для второй услуги"
                        )

            except ValidationError as e:
                # Перехватываем ValidationError и преобразуем в forms.ValidationError
                raise forms.ValidationError(str(e))
            except Exception as e:
                import traceback

                error_details = traceback.format_exc()
                print(f"DEBUG: Подробная ошибка при создании последовательной записи:")
                print(error_details)
                raise forms.ValidationError(
                    f"Ошибка при создании последовательной записи: {str(e)}"
                )

    def _handle_additional_appointments(self, main_appointment):
        """Обработка дополнительных записей к другим врачам"""
        appointment_chain_type = self.cleaned_data.get("appointment_chain_type")

        if appointment_chain_type in ["another_doctor", "multiple"]:
            additional_data = self.cleaned_data.get("additional_appointments_data")
            procedural_data = self.cleaned_data.get("procedural_appointments_data")

            if additional_data:
                try:
                    appointments_list = json.loads(additional_data)
                    procedural_list = (
                        json.loads(procedural_data) if procedural_data else []
                    )

                    for i, appointment_data in enumerate(appointments_list, start=1):
                        # Создаем запись
                        additional_appointment = self._create_additional_appointment(
                            main_appointment, appointment_data, i
                        )

                        # ПРОВЕРЯЕМ, ЕСТЬ ЛИ ПРОЦЕДУРНЫЕ ДАННЫЕ ДЛЯ ЭТОЙ ЗАПИСИ
                        procedural_info = None
                        if procedural_list:
                            # Ищем по индексу
                            for item in procedural_list:
                                if str(item.get("index")) == str(
                                    appointment_data.get("index")
                                ):
                                    procedural_info = item
                                    break

                        print(
                            f"DEBUG: Проверка процедурных данных для записи #{i}: {procedural_info}"
                        )

                        # Создаем процедурную запись если нужно (используем сервис)
                        if procedural_info and procedural_info.get("needs_procedural"):
                            print(
                                f"DEBUG: Создаем процедурную запись для дополнительной записи #{i}"
                            )
                            ProceduralAppointmentService.create_procedural_for_appointment(
                                additional_appointment,
                                main_appointment=additional_appointment,
                            )

                except (json.JSONDecodeError, KeyError) as e:
                    raise forms.ValidationError(
                        f"Ошибка обработки данных дополнительных записей: {str(e)}"
                    )

    def _create_additional_appointment(self, main_appointment, appointment_data, order):
        """Создание одной дополнительной записи"""
        try:
            # Получаем объекты из данных
            doctor_id = appointment_data.get("doctor_id")
            service_id = appointment_data.get("service_id")
            time_slot_id = appointment_data.get("time_slot_id")
            comment = appointment_data.get("comment", "")

            print(f"DEBUG: Создание дополнительной записи #{order}")
            print(
                f"DEBUG: doctor_id={doctor_id}, service_id={service_id}, time_slot_id={time_slot_id}"
            )

            if not all([doctor_id, service_id, time_slot_id]):
                raise ValueError("Не все обязательные поля заполнены")

            doctor = Doctor.objects.get(id=doctor_id)
            service = MedicalService.objects.get(id=service_id)
            time_slot = TimeSlot.objects.get(id=time_slot_id)

            # Проверяем доступность слота
            if not time_slot.is_available():
                raise forms.ValidationError(
                    f"Слот {time_slot.start_time} у врача {doctor.surname} уже занят"
                )

            # Создаем дополнительную запись
            additional_appointment = Appointment.objects.create(
                time_slot=time_slot,
                patient=main_appointment.patient,
                service=service,
                insurance_type=main_appointment.insurance_type,
                status=main_appointment.status,
                comment=comment
                or f"Дополнительная запись с основной #{main_appointment.id}",
                chain_type=Appointment.ChainType.MULTIPLE_DOCTORS,
                is_chain_main=False,
            )

            # Сохраняем цену
            self._set_appointment_price(additional_appointment, service)

            print(
                f"DEBUG: Дополнительная запись #{order} создана успешно, ID={additional_appointment.id}"
            )

            # Создаем связь
            chain = AppointmentChain.objects.create(
                main_appointment=main_appointment,
                related_appointment=additional_appointment,
                chain_type=AppointmentChain.ChainType.ANOTHER_DOCTOR,
                order=order,
            )

            print(
                f"DEBUG: Связь создана: {main_appointment.id} → {additional_appointment.id}"
            )

            return additional_appointment

        except (
            Doctor.DoesNotExist,
            MedicalService.DoesNotExist,
            TimeSlot.DoesNotExist,
        ) as e:
            raise forms.ValidationError(
                f"Ошибка создания дополнительной записи: {str(e)}"
            )


class AppointmentUpdateForm(AppointmentBaseForm):
    """Форма редактирования записи"""

    appointment_date = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
        label="Дата приема",
    )
    time_slot_id = forms.IntegerField(
        widget=forms.HiddenInput(),
        required=True,
    )

    # Поле только для отображения выбранного слота
    time_slot_display = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "readonly": "readonly",
                "id": "time_slot_display",
            }
        ),
        label="Выбранный слот",
    )

    class Meta(AppointmentBaseForm.Meta):
        fields = [
            "appointment_date",
            "service",
            "insurance_type",
            "needs_reschedule",
            "comment",
        ]

    def __init__(self, *args, **kwargs):
        self.current_appointment = kwargs.pop("current_appointment", None)
        self.doctor = kwargs.pop("doctor", None)
        super().__init__(*args, **kwargs)

        if self.current_appointment and self.instance.pk:
            self._set_initial_values()

        # Устанавливаем queryset для услуги
        self._set_service_queryset()

    def clean(self):
        cleaned_data = super().clean()

        # ВАЖНО: Обновляем total_sum из POST данных если он есть
        if "total_sum" in self.data and self.data["total_sum"]:
            try:
                cleaned_data["total_sum"] = float(self.data["total_sum"])
            except (ValueError, TypeError):
                pass

        return cleaned_data

    def _set_service_queryset(self):
        """Устанавливает queryset для поля service с учетом врача"""
        from appointments.services import AppointmentService

        # Получаем врача через сервис
        doctor = AppointmentService.get_doctor_for_form(self)

        # Получаем текущую услугу если есть
        current_service = None
        if self.current_appointment and self.current_appointment.service:
            current_service = self.current_appointment.service

        # Используем сервис для инициализации queryset
        AppointmentService.initialize_service_queryset(self, doctor, current_service)

    def _set_initial_values(self):
        """Установка начальных значений"""
        self.current_time_slot = self.instance.time_slot
        self.fields["appointment_date"].initial = self.instance.time_slot.date
        self.fields["time_slot_id"].initial = self.instance.time_slot.id
        self.fields["time_slot_display"].initial = (
            f"{self.instance.time_slot.start_time}-{self.instance.time_slot.end_time} (Каб. {self.instance.time_slot.cabinet.number})"
        )
        self.fields["service"].initial = self.instance.service

        # Определение типа записи
        if self.instance.occupies_two_slots:
            self.fields["appointment_type"].initial = "two_slots"
        elif self.instance.is_consecutive and self.instance.previous_appointment:
            self.fields["appointment_type"].initial = "additional"

        # Установка значения для процедурного кабинета
        has_procedural = Appointment.objects.filter(
            previous_appointment=self.instance, time_slot__cabinet__number=6
        ).exists()
        self.fields["needs_procedural"].initial = has_procedural

    def clean_time_slot_id(self):
        """Валидация временного слота через ID"""
        time_slot_id = self.cleaned_data.get("time_slot_id")
        if not time_slot_id:
            raise forms.ValidationError("Временной слот обязателен для заполнения")

        try:
            time_slot = TimeSlot.objects.get(id=time_slot_id)
        except TimeSlot.DoesNotExist:
            raise forms.ValidationError("Выбранный временной слот не существует")

        # Проверка принадлежности врачу
        if self.doctor and time_slot.doctor != self.doctor:
            raise forms.ValidationError("Выбранный слот не принадлежит текущему врачу")

        # Проверка доступности слота (кроме текущей записи)
        current_time_slot = getattr(self.current_appointment, "time_slot", None)
        if time_slot != current_time_slot:
            # Проверяем, доступен ли слот
            if not time_slot.is_available():
                raise forms.ValidationError("Выбранный временной слот уже занят")

        return time_slot  # Возвращаем объект TimeSlot

    def save(self, commit=True):
        appointment = super().save(commit=False)

        # Обновление временного слота из cleaned_data
        time_slot = self.cleaned_data.get("time_slot_id")  # Это объект TimeSlot
        if time_slot:
            appointment.time_slot = time_slot

        # Обновление пациента
        patient_data = self.get_patient_data()
        patient, created = PatientService.get_or_create_patient(patient_data)
        appointment.patient = patient

        # ВАЖНО: Сохраняем цену услуги при обновлении
        if appointment.service and not appointment.price_at_appointment:
            appointment.price_at_appointment = appointment.service.price

        # ДЛЯ ВСЕХ ЗАПИСЕЙ: Обновляем общую сумму
        # Сначала проверяем hidden поле total_sum, потом используем цену услуги
        total_sum = self.cleaned_data.get("total_sum")
        if total_sum:
            appointment.total_with_blood_tests = total_sum
        else:
            appointment.total_with_blood_tests = appointment.price_at_appointment

        if commit:
            appointment.save()

            # Обработка процедурного кабинета
            needs_procedural = self.cleaned_data.get("needs_procedural", False)
            self._handle_procedural_appointment(appointment, needs_procedural)

            self._handle_consecutive_appointments(appointment)

        return appointment

    def _handle_procedural_appointment(self, main_appointment, needs_procedural):
        """Обрабатывает создание/удаление/перемещение записи в процедурном кабинете"""
        # Находим существующую процедурную запись
        existing_procedural = Appointment.objects.filter(
            previous_appointment=main_appointment, time_slot__cabinet__number=6
        ).first()

        if needs_procedural:
            if existing_procedural:
                # Обновляем существующую процедурную запись через сервис
                ProceduralAppointmentService.update_procedural_appointment(
                    main_appointment, existing_procedural
                )  # ИЗМЕНЕНИЕ
            else:
                # Создаем новую процедурную запись через сервис
                procedural_appointment = (
                    ProceduralAppointmentService.create_procedural_appointment(
                        main_appointment
                    )
                )  # ИЗМЕНЕНИЕ
                # ВАЖНО: Сохраняем сумму для процедурной записи
                if procedural_appointment:
                    if not procedural_appointment.price_at_appointment:
                        procedural_appointment.price_at_appointment = (
                            procedural_appointment.service.price
                        )
                    procedural_appointment.total_with_blood_tests = (
                        procedural_appointment.price_at_appointment
                    )
                    procedural_appointment.save()
        else:
            # Удаляем процедурную запись если она существует
            if existing_procedural:
                existing_procedural.delete()

    def _update_procedural_appointment(self, main_appointment, procedural_appointment):
        """Обновляет существующую процедурную запись на новое время"""
        try:
            from timetable.models import Cabinet, Doctor, TimeSlot

            # Находим процедурный кабинет №6
            procedural_cabinet = Cabinet.objects.get(number=6)

            # Ищем врача-медсестру
            nurse_doctor = (
                Doctor.objects.filter(specialization="nurse").first()
                or main_appointment.doctor
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
            procedural_appointment.time_slot = new_procedural_slot
            procedural_appointment.service = main_appointment.service
            procedural_appointment.insurance_type = main_appointment.insurance_type
            procedural_appointment.status = main_appointment.status
            procedural_appointment.comment = main_appointment.doctor.surname

            # ВАЖНО: Сохраняем сумму
            if not procedural_appointment.price_at_appointment:
                procedural_appointment.price_at_appointment = (
                    procedural_appointment.service.price
                )
            procedural_appointment.total_with_blood_tests = (
                procedural_appointment.price_at_appointment
            )

            procedural_appointment.save()

        except Exception as e:
            raise forms.ValidationError(
                f"Ошибка при обновлении записи в процедурном кабинете: {str(e)}"
            )

    def _handle_consecutive_appointments(self, main_appointment):
        """Обработка последовательных записей"""
        appointment_type = self.cleaned_data.get("appointment_type")

        if appointment_type in ["additional", "two_slots"]:
            next_slot = main_appointment.time_slot.get_next_consecutive_slot()

            if next_slot and next_slot.is_available():
                consecutive_appointment = (
                    AppointmentService.create_consecutive_appointment(
                        main_appointment,
                        appointment_type,
                        next_slot,
                        self.cleaned_data.get("additional_service"),
                    )
                )
                if consecutive_appointment:
                    if not consecutive_appointment.price_at_appointment:
                        consecutive_appointment.price_at_appointment = (
                            consecutive_appointment.service.price
                        )
                    consecutive_appointment.total_with_blood_tests = (
                        consecutive_appointment.price_at_appointment
                    )
                    consecutive_appointment.save()


class ProceduralAppointmentForm(AppointmentBaseForm):
    """Форма для создания записи в процедурный кабинет"""

    procedural_start_time = forms.TimeField(
        required=True,
        label="Время начала",
        widget=forms.TimeInput(attrs={"type": "time", "class": "form-control"}),
    )
    procedural_end_time = forms.TimeField(
        required=True,
        label="Время окончания",
        widget=forms.TimeInput(attrs={"type": "time", "class": "form-control"}),
    )

    # Поле для выбранных анализов крови
    selected_blood_tests_input = forms.CharField(
        required=False,
        widget=forms.HiddenInput(attrs={"id": "id_selected_blood_tests"}),
        label="Выбранные анализы крови",
    )

    # СКРЫТОЕ ПОЛЕ ДЛЯ СУММЫ
    total_sum = forms.DecimalField(
        required=False,
        widget=forms.HiddenInput(attrs={"id": "id_total_sum"}),
        decimal_places=2,
        max_digits=10,
        label="Итоговая сумма",
    )

    def __init__(self, *args, **kwargs):
        self.selected_date = kwargs.pop("selected_date", None)
        kwargs.pop("time_slot", None)
        kwargs.pop("doctor", None)
        super().__init__(*args, **kwargs)

        # Удаляем ненужные поля
        for field in [
            "needs_procedural",
            "procedural_time_slot",
            "appointment_type",
            "additional_service",
        ]:
            if field in self.fields:
                del self.fields[field]

        self.set_nurse_services()

    def set_nurse_services(self):
        """Устанавливает queryset услуг, доступных для медсестры"""
        from timetable.models import MedicalServiceCategory

        nurse_categories = [
            MedicalServiceCategory.MEDICAL_BLOCKADES,
            MedicalServiceCategory.ANALYZES,
        ]

        nurse_services = MedicalService.objects.filter(
            category__in=nurse_categories, is_active=True
        )

        # Обновляем queryset для поля service
        self.fields["service"].queryset = nurse_services

    def clean(self):
        cleaned_data = super().clean()

        # Валидация времени
        start_time = cleaned_data.get("procedural_start_time")
        end_time = cleaned_data.get("procedural_end_time")

        if start_time and end_time and start_time >= end_time:
            raise forms.ValidationError(
                "Время окончания должно быть позже времени начала"
            )

        service = cleaned_data.get("service")
        selected_blood_tests_input = cleaned_data.get("selected_blood_tests_input", "")

        # Преобразуем строку с ID в список объектов BloodTest
        selected_blood_tests = []
        if selected_blood_tests_input:
            try:
                selected_blood_tests_input = selected_blood_tests_input.strip()
                test_ids = [
                    int(id.strip())
                    for id in selected_blood_tests_input.split(",")
                    if id.strip() and id.strip().isdigit()
                ]
                selected_blood_tests = BloodTest.objects.filter(id__in=test_ids)
            except (ValueError, TypeError) as e:
                raise forms.ValidationError("Неверный формат выбранных анализов")

        # Сохраняем в cleaned_data
        cleaned_data["selected_blood_tests"] = selected_blood_tests

        # Валидация для услуги "Забор крови"
        if service and "забор крови" in service.name.lower():
            if not selected_blood_tests:
                raise forms.ValidationError(
                    "Для услуги 'Забор крови' необходимо выбрать хотя бы один анализ"
                )

        return cleaned_data

    def save(self, commit=True):
        # Создание/поиск пациента
        patient_data = self.get_patient_data()
        patient, created = PatientService.get_or_create_patient(patient_data)

        # Создание записи
        appointment = super().save(commit=False)

        # Сохраняем цену услуги на момент записи
        if appointment.service and not appointment.price_at_appointment:
            appointment.price_at_appointment = appointment.service.price

        # Создаем слот
        start_time = self.cleaned_data.get("procedural_start_time")
        end_time = self.cleaned_data.get("procedural_end_time")
        time_slot = self.create_procedural_slot(start_time, end_time)

        appointment.time_slot = time_slot
        appointment.patient = patient

        # ВАЖНО: Сохраняем общую сумму из скрытого поля
        total_sum = self.cleaned_data.get("total_sum")
        if total_sum:
            appointment.total_with_blood_tests = total_sum
        else:
            # Если сумма не пришла, считаем ее вручную
            selected_blood_tests = self.cleaned_data.get("selected_blood_tests", [])
            tests_price = sum(test.price for test in selected_blood_tests)
            service_price = (
                appointment.price_at_appointment or appointment.service.price
            )
            appointment.total_with_blood_tests = service_price + tests_price

        if commit:
            appointment.save()

            # Сохраняем выбранные анализы крови
            selected_blood_tests = self.cleaned_data.get("selected_blood_tests", [])
            for test in selected_blood_tests:
                AppointmentBloodTest.objects.create(
                    appointment=appointment, blood_test=test
                )

            # Автоматически формируем комментарий (необязательно, но полезно)
            user_comment = self.cleaned_data.get("comment", "").strip()
            comment_lines = []

            if user_comment:
                comment_lines.append(user_comment)

            # Добавляем информацию об анализах, если они есть
            if selected_blood_tests:
                tests_price = sum(test.price for test in selected_blood_tests)
                service_price = (
                    appointment.price_at_appointment or appointment.service.price
                )
                total_price = tests_price + service_price

                comment_lines.append(
                    f"Анализы: {tests_price} руб. + Забор крови: {service_price} руб. = Итого: {total_price} руб."
                )

            # Объединяем комментарии
            if comment_lines:
                appointment.comment = "\n".join(comment_lines)

            appointment.save()

        return appointment

    def create_procedural_slot(self, start_time, end_time):
        """Создает или находит существующий временной слот для процедурного кабинета"""
        try:
            date = self.selected_date or timezone.now().date()

            # Используем сервис для создания/получения слота
            time_slot = ProceduralAppointmentService.create_or_get_procedural_slot(
                date=date,
                start_time=start_time,
                end_time=end_time,
                doctor=self.doctor if hasattr(self, "doctor") else None,
            )

            return time_slot
        except Exception as e:
            raise forms.ValidationError(f"Ошибка при создании/поиске слота: {str(e)}")


class ProceduralAppointmentUpdateForm(ProceduralAppointmentForm):
    """Форма для редактирования записи в процедурный кабинет"""

    def __init__(self, *args, **kwargs):
        self.current_appointment = kwargs.pop("current_appointment", None)
        super().__init__(*args, **kwargs)

        self.fields["service"].widget.attrs.update({"data-price-field": "id_total_sum"})

        if self.current_appointment and self.instance.pk:
            self._set_initial_blood_tests()
            self._set_initial_comment_without_tests()

            # Устанавливаем начальное значение для суммы
            if self.current_appointment.total_with_blood_tests:
                self.fields["total_sum"].initial = (
                    self.current_appointment.total_with_blood_tests
                )

    def _set_initial_blood_tests(self):
        """Устанавливаем начальные значения для выбранных анализов крови"""
        selected_tests = self.current_appointment.selected_blood_tests.all()
        if selected_tests:
            test_ids = [str(test.blood_test.id) for test in selected_tests]
            self.fields["selected_blood_tests_input"].initial = ",".join(test_ids)

    def _set_initial_comment_without_tests(self):
        """Устанавливаем начальный комментарий без информации об анализах"""
        if self.current_appointment and self.current_appointment.comment:
            comment = self.current_appointment.comment
            lines = comment.split("\n")
            filtered_lines = []

            for line in lines:
                if not any(
                    keyword in line
                    for keyword in ["Анализы:", "Итого:", "Забор крови:"]
                ):
                    filtered_lines.append(line)

            clean_comment = "\n".join(filtered_lines).strip()
            self.fields["comment"].initial = clean_comment

    def save(self, commit=True):
        appointment = super().save(commit=False)

        # Используем текущий слот
        time_slot = (
            self.current_appointment.time_slot
            if self.current_appointment
            else appointment.time_slot
        )

        # Обновляем время если нужно
        start_time = self.cleaned_data.get("procedural_start_time")
        end_time = self.cleaned_data.get("procedural_end_time")

        if start_time and end_time and time_slot:
            if start_time != time_slot.start_time or end_time != time_slot.end_time:
                time_slot.start_time = start_time
                time_slot.end_time = end_time
                time_slot.save()

        appointment.time_slot = time_slot

        # Обновляем пациента
        patient_data = self.get_patient_data()
        patient, created = PatientService.get_or_create_patient(patient_data)
        appointment.patient = patient

        # Сохраняем общую сумму из скрытого поля
        total_sum = self.cleaned_data.get("total_sum")
        if total_sum:
            appointment.total_with_blood_tests = total_sum
        else:
            # Если сумма не пришла, пересчитываем
            selected_blood_tests = self.cleaned_data.get("selected_blood_tests", [])
            tests_price = sum(test.price for test in selected_blood_tests)
            service_price = (
                appointment.price_at_appointment or appointment.service.price
            )
            appointment.total_with_blood_tests = service_price + tests_price

        if commit:
            appointment.save()

            # Обновляем связи с анализами
            selected_blood_tests = self.cleaned_data.get("selected_blood_tests", [])
            current_relations = AppointmentBloodTest.objects.filter(
                appointment=appointment
            )
            current_test_ids = set(
                relation.blood_test_id for relation in current_relations
            )
            new_test_ids = set(test.id for test in selected_blood_tests)

            # Удаляем старые
            if current_test_ids - new_test_ids:
                AppointmentBloodTest.objects.filter(
                    appointment=appointment,
                    blood_test_id__in=current_test_ids - new_test_ids,
                ).delete()

            # Добавляем новые
            for test_id in new_test_ids - current_test_ids:
                AppointmentBloodTest.objects.create(
                    appointment=appointment, blood_test_id=test_id
                )

            # Формируем комментарий
            user_comment = self.cleaned_data.get("comment", "").strip()
            comment_lines = []

            if user_comment:
                comment_lines.append(user_comment)

            if selected_blood_tests:
                tests_price = sum(test.price for test in selected_blood_tests)
                service_price = (
                    appointment.price_at_appointment or appointment.service.price
                )
                total_price = tests_price + service_price

                comment_lines.append(
                    f"Анализы: {tests_price} руб. + Забор крови: {service_price} руб. = Итого: {total_price} руб."
                )

            if comment_lines:
                appointment.comment = "\n".join(comment_lines)
            else:
                appointment.comment = ""

            appointment.save()

        return appointment


class AdditionalAppointmentForm(forms.Form):
    """Форма для одной дополнительной записи к другому врачу"""

    doctor = forms.ModelChoiceField(
        queryset=Doctor.objects.order_by("surname"),
        widget=forms.Select(
            attrs={
                "class": "form-select additional-doctor-select",
                "data-action": "change->appointment#onDoctorChange",
            }
        ),
        label="Врач",
        required=True,
    )

    service = forms.ModelChoiceField(
        queryset=MedicalService.objects.none(),
        widget=forms.Select(
            attrs={
                "class": "form-select additional-service-select",
                "disabled": "disabled",
                "data-action": "change->appointment#onServiceChange",
            }
        ),
        label="Услуга",
        required=True,
    )

    appointment_date = forms.DateField(
        widget=forms.DateInput(
            attrs={
                "type": "date",
                "class": "form-control additional-date-select",
                "data-action": "change->appointment#onDateChange",
            }
        ),
        label="Дата приема",
        required=True,
    )

    time_slot = forms.ModelChoiceField(
        queryset=TimeSlot.objects.none(),
        widget=forms.Select(
            attrs={
                "class": "form-select additional-slot-select",
                "disabled": "disabled",
                "data-action": "change->appointment#onSlotChange",
            }
        ),
        label="Временной слот",
        required=True,
    )

    comment = forms.CharField(
        widget=forms.Textarea(
            attrs={
                "rows": 2,
                "class": "form-control",
                "placeholder": "Комментарий к дополнительной записи",
            }
        ),
        label="Комментарий",
        required=False,
    )

    def __init__(self, *args, **kwargs):
        self.initial_doctor = kwargs.pop("initial_doctor", None)
        self.initial_date = kwargs.pop("initial_date", None)
        super().__init__(*args, **kwargs)

        # Устанавливаем минимальную дату - сегодня
        today = timezone.now().date()
        self.fields["appointment_date"].widget.attrs["min"] = today.isoformat()

        # Устанавливаем начальные значения если есть
        if self.initial_doctor:
            self.fields["doctor"].initial = self.initial_doctor
            self.set_service_queryset(self.initial_doctor)

        if self.initial_date:
            self.fields["appointment_date"].initial = self.initial_date

    def set_service_queryset(self, doctor):
        """Устанавливает queryset услуг для выбранного врача"""
        if doctor:
            # Используем сервис для инициализации queryset
            from appointments.services import AppointmentService

            # Создаем временный объект формы для использования сервиса
            class TempForm:
                def __init__(self, doctor):
                    self.doctor = doctor
                    self.fields = {
                        "service": type(
                            "Field", (), {"queryset": MedicalService.objects.none()}
                        ),
                        "additional_service": type(
                            "Field", (), {"queryset": MedicalService.objects.none()}
                        ),
                    }

            temp_form = TempForm(doctor)
            AppointmentService.initialize_service_queryset(temp_form, doctor)

            self.fields["service"].queryset = temp_form.fields["service"].queryset
            self.fields["service"].widget.attrs.pop("disabled", None)

    def set_time_slot_queryset(self, doctor, date):
        """Устанавливает queryset слотов для выбранного врача и даты"""

        if doctor and date:
            # Получаем доступные слоты
            available_slots = TimeSlot.objects.filter(
                doctor=doctor,
                date=date,
                slot_type="working",
                appointments__isnull=True,  # Только свободные слоты
            ).order_by("start_time")

            self.fields["time_slot"].queryset = available_slots
            if available_slots.exists():
                self.fields["time_slot"].widget.attrs.pop("disabled", None)
            else:
                self.fields["time_slot"].widget.attrs["disabled"] = "disabled"
                self.fields["time_slot"].queryset = TimeSlot.objects.none()

    def clean(self):
        cleaned_data = super().clean()

        doctor = cleaned_data.get("doctor")
        appointment_date = cleaned_data.get("appointment_date")
        time_slot = cleaned_data.get("time_slot")

        # Проверяем, что все обязательные поля есть
        if not doctor or not appointment_date or not time_slot:
            return cleaned_data

        # Проверяем, что слот принадлежит выбранному врачу
        if time_slot.doctor != doctor:
            raise ValidationError("Выбранный слот не принадлежит выбранному врачу")

        # Проверяем, что слот на выбранную дату
        if time_slot.date != appointment_date:
            raise ValidationError("Выбранный слот не на выбранную дату")

        # Проверяем, что слот свободен
        if not time_slot.is_available():
            raise ValidationError("Выбранный слот уже занят")

        return cleaned_data
