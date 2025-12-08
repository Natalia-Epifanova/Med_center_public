from django import forms
from django.forms import ModelForm
from django.utils import timezone

from appointments.models import Appointment, AppointmentBloodTest
from appointments.services import AppointmentService
from appointments.validators import AppointmentValidator
from patients.mixins import PatientFieldsMixin
from patients.services import PatientService
from timetable.mixins import ServiceBasedFormMixin, StyleFormMixin
from timetable.models import BloodTest, MedicalService, TimeSlot
from timetable.utils import get_doctor_services, validate_pishchelev_restrictions


class AppointmentBaseForm(
    StyleFormMixin, PatientFieldsMixin, ServiceBasedFormMixin, ModelForm
):
    """Базовая форма для записи на прием"""

    ADDITIONAL_SERVICE_CHOICES = [
        ("none", "Только одна услуга"),
        ("additional", "Добавить вторую услугу к этому же врачу"),
        ("two_slots", "Занять два окошка для одной услуги"),
    ]

    service = forms.ModelChoiceField(
        queryset=MedicalService.objects.none(),
        widget=forms.Select(attrs={"class": "form-select"}),
        label="Услуга",
    )
    appointment_type = forms.ChoiceField(
        choices=ADDITIONAL_SERVICE_CHOICES,
        initial="none",
        widget=forms.RadioSelect(),
        label="Тип записи",
    )
    additional_service = forms.ModelChoiceField(
        queryset=MedicalService.objects.none(),
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
        label="Вторая услуга",
    )
    needs_procedural = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
        label="Занять окошко в процедурном кабинете",
        help_text="Автоматически займет такое же время в процедурном кабинете",
    )
    total_sum = forms.DecimalField(
        required=False,
        widget=forms.HiddenInput(attrs={"id": "id_total_sum"}),
        decimal_places=2,
        max_digits=10,
        label="Итоговая сумма",
    )

    class Meta:
        model = Appointment
        fields = ["service", "insurance_type", "needs_reschedule", "comment"]
        widgets = {
            "insurance_type": forms.Select(attrs={"class": "form-select"}),
            "needs_reschedule": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
            "comment": forms.Textarea(attrs={"rows": 3, "class": "form-control"}),
        }
        labels = {
            "insurance_type": "Тип оплаты",
            "needs_reschedule": "Требуется перезапись на более ранний срок",
            "comment": "Комментарий",
        }

    def clean(self):
        cleaned_data = super().clean()

        # Валидация данных пациента
        patient_data = self._get_patient_data()
        cleaned_patient_data = PatientService.clean_patient_data(patient_data)

        # Валидация дополнительной услуги
        AppointmentValidator.validate_additional_service(
            cleaned_data.get("appointment_type"), cleaned_data.get("additional_service")
        )

        # Валидация последовательных записей
        time_slot = getattr(self, "time_slot", None)
        if (
            cleaned_data.get("appointment_type") in ["additional", "two_slots"]
            and time_slot
        ):
            current_time_slot = getattr(self, "current_time_slot", None)
            AppointmentValidator.validate_consecutive_slot(time_slot, current_time_slot)

        # ВАЛИДАЦИЯ ДЛЯ ВРАЧА ПИЩЕЛЕВА П.В. с использованием утилит
        self._validate_pishchelev_restrictions(cleaned_data)

        return cleaned_data

    def _validate_pishchelev_restrictions(self, cleaned_data):
        """Проверка ограничений для врача Пищелева П.В."""
        doctor = None

        # Получаем врача в зависимости от контекста
        if hasattr(self, "time_slot") and self.time_slot:
            doctor = self.time_slot.doctor
        elif hasattr(self, "current_appointment") and self.current_appointment:
            doctor = self.current_appointment.doctor
        elif hasattr(self, "doctor") and self.doctor:
            doctor = self.doctor

        service = cleaned_data.get("service")
        time_slot = getattr(self, "time_slot", None)

        # Используем утилиту для валидации
        validate_pishchelev_restrictions(doctor, service, time_slot)

    def _get_patient_data(self):
        """Извлекает данные пациента"""
        return {
            field: self.cleaned_data.get(field)
            for field in [
                "surname",
                "first_name",
                "last_name",
                "phone_number",
                "card_number",
                "date_of_birth",
            ]
        }


