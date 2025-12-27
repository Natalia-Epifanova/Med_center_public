import json

from django import forms
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from appointments.forms.base import AppointmentChainBaseForm
from appointments.forms.procedural_base import ProceduralAppointmentBaseForm
from appointments.models import Appointment, AppointmentBloodTest, AppointmentChain
from appointments.services import (
    ConsecutiveAppointmentService,
    ProceduralAppointmentService,
)
from patients.services import PatientService
from timetable.models import BloodTest, Doctor, MedicalService, TimeSlot
from timetable.utils import get_doctor_services


class AppointmentForm(AppointmentChainBaseForm, forms.ModelForm):
    """Форма создания записи с возможностью изменения времени"""

    class Meta:
        model = Appointment
        fields = [
            "service",
            "insurance_type",
            "needs_reschedule",
            "comment",
        ]

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

        # Теперь передаем в родительский класс
        super().__init__(*args, **kwargs, time_slot=self.time_slot, doctor=self.doctor)
        self.fields["insurance_type"].initial = "paid"
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

    def _validate_consecutive_for_pishchelev(
        self, main_appointment, appointment_chain_type
    ):
        """Дополнительная валидация для последовательных записей Пищелева"""
        if not hasattr(main_appointment, "doctor") or not main_appointment.doctor:
            return

        is_pishchelev = "пищелев" in main_appointment.doctor.surname.lower()
        if not is_pishchelev:
            return

        if appointment_chain_type == "additional":
            additional_service = self.cleaned_data.get("additional_service")
            if not additional_service:
                return

            # Получаем следующий слот
            next_slot = main_appointment.time_slot.get_next_consecutive_slot()
            if not next_slot:
                return

            # Проверяем ограничения для следующего слота
            slot_duration = self._get_slot_duration_minutes(next_slot)
            is_insoles = self._is_insoles_service(additional_service)

            if slot_duration == 20 and not is_insoles:
                raise forms.ValidationError(
                    "❌ Врач Пищелев П.В. на 20-минутные интервалы принимает ТОЛЬКО на изготовление стелек!\n\n"
                    'Для второй услуги выберите "Изготовление стелек" или выберите 30-минутный интервал.'
                )

        elif appointment_chain_type == "two_slots":
            # Для записи на 2 слота
            next_slot = main_appointment.time_slot.get_next_consecutive_slot()
            if not next_slot:
                return

            slot_duration = self._get_slot_duration_minutes(next_slot)
            is_insoles = self._is_insoles_service(main_appointment.service)

            if slot_duration == 20 and not is_insoles:
                raise forms.ValidationError(
                    "❌ Врач Пищелев П.В. на 20-минутные интервалы принимает ТОЛЬКО на изготовление стелек!\n\n"
                    "Невозможно занять два 20-минутных слота для этой услуги."
                )

    @transaction.atomic
    def save(self, commit=True):
        """Сохраняет запись с транзакционной безопасностью"""
        if not commit:
            return super(AppointmentChainBaseForm, self).save(commit=False)

        try:
            with transaction.atomic():
                # Создание/поиск пациента
                patient_data = self.get_patient_data()
                patient, created = PatientService.get_or_create_patient(patient_data)

                # Получаем объект записи из родительского класса
                appointment = super(AppointmentChainBaseForm, self).save(commit=False)
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
                    appointment.chain_type = Appointment.ChainType.SAME_DOCTOR
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

                # ВАЖНО: Сохраняем основную запись сразу для получения ID
                appointment.save()

                # ДОПОЛНИТЕЛЬНАЯ ПРОВЕРКА ПИЩЕЛЕВА для последовательных записей
                if appointment_chain_type in ["additional", "two_slots"]:
                    self._validate_consecutive_for_pishchelev(
                        appointment, appointment_chain_type
                    )

                # ПРОВЕРКА 1: Процедурная запись для ОСНОВНОЙ записи (проверяем ДО создания)
                if self.cleaned_data.get("needs_procedural"):
                    if not ProceduralAppointmentService.can_create_procedural_appointment(
                        appointment
                    ):
                        raise forms.ValidationError(
                            "Невозможно создать запись: выбранное время в процедурном кабинете уже занято. "
                            "Пожалуйста, выберите другое время."
                        )

                # ПРОВЕРКА 2: Для второй услуги с процедурным кабинетом
                needs_procedural_additional = self.cleaned_data.get(
                    "needs_procedural_additional", False
                )

                if (
                    appointment_chain_type == "additional"
                    and needs_procedural_additional
                ):
                    # Создаем временный объект для проверки
                    temp_appointment = Appointment(
                        time_slot=appointment.time_slot,
                        patient=appointment.patient,
                        service=self.cleaned_data.get("additional_service"),
                        insurance_type=appointment.insurance_type,
                        status=appointment.status,
                    )

                    if not ProceduralAppointmentService.can_create_procedural_appointment(
                        temp_appointment
                    ):
                        raise forms.ValidationError(
                            "Невозможно создать запись: выбранное время в процедурном кабинете уже занято "
                            "для второй услуги. Пожалуйста, выберите другое время."
                        )

                # Только после всех проверок создаем остальные записи
                if self.cleaned_data.get("needs_procedural"):
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

                # Обработка последовательных записей к тому же врачу
                if appointment_chain_type in ["additional", "two_slots"]:
                    self._handle_consecutive_appointments(
                        appointment,
                        appointment_chain_type,
                        needs_procedural_additional,
                    )

                # Обработка дополнительных записей к другим врачам
                if appointment_chain_type in ["another_doctor", "multiple"]:
                    self._handle_additional_appointments(appointment)

                return appointment

        except forms.ValidationError:
            raise
        except IntegrityError as e:
            if "unique_doctor_time_slot" in str(e):
                raise forms.ValidationError(
                    "Невозможно создать запись: выбранное время уже занято другим пациентом. "
                    "Пожалуйста, обновите страницу и выберите другое время."
                )
            raise

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

            except ValidationError as e:
                # Перехватываем ValidationError и преобразуем в forms.ValidationError
                raise forms.ValidationError(str(e))

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
                        if "insurance_type" not in appointment_data:
                            # Установить значение по умолчанию
                            appointment_data["insurance_type"] = "paid"
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

                        # Создаем процедурную запись если нужно (используем сервис)
                        if procedural_info and procedural_info.get("needs_procedural"):
                            ProceduralAppointmentService.create_procedural_for_appointment(
                                additional_appointment,
                                main_appointment=additional_appointment,
                            )

                except (json.JSONDecodeError, KeyError) as e:
                    raise forms.ValidationError(
                        f"Ошибка обработки данных дополнительных записей: {str(e)}"
                    )

    def _create_additional_appointment(self, main_appointment, appointment_data, order):
        """Создание одной дополнительной записи с проверкой времени"""
        try:
            # Получаем объекты из данных
            doctor_id = appointment_data.get("doctor_id")
            service_id = appointment_data.get("service_id")
            time_slot_id = appointment_data.get("time_slot_id")
            comment = appointment_data.get("comment", "")
            insurance_type = appointment_data.get("insurance_type", "paid")

            if not all([doctor_id, service_id, time_slot_id]):
                raise ValueError("Не все обязательные поля заполнены")

            doctor = Doctor.objects.get(id=doctor_id)
            service = MedicalService.objects.get(id=service_id)
            time_slot = TimeSlot.objects.get(id=time_slot_id)

            # ВАЖНОЕ ДОБАВЛЕНИЕ: Проверка ограничений Пищелева
            if "пищелев" in doctor.surname.lower():
                from django.core.exceptions import ValidationError

                from timetable.utils import validate_pishchelev_restrictions

                try:
                    validate_pishchelev_restrictions(doctor, service, time_slot)
                except ValidationError as e:
                    raise forms.ValidationError(
                        f"Ошибка в дополнительной записи #{order} (к врачу {doctor.surname}): {str(e)}"
                    )

            # Проверяем, что дата дополнительной записи НЕ пересекается по времени с основной
            if time_slot.date == main_appointment.date:
                # Получаем время начала и окончания слотов
                main_start = main_appointment.start_time
                main_end = main_appointment.end_time
                add_start = time_slot.start_time
                add_end = time_slot.end_time

                # Функция для конвертации времени в минуты
                def time_to_minutes(t):
                    return t.hour * 60 + t.minute + t.second / 60

                main_start_minutes = time_to_minutes(main_start)
                main_end_minutes = time_to_minutes(main_end)
                add_start_minutes = time_to_minutes(add_start)
                add_end_minutes = time_to_minutes(add_end)

                # Проверяем пересечение времени
                # Два интервала пересекаются, если:
                # add_start < main_end И add_end > main_start
                is_overlapping = (
                    add_start_minutes < main_end_minutes
                    and add_end_minutes > main_start_minutes
                )

                if is_overlapping:
                    raise forms.ValidationError(
                        f"Ошибка: Время дополнительной записи пересекается с основной записью.\n"
                        f"Основная запись: {main_appointment.date.strftime('%d.%m.%Y')} "
                        f"{main_start.strftime('%H:%M')}-{main_end.strftime('%H:%M')}\n"
                        f"Дополнительная запись: {time_slot.date.strftime('%d.%m.%Y')} "
                        f"{add_start.strftime('%H:%M')}-{add_end.strftime('%H:%M')}\n\n"
                        f"Выберите другое время для дополнительной записи."
                    )

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
                insurance_type=insurance_type,
                status=main_appointment.status,
                comment=comment
                or f"Дополнительная запись с основной #{main_appointment.id}",
                chain_type=Appointment.ChainType.MULTIPLE_DOCTORS,
                is_chain_main=False,
            )

            # Сохраняем цену
            self._set_appointment_price(additional_appointment, service)

            # Создаем связь
            chain = AppointmentChain.objects.create(
                main_appointment=main_appointment,
                related_appointment=additional_appointment,
                chain_type=AppointmentChain.ChainType.ANOTHER_DOCTOR,
                order=order,
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


class AppointmentSimpleEditForm(forms.ModelForm):
    """Упрощенная форма редактирования записи с исправленной валидацией"""

    new_appointment_date = forms.DateField(
        required=True,
        label="Новая дата приема",
        widget=forms.DateInput(
            attrs={
                "type": "date",
                "class": "form-control",
                "id": "id_new_appointment_date",
            }
        ),
    )

    # ЗАМЕНА ModelChoiceField на IntegerField + Hidden поле
    new_time_slot_id = forms.IntegerField(
        required=True,
        widget=forms.HiddenInput(attrs={"id": "id_new_time_slot_id"}),
        label="ID временного слота",
    )

    # Поле для отображения (только для UI)
    new_time_slot_display = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "readonly": "readonly",
                "id": "id_new_time_slot_display",
                "placeholder": "Выберите слот из списка ниже",
            }
        ),
        label="Выбранный временной слот",
    )

    class Meta:
        model = Appointment
        fields = [
            "service",
            "insurance_type",
            "needs_reschedule",
            "comment",
        ]  # ДОБАВЛЕНО needs_reschedule
        widgets = {
            "service": forms.Select(attrs={"class": "form-select"}),
            "insurance_type": forms.Select(attrs={"class": "form-select"}),
            "needs_reschedule": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),  # ДОБАВЛЕНО
            "comment": forms.Textarea(attrs={"rows": 3, "class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        self.appointment = kwargs.get("instance")
        super().__init__(*args, **kwargs)

        if self.appointment:
            print(f"DEBUG FORM: Appointment date = {self.appointment.date}")
            print(
                f"DEBUG FORM: Appointment time_slot id = {self.appointment.time_slot.id if self.appointment.time_slot else 'None'}"
            )

            # Проверяем наличие процедурной записи
            procedural_exists = AppointmentChain.objects.filter(
                main_appointment=self.appointment,
                chain_type=AppointmentChain.ChainType.PROCEDURAL,
            ).exists()

            if procedural_exists:
                print(
                    f"DEBUG FORM: Found procedural appointment for appointment {self.appointment.id}"
                )

            # Устанавливаем минимальную дату - сегодня
            from django.utils import timezone

            today = timezone.now().date()

            # ВАЖНОЕ ИСПРАВЛЕНИЕ: Правильно инициализируем поле даты
            appointment_date = self.appointment.date
            print(f"DEBUG FORM: Setting initial date to {appointment_date}")

            self.fields["new_appointment_date"].initial = appointment_date
            self.fields["new_appointment_date"].widget.attrs["min"] = today.isoformat()

            # ДОБАВЛЯЕМ: Устанавливаем значение виджета
            if appointment_date:
                self.initial["new_appointment_date"] = appointment_date

            # Инициализируем поле слота
            if self.appointment.time_slot:
                self.fields["new_time_slot_id"].initial = self.appointment.time_slot.id
                # Устанавливаем отображение текущего слота
                current_slot_display = (
                    f"{self.appointment.start_time.strftime('%H:%M')}-"
                    f"{self.appointment.end_time.strftime('%H:%M')} "
                    f"(Каб. {self.appointment.cabinet.number})"
                )
                self.fields["new_time_slot_display"].initial = current_slot_display
                print(
                    f"DEBUG FORM: Setting initial slot display to {current_slot_display}"
                )

            # Ограничиваем услуги только для этого врача
            self.fields["service"].queryset = get_doctor_services(
                self.appointment.doctor
            )

    def clean(self):
        cleaned_data = super().clean()

        new_date = cleaned_data.get("new_appointment_date")
        new_time_slot_id = cleaned_data.get("new_time_slot_id")

        # Если слот не выбран, используем текущий слот записи
        if not new_time_slot_id and self.appointment.time_slot:
            cleaned_data["new_time_slot_id"] = self.appointment.time_slot.id
            new_time_slot_id = self.appointment.time_slot.id

        if new_date and new_time_slot_id:
            try:
                # Получаем объект TimeSlot
                new_time_slot = TimeSlot.objects.get(id=new_time_slot_id)

                # 1. Проверяем, что слот принадлежит выбранной дате
                if new_time_slot.date != new_date:
                    self.add_error(
                        "new_time_slot_id",
                        f"Выбранный слот относится к дате {new_time_slot.date.strftime('%d.%m.%Y')}, "
                        f"а не к выбранной дате {new_date.strftime('%d.%m.%Y')}",
                    )
                    return cleaned_data

                # 2. Проверяем, что слот принадлежит правильному врачу
                if new_time_slot.doctor != self.appointment.doctor:
                    self.add_error(
                        "new_time_slot_id",
                        f"Слот принадлежит врачу {new_time_slot.doctor.surname}, "
                        f"а не {self.appointment.doctor.surname}",
                    )
                    return cleaned_data

                # 3. Проверяем, что слот свободен (кроме текущей записи)
                current_slot_id = (
                    self.appointment.time_slot.id
                    if self.appointment.time_slot
                    else None
                )
                if new_time_slot.appointments.exists():
                    # Если это не текущий слот записи, показываем ошибку
                    if not (current_slot_id and new_time_slot.id == current_slot_id):
                        # Получаем имя пациента, который занял слот
                        occupied_appointment = new_time_slot.appointments.first()
                        patient_name = occupied_appointment.patient.get_full_name()
                        self.add_error(
                            "new_time_slot_id",
                            f"Этот временной слот уже занят пациентом {patient_name}",
                        )
                        return cleaned_data

                # ВАЖНОЕ ИСПРАВЛЕНИЕ: Проверяем доступность процедурного кабинета прямо в clean
                if new_time_slot.id != current_slot_id:
                    self._validate_procedural_availability(new_time_slot, new_date)

                # Если все проверки пройдены, добавляем объект в cleaned_data
                cleaned_data["new_time_slot"] = new_time_slot

            except TimeSlot.DoesNotExist:
                self.add_error(
                    "new_time_slot_id", "Выбранный временной слот не существует"
                )
            except ValueError:
                self.add_error(
                    "new_time_slot_id", "Неверный формат идентификатора слота"
                )
            except forms.ValidationError as e:
                # Перехватываем ошибку валидации процедурного кабинета
                self.add_error("new_time_slot_id", str(e))
                return cleaned_data

        # Проверяем, что выбран слот
        elif new_date and not new_time_slot_id:
            # Если дата выбрана, но слот нет - автоматически выбираем текущий слот
            if self.appointment.time_slot:
                cleaned_data["new_time_slot_id"] = self.appointment.time_slot.id
                cleaned_data["new_time_slot"] = self.appointment.time_slot
            else:
                self.add_error("new_time_slot_id", "Выберите временной слот")

        return cleaned_data

    def _validate_procedural_availability(self, new_time_slot, new_date):
        """Проверяет доступность времени в процедурном кабинете для нового слота"""
        from timetable.models import Cabinet

        print(
            f"DEBUG: Validating procedural availability for new slot {new_time_slot.id}"
        )

        # Проверяем, есть ли процедурная запись
        has_procedural = Appointment.objects.filter(
            previous_appointment=self.appointment,
            time_slot__cabinet__number=6,
        ).exists()

        if not has_procedural:
            print(f"DEBUG: No procedural appointment found")
            return True

        print(
            f"DEBUG: Found procedural appointment for appointment {self.appointment.id}"
        )

        # Находим процедурный кабинет
        try:
            procedural_cabinet = Cabinet.objects.get(number=6)
        except Cabinet.DoesNotExist:
            raise forms.ValidationError(
                "Процедурный кабинет (кабинет 6) не найден в системе"
            )

        # Находим процедурную запись для получения ее текущего слота
        procedural_appointment = Appointment.objects.filter(
            previous_appointment=self.appointment,
            time_slot__cabinet__number=6,
        ).first()

        if not procedural_appointment:
            return True

        # Проверяем доступность времени в процедурном кабинете на новую дату
        # Исключаем текущий слот процедурной записи из проверки
        conflicting_slots = TimeSlot.objects.filter(
            date=new_date,
            cabinet=procedural_cabinet,
            start_time__lt=new_time_slot.end_time,
            end_time__gt=new_time_slot.start_time,
            appointments__isnull=False,
        ).exclude(
            id=procedural_appointment.time_slot_id  # Исключаем текущий слот процедурной записи
        )

        print(f"DEBUG: Found {conflicting_slots.count()} conflicting slots")

        if conflicting_slots.exists():
            occupied_slot = conflicting_slots.first()
            patient_name = occupied_slot.appointments.first().patient.get_full_name()

            error_msg = (
                f"Невозможно перенести запись: время {new_time_slot.start_time.strftime('%H:%M')}-"
                f"{new_time_slot.end_time.strftime('%H:%M')} {new_date.strftime('%d.%m.%Y')} "
                f"в процедурном кабинете уже занято пациентом {patient_name}. "
                f"Пожалуйста, выберите другое время или отмените процедурную запись."
            )
            print(f"ERROR: {error_msg}")
            raise forms.ValidationError(error_msg)

        return True

    @transaction.atomic
    def save(self, commit=True):
        """Сохраняет запись с проверкой процедурного кабинета"""
        appointment = super().save(commit=False)

        # Получаем новую дату и слот
        new_date = self.cleaned_data["new_appointment_date"]
        new_time_slot = self.cleaned_data["new_time_slot"]

        # Сохраняем старый слот для сравнения
        old_time_slot = appointment.time_slot
        old_date = appointment.date

        # Проверяем, изменились ли дата или время
        date_changed = new_date != old_date
        time_changed = new_time_slot.id != old_time_slot.id if new_time_slot else False

        print(f"DEBUG SAVE: Date changed: {date_changed}, Time changed: {time_changed}")

        # Обновляем слот только если он изменился
        if date_changed or time_changed:
            appointment.time_slot = new_time_slot

        # Сохраняем запись
        if commit:
            try:
                appointment.save()
                print(f"DEBUG SAVE: Saved appointment {appointment.id}")

                # Переносим процедурную запись если она есть
                if date_changed or time_changed:
                    self._move_procedural_appointment(
                        appointment, old_time_slot, new_time_slot, old_date
                    )

                # ВАЖНО: Всегда обновляем услугу в процедурной записи
                self._update_procedural_service(appointment)

            except forms.ValidationError as e:
                # Если возникает ошибка при переносе процедурной записи
                print(f"DEBUG SAVE: Procedural move error: {str(e)}")
                raise forms.ValidationError(str(e))

        return appointment

    def _move_procedural_appointment(
        self, appointment, old_time_slot, new_time_slot, old_date
    ):
        """Переносит связанную процедурную запись на новое время"""
        from timetable.models import Cabinet

        print(f"DEBUG: Starting procedural move for appointment {appointment.id}")

        # Ищем процедурную запись
        procedural_appointment = Appointment.objects.filter(
            previous_appointment=appointment,
            time_slot__cabinet__number=6,
        ).first()

        if not procedural_appointment:
            print(f"DEBUG: No procedural appointment found")
            return

        print(f"DEBUG: Found procedural appointment: {procedural_appointment.id}")

        # Находим процедурный кабинет
        try:
            procedural_cabinet = Cabinet.objects.get(number=6)
        except Cabinet.DoesNotExist:
            raise forms.ValidationError(
                "Процедурный кабинет (кабинет 6) не найден в системе"
            )

        # Находим или создаем слот в процедурном кабинете на НОВОЕ время
        procedural_time_slot, created = TimeSlot.objects.get_or_create(
            doctor=procedural_appointment.doctor or appointment.doctor,
            cabinet=procedural_cabinet,
            date=new_time_slot.date,
            start_time=new_time_slot.start_time,
            end_time=new_time_slot.end_time,
            defaults={"slot_type": "working", "description": "Процедурный кабинет"},
        )

        print(f"DEBUG: Created new procedural time slot? {created}")

        # Проверяем, не занят ли этот слот другой записью
        if not created and procedural_time_slot.appointments.exists():
            other_appointment = procedural_time_slot.appointments.exclude(
                id=procedural_appointment.id
            ).first()

            if other_appointment:
                error_msg = (
                    f"Невозможно перенести запись: время в процедурном кабинете уже занято записью "
                    f"#{other_appointment.id} для пациента {other_appointment.patient.get_full_name()}."
                )
                print(f"ERROR: {error_msg}")
                raise forms.ValidationError(error_msg)

        # Сохраняем старый слот для удаления
        old_procedural_slot = procedural_appointment.time_slot

        # Обновляем слот процедурной записи
        procedural_appointment.time_slot = procedural_time_slot

        # Если изменилась дата, обновляем дату процедурной записи
        if new_time_slot.date != old_date:
            procedural_appointment.date = new_time_slot.date

        # Обновляем комментарий с именем врача
        if procedural_appointment.comment != appointment.doctor.surname:
            procedural_appointment.comment = appointment.doctor.surname

        procedural_appointment.save()
        print(f"DEBUG: Saved procedural appointment {procedural_appointment.id}")

        # Удаляем старый пустой слот
        if old_procedural_slot and not old_procedural_slot.appointments.exists():
            print(f"DEBUG: Deleting old procedural slot {old_procedural_slot.id}")
            old_procedural_slot.delete()

        print(f"DEBUG: Procedural move completed successfully")

    def _update_procedural_service(self, appointment):
        """Всегда обновляет услугу в процедурной записи на ту же что и в основной записи"""
        print(f"DEBUG: Updating procedural service for appointment {appointment.id}")

        # Находим процедурную запись
        procedural_appointment = Appointment.objects.filter(
            previous_appointment=appointment,
            time_slot__cabinet__number=6,
        ).first()

        if not procedural_appointment:
            print(f"DEBUG: No procedural appointment found to update service")
            return

        # Всегда обновляем на ту же услугу что и в основной записи
        if appointment.service:
            print(f"DEBUG: Appointment service: {appointment.service.name}")
            procedural_appointment.service = appointment.service
            procedural_appointment.price_at_appointment = appointment.service.price
            procedural_appointment.save()
            print(
                f"DEBUG: Updated procedural appointment #{procedural_appointment.id} service to: {appointment.service.name}"
            )
        else:
            print(f"DEBUG: Appointment has no service, cannot update procedural")

    def check_for_procedural_appointment_debug(self, appointment):
        """Отладочная функция для проверки процедурной записи"""
        from appointments.models import AppointmentChain

        print("=== DEBUG: Checking for procedural appointment ===")
        print(f"Appointment ID: {appointment.id}")
        print(f"Appointment doctor: {appointment.doctor.surname}")
        print(f"Appointment cabinet: {appointment.cabinet.number}")

        # Все связанные записи через AppointmentChain
        chains = AppointmentChain.objects.filter(main_appointment=appointment)
        print(f"Total chains: {chains.count()}")

        for chain in chains:
            print(f"  Chain {chain.id}: type={chain.chain_type}")
            if chain.related_appointment:
                related = chain.related_appointment
                print(f"    Related appointment {related.id}:")
                print(
                    f"      Doctor: {related.doctor.surname if related.doctor else 'None'}"
                )
                print(
                    f"      Cabinet: {related.cabinet.number if related.cabinet else 'None'}"
                )
                print(f"      Time: {related.start_time}-{related.end_time}")

        # Проверяем через is_consecutive
        consecutive = Appointment.objects.filter(previous_appointment=appointment)
        print(f"Consecutive appointments: {consecutive.count()}")
        for app in consecutive:
            print(f"  Consecutive appointment {app.id}:")
            print(f"    Doctor: {app.doctor.surname if app.doctor else 'None'}")
            print(f"    Cabinet: {app.cabinet.number if app.cabinet else 'None'}")

        return chains.exists() or consecutive.exists()


class ProceduralAppointmentForm(ProceduralAppointmentBaseForm, forms.ModelForm):
    """Форма создания записи в процедурный кабинет с поддержкой цепочек"""

    class Meta:
        model = Appointment
        fields = ["service", "insurance_type", "needs_reschedule", "comment"]

    def __init__(self, *args, **kwargs):
        self.selected_date = kwargs.pop("selected_date", None)

        # Убираем doctor и time_slot из kwargs, так как они не нужны для процедурной формы
        doctor = None  # Для процедурного кабинета - это медсестра
        time_slot = None

        # Вызываем инициализацию родительских классов отдельно
        forms.ModelForm.__init__(self, *args, **kwargs)
        ProceduralAppointmentBaseForm.__init__(
            self,
            *args,
            **kwargs,
            doctor=doctor,
            time_slot=time_slot,
            selected_date=self.selected_date,
        )

        # Устанавливаем сегодняшнюю дату как дефолтную
        if not self.selected_date:
            self.selected_date = timezone.now().date()

        # Обновляем queryset для услуги
        self._update_service_queryset()

    def _update_service_queryset(self):
        """Обновляет queryset услуг после инициализации формы"""
        from timetable.models import MedicalServiceCategory

        nurse_categories = [
            MedicalServiceCategory.MEDICAL_BLOCKADES,
            MedicalServiceCategory.ANALYZES,
        ]

        nurse_services = MedicalService.objects.filter(
            category__in=nurse_categories, is_active=True
        )

        self.fields["service"].queryset = nurse_services

    @transaction.atomic
    def save(self, commit=True):
        """Создание процедурной записи с возможностью цепочек"""
        if not commit:
            return forms.ModelForm.save(self, commit=False)

        try:
            with transaction.atomic():
                # ВАЖНО: Проверяем доступность времени в процедурном кабинете ПЕРЕД созданием пациента
                start_time = self.cleaned_data.get("procedural_start_time")
                end_time = self.cleaned_data.get("procedural_end_time")

                # Проверяем доступность времени в процедурном кабинете
                if not self._check_procedural_time_availability(start_time, end_time):
                    raise forms.ValidationError(
                        "Невозможно создать запись: выбранное время в процедурном кабинете уже занято. "
                        "Пожалуйста, выберите другое время."
                    )

                # Создание/поиск пациента (общая логика)
                patient_data = self.get_patient_data()
                patient, created = PatientService.get_or_create_patient(patient_data)

                # Создание основной процедурной записи
                appointment = forms.ModelForm.save(self, commit=False)
                appointment.patient = patient

                # Создаем слот для процедурного кабинета
                time_slot = self._create_procedural_slot(start_time, end_time)

                # Проверяем доступность слота перед использованием
                if not time_slot.is_available():
                    raise forms.ValidationError(
                        "Невозможно создать запись: выбранное время в процедурном кабинете уже занято. "
                        "Пожалуйста, выберите другое время."
                    )

                appointment.time_slot = time_slot
                appointment.is_chain_main = True

                # Определяем тип цепочки
                appointment_chain_type = self.cleaned_data.get("appointment_chain_type")
                if appointment_chain_type in ["another_doctor", "multiple"]:
                    appointment.chain_type = Appointment.ChainType.MULTIPLE_DOCTORS
                else:
                    appointment.chain_type = Appointment.ChainType.SINGLE

                # Устанавливаем цену
                self._set_appointment_price(appointment)

                # Сохраняем общую сумму
                total_sum = self.cleaned_data.get("total_sum")
                if total_sum:
                    appointment.total_with_blood_tests = total_sum

                # ВАЖНО: Сохраняем основную запись
                appointment.save()

                # Обработка анализов крови (если есть)
                self._handle_blood_tests(appointment)

                # Обработка дополнительных записей к другим врачам
                if appointment_chain_type in ["another_doctor", "multiple"]:
                    # ВАЖНО: Проверяем доступность времени для дополнительных записей перед их созданием
                    additional_data = self.cleaned_data.get(
                        "additional_appointments_data"
                    )
                    if additional_data:
                        appointments_list = json.loads(additional_data)
                        for i, appointment_data in enumerate(
                            appointments_list, start=1
                        ):
                            self._validate_additional_appointment_time(
                                appointment_data, i, appointment
                            )

                    # Создаем записи к врачам только если основная запись создана успешно
                    self._handle_additional_appointments(appointment)

                return appointment

        except forms.ValidationError as e:
            raise
        except IntegrityError as e:
            if "unique_doctor_time_slot" in str(e):
                raise forms.ValidationError(
                    "Невозможно создать запись: выбранное время уже занято другим пациентом."
                )
            raise

    def _check_procedural_time_availability(self, start_time, end_time):
        """Проверяет доступность времени в процедурном кабинете"""
        try:
            from appointments.services import ProceduralAppointmentService
            from timetable.models import Cabinet

            date = self.selected_date or timezone.now().date()
            procedural_cabinet = Cabinet.objects.get(number=6)

            # Проверяем конфликтующие слоты в процедурном кабинете
            from timetable.models import TimeSlot

            conflicting_slots = TimeSlot.get_conflicting_slots(
                date=date,
                start_time=start_time,
                end_time=end_time,
                cabinet=procedural_cabinet,
            ).filter(appointments__isnull=False)

            return not conflicting_slots.exists()

        except Exception:
            return False

    def _create_procedural_slot(self, start_time, end_time):
        """Создает или находит существующий временной слот для процедурного кабинета"""
        from appointments.services import ProceduralAppointmentService

        date = self.selected_date or timezone.now().date()

        time_slot = ProceduralAppointmentService.create_or_get_procedural_slot(
            date=date,
            start_time=start_time,
            end_time=end_time,
            doctor=None,  # Для процедурного кабинета врач - медсестра
        )

        return time_slot

    def _validate_additional_appointment_time(
        self, appointment_data, order, main_appointment
    ):
        """Проверяет доступность времени для дополнительной записи"""
        try:
            doctor_id = appointment_data.get("doctor_id")
            service_id = appointment_data.get("service_id")
            time_slot_id = appointment_data.get("time_slot_id")

            if not all([doctor_id, service_id, time_slot_id]):
                return

            time_slot = TimeSlot.objects.get(id=time_slot_id)

            # Проверяем доступность слота
            if not time_slot.is_available():
                raise forms.ValidationError(
                    f"Ошибка в дополнительной записи #{order}: "
                    f"Слот {time_slot.start_time} уже занят. "
                    "Пожалуйста, выберите другое время."
                )

        except TimeSlot.DoesNotExist:
            raise forms.ValidationError(
                f"Ошибка в дополнительной записи #{order}: выбранный временной слот не существует"
            )

    def _handle_blood_tests(self, appointment):
        """Обработка выбранных анализов крови"""
        selected_blood_tests_input = self.cleaned_data.get(
            "selected_blood_tests_input", ""
        )

        if selected_blood_tests_input:
            try:
                selected_blood_tests_input = selected_blood_tests_input.strip()
                test_ids = [
                    int(id.strip())
                    for id in selected_blood_tests_input.split(",")
                    if id.strip() and id.strip().isdigit()
                ]

                selected_blood_tests = BloodTest.objects.filter(id__in=test_ids)

                # Сохраняем выбранные анализы
                for test in selected_blood_tests:
                    AppointmentBloodTest.objects.create(
                        appointment=appointment, blood_test=test
                    )

                # Обновляем комментарий с информацией об анализах
                self._update_appointment_comment(appointment, selected_blood_tests)

            except (ValueError, TypeError) as e:
                raise forms.ValidationError("Неверный формат выбранных анализов")

    def _update_appointment_comment(self, appointment, selected_blood_tests):
        """Обновляет комментарий с информацией об анализах"""
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
            appointment.save()

    def _handle_additional_appointments(self, main_appointment):
        """Обработка дополнительных записей к другим врачам (общая логика)"""
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

                        # Проверяем, есть ли процедурные данные для этой записи
                        procedural_info = None
                        if procedural_list:
                            for item in procedural_list:
                                if str(item.get("index")) == str(
                                    appointment_data.get("index")
                                ):
                                    procedural_info = item
                                    break

                        # Создаем процедурную запись если нужно
                        if procedural_info and procedural_info.get("needs_procedural"):
                            ProceduralAppointmentService.create_procedural_for_appointment(
                                additional_appointment,
                                main_appointment=additional_appointment,
                            )

                except (json.JSONDecodeError, KeyError) as e:
                    raise forms.ValidationError(
                        f"Ошибка обработки данных дополнительных записей: {str(e)}"
                    )

    def _create_additional_appointment(self, main_appointment, appointment_data, order):
        """Создание одной дополнительной записи (общая логика)"""
        try:
            # Получаем объекты из данных
            doctor_id = appointment_data.get("doctor_id")
            service_id = appointment_data.get("service_id")
            time_slot_id = appointment_data.get("time_slot_id")
            comment = appointment_data.get("comment", "")
            insurance_type = appointment_data.get("insurance_type", "paid")

            if not all([doctor_id, service_id, time_slot_id]):
                raise ValueError("Не все обязательные поля заполнены")

            doctor = Doctor.objects.get(id=doctor_id)
            service = MedicalService.objects.get(id=service_id)
            time_slot = TimeSlot.objects.get(id=time_slot_id)

            # Проверяем доступность слота (повторная проверка для надежности)
            if not time_slot.is_available():
                raise forms.ValidationError(
                    f"Слот {time_slot.start_time} у врача {doctor.surname} уже занят"
                )

            # Создаем дополнительную запись
            additional_appointment = Appointment.objects.create(
                time_slot=time_slot,
                patient=main_appointment.patient,
                service=service,
                insurance_type=insurance_type,
                status=Appointment.AppointmentStatus.SCHEDULED,
                comment=comment
                or f"Дополнительная запись с основной #{main_appointment.id}",
                chain_type=Appointment.ChainType.MULTIPLE_DOCTORS,
                is_chain_main=False,
            )

            # Сохраняем цену
            additional_appointment.price_at_appointment = service.price
            additional_appointment.total_with_blood_tests = service.price
            additional_appointment.save()

            # Создаем связь
            AppointmentChain.objects.create(
                main_appointment=main_appointment,
                related_appointment=additional_appointment,
                chain_type=AppointmentChain.ChainType.ANOTHER_DOCTOR,
                order=order,
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

    def _set_appointment_price(self, appointment):
        """Устанавливает цену услуги для записи"""
        if not appointment.price_at_appointment and appointment.service:
            appointment.price_at_appointment = appointment.service.price

        # Устанавливаем итоговую сумму
        if not appointment.total_with_blood_tests:
            appointment.total_with_blood_tests = appointment.price_at_appointment


class ProceduralAppointmentUpdateForm(forms.ModelForm):
    """Упрощенная форма для редактирования процедурной записи - только основные поля"""

    # ДОБАВЛЯЕМ поле для даты
    procedural_appointment_date = forms.DateField(
        required=True,
        label="Дата записи",
        widget=forms.DateInput(
            attrs={
                "type": "date",
                "class": "form-control",
                "id": "id_procedural_appointment_date",
            }
        ),
    )

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

    selected_blood_tests_input = forms.CharField(
        required=False,
        widget=forms.HiddenInput(attrs={"id": "id_selected_blood_tests"}),
        label="Выбранные анализы крови",
    )

    total_sum = forms.DecimalField(
        required=False,
        max_digits=10,
        decimal_places=2,
        widget=forms.HiddenInput(attrs={"id": "id_total_sum"}),
        label="Итоговая сумма",
    )

    class Meta:
        model = Appointment
        fields = ["service", "insurance_type", "comment"]
        widgets = {
            "service": forms.Select(attrs={"class": "form-select"}),
            "insurance_type": forms.Select(attrs={"class": "form-select"}),
            "comment": forms.Textarea(attrs={"rows": 3, "class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        self.current_appointment = kwargs.pop("current_appointment", None)
        self.selected_date = kwargs.pop("selected_date", None)
        super().__init__(*args, **kwargs)
        # Устанавливаем минимальную дату - сегодня
        from django.utils import timezone

        today = timezone.now().date()
        self.fields["procedural_appointment_date"].widget.attrs[
            "min"
        ] = today.isoformat()

        # Устанавливаем начальные значения
        if self.current_appointment and self.instance.pk:
            self._set_initial_values()

    def _set_initial_values(self):
        """Устанавливает начальные значения для формы"""

        # 1. Устанавливаем дату
        if self.current_appointment.date:
            self.fields["procedural_appointment_date"].initial = (
                self.current_appointment.date
            )

        # 2. Устанавливаем анализы крови
        selected_tests = self.current_appointment.selected_blood_tests.all()
        if selected_tests.exists():
            test_ids = [str(test.blood_test.id) for test in selected_tests]
            self.fields["selected_blood_tests_input"].initial = ",".join(test_ids)

        # 3. Устанавливаем сумму
        if self.current_appointment.total_with_blood_tests:
            self.fields["total_sum"].initial = (
                self.current_appointment.total_with_blood_tests
            )

        # 4. Устанавливаем время
        if self.current_appointment.start_time:
            self.fields["procedural_start_time"].initial = (
                self.current_appointment.start_time.strftime("%H:%M")
            )
        if self.current_appointment.end_time:
            self.fields["procedural_end_time"].initial = (
                self.current_appointment.end_time.strftime("%H:%M")
            )

        # 5. Устанавливаем услугу
        if self.current_appointment.service:
            self.fields["service"].initial = self.current_appointment.service

    def clean(self):
        """Переопределяем clean для отладки"""
        cleaned_data = super().clean()

        # Валидация времени
        start_time = cleaned_data.get("procedural_start_time")
        end_time = cleaned_data.get("procedural_end_time")
        appointment_date = cleaned_data.get("procedural_appointment_date")

        if start_time and end_time and start_time >= end_time:
            raise forms.ValidationError(
                "Время окончания должно быть позже времени начала"
            )

        # Проверка доступности времени в процедурном кабинете
        if appointment_date and start_time and end_time:
            if not self._check_procedural_time_availability(
                appointment_date, start_time, end_time
            ):
                raise forms.ValidationError(
                    "Выбранное время в процедурном кабинете уже занято. "
                    "Пожалуйста, выберите другое время."
                )

        # ВАЖНО: Если нет анализов, устанавливаем пустую строку
        if not cleaned_data.get("selected_blood_tests_input"):
            cleaned_data["selected_blood_tests_input"] = ""

        # ВАЖНО: Если нет суммы, пытаемся ее рассчитать
        if not cleaned_data.get("total_sum"):
            # Пытаемся рассчитать сумму на основе выбранных тестов и услуги
            try:
                service = (
                    cleaned_data.get("service") or self.current_appointment.service
                )
                test_ids_input = cleaned_data.get("selected_blood_tests_input", "")

                test_ids = [
                    int(id.strip())
                    for id in test_ids_input.split(",")
                    if id.strip().isdigit()
                ]
                tests_price = sum(
                    BloodTest.objects.filter(id__in=test_ids).values_list(
                        "price", flat=True
                    )
                )
                service_price = service.price if service else 0
                total = tests_price + service_price

                cleaned_data["total_sum"] = total
            except:
                cleaned_data["total_sum"] = 0

        return cleaned_data

    def _check_procedural_time_availability(self, date, start_time, end_time):
        """Проверяет доступность времени в процедурном кабинете на указанную дату"""
        try:
            from timetable.models import Cabinet, TimeSlot

            procedural_cabinet = Cabinet.objects.get(number=6)

            conflicting_slots = TimeSlot.get_conflicting_slots(
                date=date,
                start_time=start_time,
                end_time=end_time,
                cabinet=procedural_cabinet,
            ).filter(appointments__isnull=False)

            # Исключаем текущую запись из проверки
            if self.current_appointment and self.current_appointment.time_slot:
                conflicting_slots = conflicting_slots.exclude(
                    id=self.current_appointment.time_slot_id
                )

            return not conflicting_slots.exists()

        except Exception as e:
            print(f"ERROR in time availability check: {str(e)}")
            return False

    @transaction.atomic
    def save(self, commit=True):
        """Переопределяем save для ОБНОВЛЕНИЯ существующей записи"""
        # ОБНОВЛЕНИЕ существующей записи
        appointment = self.instance

        # 1. Получаем новые дату и время
        new_date = self.cleaned_data.get("procedural_appointment_date")
        start_time = self.cleaned_data.get("procedural_start_time")
        end_time = self.cleaned_data.get("procedural_end_time")

        # 2. Проверяем, изменились ли дата или время
        date_changed = new_date and new_date != appointment.date
        time_changed = False

        if start_time and end_time and appointment.time_slot:
            current_start = appointment.time_slot.start_time.strftime("%H:%M")
            current_end = appointment.time_slot.end_time.strftime("%H:%M")
            new_start = (
                start_time.strftime("%H:%M")
                if hasattr(start_time, "strftime")
                else str(start_time)
            )
            new_end = (
                end_time.strftime("%H:%M")
                if hasattr(end_time, "strftime")
                else str(end_time)
            )

            time_changed = current_start != new_start or current_end != new_end

        # 3. Если дата или время изменились, создаем/ищем новый слот
        if date_changed or time_changed:

            # Создаем новый слот или используем существующий
            from appointments.services import ProceduralAppointmentService

            time_slot = ProceduralAppointmentService.create_or_get_procedural_slot(
                date=new_date,  # Используем новую дату
                start_time=start_time,
                end_time=end_time,
                doctor=appointment.doctor,
            )

            # Проверяем доступность (кроме текущей записи)
            if time_slot.id != appointment.time_slot_id:
                if time_slot.appointments.exclude(id=appointment.id).exists():
                    raise forms.ValidationError(
                        "Выбранное время уже занято другой записью. Пожалуйста, выберите другое время."
                    )

            appointment.time_slot = time_slot

        # 4. Обновляем остальные поля
        appointment.service = self.cleaned_data.get("service") or appointment.service
        appointment.insurance_type = (
            self.cleaned_data.get("insurance_type") or appointment.insurance_type
        )

        # 5. Сохраняем комментарий как есть (без добавления информации об анализах)
        user_comment = self.cleaned_data.get("comment", "")
        if user_comment != appointment.comment:
            appointment.comment = user_comment
        # 6. Сохраняем общую сумму
        total_sum = self.cleaned_data.get("total_sum")
        if total_sum:
            appointment.total_with_blood_tests = total_sum
        elif not appointment.total_with_blood_tests:
            # Если сумма не установлена, вычисляем ее
            tests_price = appointment.get_tests_price
            service_price = appointment.service.price if appointment.service else 0
            appointment.total_with_blood_tests = tests_price + service_price
        # 7. Сохраняем запись
        if commit:
            appointment.save()
            # 8. Обновляем анализы крови
            self._update_blood_tests(appointment)

        return appointment

    def _update_blood_tests(self, appointment):
        """Обновляет выбранные анализы крови"""
        selected_blood_tests_input = self.cleaned_data.get(
            "selected_blood_tests_input", ""
        )

        # Удаляем все текущие связи
        appointment.selected_blood_tests.all().delete()

        if selected_blood_tests_input and selected_blood_tests_input.strip():
            try:
                # Парсим ID анализов
                test_ids = [
                    int(id.strip())
                    for id in selected_blood_tests_input.split(",")
                    if id.strip() and id.strip().isdigit()
                ]

                # Добавляем новые
                for test_id in test_ids:
                    AppointmentBloodTest.objects.create(
                        appointment=appointment, blood_test_id=test_id
                    )

            except (ValueError, TypeError) as e:
                print(f"ERROR parsing test IDs: {str(e)}")


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
