from django import forms
from django.forms import ModelForm
from .mixins import StyleFormMixin, ServiceBasedFormMixin
from patients.mixins import PatientFieldsMixin
from .models import TimeSlot, Appointment, MedicalService, DayComment
from .services import PatientService, AppointmentService
from .utils import validate_pishchelev_restrictions, get_doctor_services
from .validators import AppointmentValidator


class TimeSlotForm(StyleFormMixin, ModelForm):
    """Упрощенная форма для добавления временных слотов"""

    ADD_TYPE_CHOICES = [
        ("single", "Добавить один слот"),
        ("multiple", "Добавить несколько слотов с интервалом"),
    ]

    add_type = forms.ChoiceField(
        choices=ADD_TYPE_CHOICES,
        widget=forms.RadioSelect(attrs={"class": "form-check-input"}),
        initial="single",
        label="Тип добавления",
    )

    # Поля для одиночного добавления
    single_start_time = forms.TimeField(
        widget=forms.TimeInput(attrs={"type": "time"}),
        required=False,
        label="Время начала",
    )
    single_end_time = forms.TimeField(
        widget=forms.TimeInput(attrs={"type": "time"}),
        required=False,
        label="Время окончания",
    )
    single_slot_type = forms.ChoiceField(
        choices=TimeSlot.SLOT_TYPE_CHOICES,
        initial="working",
        required=False,
        label="Тип слота",
    )
    single_description = forms.CharField(
        required=False,
        max_length=200,
        label="Описание",
        widget=forms.TextInput(attrs={"placeholder": "Например: Обед"}),
    )

    # Поля для множественного добавления
    multiple_start_time = forms.TimeField(
        widget=forms.TimeInput(attrs={"type": "time"}),
        required=False,
        label="Время начала диапазона",
    )
    multiple_end_time = forms.TimeField(
        widget=forms.TimeInput(attrs={"type": "time"}),
        required=False,
        label="Время окончания диапазона",
    )
    interval = forms.IntegerField(
        min_value=5,
        max_value=120,
        initial=20,
        required=False,
        label="Интервал (минуты)",
    )

    class Meta:
        model = TimeSlot
        fields = ["date", "cabinet", "doctor"]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
        }
        labels = {
            "date": "Дата расписания",
            "cabinet": "Кабинет",
            "doctor": "Врач",
        }


class TimeSlotUpdateForm(StyleFormMixin, ModelForm):
    """Форма для редактирования существующего слота"""

    class Meta:
        model = TimeSlot
        fields = [
            "date",
            "cabinet",
            "doctor",
            "start_time",
            "end_time",
            "slot_type",
            "description",
        ]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "start_time": forms.TimeInput(attrs={"type": "time"}),
            "end_time": forms.TimeInput(attrs={"type": "time"}),
        }
        labels = {
            "date": "Дата расписания",
            "cabinet": "Кабинет",
            "doctor": "Врач",
            "start_time": "Время начала",
            "end_time": "Время окончания",
            "slot_type": "Тип слота",
            "description": "Описание",
        }


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

        if commit:
            try:
                appointment.save()

                # Создание процедурной записи
                if self.cleaned_data.get("needs_procedural"):
                    AppointmentService.create_procedural_appointment(appointment)

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

    def _set_service_queryset(self):
        """Устанавливает queryset для поля service с учетом врача"""
        from .utils import get_doctor_services

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

    def clean(self):
        """Дополнительная валидация всей формы"""
        cleaned_data = super().clean()

        # Получаем объект time_slot из clean_time_slot_id
        time_slot = cleaned_data.get("time_slot_id")  # Это объект TimeSlot
        appointment_date = cleaned_data.get("appointment_date")

        if appointment_date and time_slot:
            if appointment_date != time_slot.date:
                raise forms.ValidationError(
                    f"Выбранная дата приема ({appointment_date}) не совпадает с датой слота ({time_slot.date})."
                )

        return cleaned_data

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
                AppointmentService.create_procedural_appointment(main_appointment)
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

    def __init__(self, *args, **kwargs):
        # Обрабатываем параметр selected_date
        self.selected_date = kwargs.pop("selected_date", None)
        # Убираем параметры, которые не нужны для процедурной формы
        kwargs.pop("time_slot", None)
        kwargs.pop("doctor", None)
        super().__init__(*args, **kwargs)

        # Убираем поле needs_procedural и procedural_time_slot
        if "needs_procedural" in self.fields:
            del self.fields["needs_procedural"]
        if "procedural_time_slot" in self.fields:
            del self.fields["procedural_time_slot"]

        # Настраиваем queryset для услуг - только те, что доступны медсестре
        self.set_nurse_services()

    def set_nurse_services(self):
        """Устанавливает queryset услуг, доступных для медсестры"""
        from .models import MedicalServiceCategory

        # Категории услуг, которые может оказывать медсестра
        nurse_categories = [
            MedicalServiceCategory.MEDICAL_BLOCKADES,
            MedicalServiceCategory.ANALYZES,
            # Добавьте другие категории, если нужно
        ]

        # Получаем услуги для указанных категорий
        nurse_services = MedicalService.objects.filter(
            category__in=nurse_categories, is_active=True
        )

        # Обновляем queryset для поля service
        self.fields["service"].queryset = nurse_services

        # Также обновляем queryset для additional_service
        if "additional_service" in self.fields:
            self.fields["additional_service"].queryset = nurse_services

    def clean(self):
        cleaned_data = super().clean()

        # Валидация времени
        start_time = cleaned_data.get("procedural_start_time")
        end_time = cleaned_data.get("procedural_end_time")

        if start_time and end_time and start_time >= end_time:
            raise forms.ValidationError(
                "Время окончания должно быть позже времени начала"
            )

        return cleaned_data

    def save(self, commit=True):
        # Создание/поиск пациента
        patient_data = self._get_patient_data()
        patient, created = PatientService.get_or_create_patient(patient_data)

        # Создание записи
        appointment = super().save(commit=False)

        # Создаем новый слот
        start_time = self.cleaned_data.get("procedural_start_time")
        end_time = self.cleaned_data.get("procedural_end_time")
        time_slot = self.create_procedural_slot(start_time, end_time)

        appointment.time_slot = time_slot
        appointment.patient = patient

        if commit:
            appointment.save()
            # Обработка последовательных записей
            self._handle_consecutive_appointments(appointment)

        return appointment

    def create_procedural_slot(self, start_time, end_time):
        """Создает временный слот для процедурного кабинета"""
        from django.utils import timezone
        from .models import Cabinet, Doctor, TimeSlot

        try:
            procedural_cabinet = Cabinet.objects.get(number=6)
            nurse_doctor = Doctor.objects.filter(specialization="nurse").first()

            # Используем дату из параметра или текущую дату
            date = self.selected_date or timezone.now().date()

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
            raise forms.ValidationError(f"Ошибка при создании слота: {str(e)}")

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
                    consecutive_appointment.save()


class DayCommentForm(StyleFormMixin, ModelForm):
    """Форма для комментария дня"""

    class Meta:
        model = DayComment
        fields = ["comment"]
        widgets = {
            "comment": forms.Textarea(
                attrs={
                    "rows": 3,
                    "class": "form-control",
                    "placeholder": "Например: Роза с 8-14",
                }
            ),
        }
        labels = {
            "comment": "Комментарий для дня",
        }