class AppointmentForm(AppointmentBaseForm):
    """Форма создания записи"""

    def __init__(self, *args, **kwargs):
        self.time_slot = kwargs.pop("time_slot", None)
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()

        # ВАЖНО: Обновляем total_sum из POST данных если он есть
        if "total_sum" in self.data and self.data["total_sum"]:
            try:
                cleaned_data["total_sum"] = float(self.data["total_sum"])
            except (ValueError, TypeError):
                pass

        return cleaned_data

    def save(self, commit=True):
        # Создание/поиск пациента
        patient_data = self._get_patient_data()
        patient, created = PatientService.get_or_create_patient(patient_data)

        # Создание записи
        appointment = super().save(commit=False)
        appointment.time_slot = self.time_slot
        appointment.patient = patient

        # Проверка процедурной записи
        if self.cleaned_data.get("needs_procedural"):
            if not AppointmentService.can_create_procedural_appointment(appointment):
                raise forms.ValidationError(
                    "Невозможно создать запись: выбранное время в процедурном кабинете уже занято."
                )

        # ВАЖНО: Сохраняем цену услуги ДО сохранения записи
        if appointment.service and not appointment.price_at_appointment:
            appointment.price_at_appointment = appointment.service.price

        # ДЛЯ ВСЕХ ЗАПИСЕЙ: Сохраняем общую сумму
        # Сначала проверяем hidden поле total_sum, потом используем цену услуги
        total_sum = self.cleaned_data.get("total_sum")
        if total_sum:
            appointment.total_with_blood_tests = total_sum
        else:
            appointment.total_with_blood_tests = appointment.price_at_appointment

        if commit:
            try:
                appointment.save()

                # Создание процедурной записи
                if self.cleaned_data.get("needs_procedural"):
                    procedural_appointment = (
                        AppointmentService.create_procedural_appointment(appointment)
                    )
                    # Для процедурной записи тоже сохраняем сумму
                    if procedural_appointment:
                        if not procedural_appointment.price_at_appointment:
                            procedural_appointment.price_at_appointment = (
                                procedural_appointment.service.price
                            )
                        procedural_appointment.total_with_blood_tests = (
                            procedural_appointment.price_at_appointment
                        )
                        procedural_appointment.save()

                # Обработка последовательных записей
                self._handle_consecutive_appointments(appointment)

            except Exception as e:
                # Обрабатываем ошибку уникальности слота
                if "unique_doctor_time_slot" in str(e):
                    raise forms.ValidationError(
                        "Невозможно создать запись: выбранное время уже занято другим пациентом. "
                        "Пожалуйста, обновите страницу и выберите другое время."
                    )
                # Обрабатываем другие ошибки базы данных
                elif "duplicate key" in str(e).lower():
                    raise forms.ValidationError(
                        "Невозможно создать запись: произошел конфликт расписания. "
                        "Пожалуйста, обновите страницу и попробуйте снова."
                    )
                else:
                    # Пробрасываем оригинальную ошибку для отладки
                    raise

        return appointment

    def _handle_consecutive_appointments(self, main_appointment):
        """Обработка последовательных записей"""
        appointment_type = self.cleaned_data.get("appointment_type")

        if appointment_type in ["additional", "two_slots"]:
            next_slot = main_appointment.time_slot.get_next_consecutive_slot()

            if next_slot and next_slot.is_available():
                try:
                    consecutive_appointment = (
                        AppointmentService.create_consecutive_appointment(
                            main_appointment,
                            appointment_type,
                            next_slot,
                            self.cleaned_data.get("additional_service"),
                        )
                    )
                    if consecutive_appointment:
                        # ВАЖНО: Сохраняем сумму для последовательных записей
                        if (
                            not consecutive_appointment.price_at_appointment
                            and consecutive_appointment.service
                        ):
                            consecutive_appointment.price_at_appointment = (
                                consecutive_appointment.service.price
                            )
                        consecutive_appointment.total_with_blood_tests = (
                            consecutive_appointment.price_at_appointment
                        )
                        consecutive_appointment.save()
                except Exception as e:
                    # Обрабатываем ошибки при создании последовательных записей
                    if "unique_doctor_time_slot" in str(e):
                        raise forms.ValidationError(
                            "Невозможно создать дополнительную запись: следующий временной слот уже занят. "
                            "Пожалуйста, выберите другой тип записи или другое время."
                        )
                    else:
                        raise


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

        # Получаем врача из текущей записи
        doctor = self.current_appointment.doctor if self.current_appointment else None

        # Получаем текущую услугу если есть
        current_service = None
        if self.current_appointment and self.current_appointment.service:
            current_service = self.current_appointment.service

        # Используем утилиту для получения услуг врача
        services_queryset = get_doctor_services(doctor, current_service)

        self.fields["service"].queryset = services_queryset

        # Также обновляем queryset для additional_service
        if "additional_service" in self.fields:
            self.fields["additional_service"].queryset = services_queryset

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
        patient_data = self._get_patient_data()
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
                # Обновляем существующую процедурную запись
                self._update_procedural_appointment(
                    main_appointment, existing_procedural
                )
            else:
                # Создаем новую процедурную запись
                procedural_appointment = (
                    AppointmentService.create_procedural_appointment(main_appointment)
                )
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
            from .models import Cabinet, Doctor, TimeSlot

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
        patient_data = self._get_patient_data()
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
        from timetable.models import Cabinet, Doctor, TimeSlot

        try:
            procedural_cabinet = Cabinet.objects.get(number=6)
            nurse_doctor = Doctor.objects.filter(specialization="nurse").first()
            date = self.selected_date or timezone.now().date()

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
        patient_data = self._get_patient_data()
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
