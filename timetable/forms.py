from django import forms
from django.forms import ModelForm
from .mixins import StyleFormMixin, ServiceBasedFormMixin
from patients.mixins import PatientFieldsMixin
from .models import TimeSlot, Appointment, MedicalService, DayComment
from .services import PatientService, AppointmentService
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

        return cleaned_data

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
            appointment.save()

            # Создание процедурной записи
            if self.cleaned_data.get("needs_procedural"):
                AppointmentService.create_procedural_appointment(appointment)

            # Обработка последовательных записей
            self._handle_consecutive_appointments(appointment)

        return appointment

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


class AppointmentUpdateForm(AppointmentBaseForm):
    """Форма редактирования записи"""

    appointment_date = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
        label="Дата приема",
    )
    time_slot = forms.CharField(
        widget=forms.HiddenInput(),
        required=True,
        label="Временной слот",
    )

    class Meta(AppointmentBaseForm.Meta):
        fields = [
            "appointment_date",
            "time_slot",
            "service",
            "insurance_type",
            "needs_reschedule",
            "comment",
        ]

    def __init__(self, *args, **kwargs):
        self.current_appointment = kwargs.pop("current_appointment", None)
        super().__init__(*args, **kwargs)

        if self.current_appointment and self.instance.pk:
            self._set_initial_values()

    def _set_initial_values(self):
        """Установка начальных значений"""
        self.current_time_slot = self.instance.time_slot
        self.fields["appointment_date"].initial = self.instance.time_slot.date
        self.fields["time_slot"].initial = self.instance.time_slot.id
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

    def clean_time_slot(self):
        """Валидация временного слота"""
        time_slot_id = self.cleaned_data.get("time_slot")
        if not time_slot_id:
            raise forms.ValidationError("Временной слот обязателен для заполнения")

        try:
            time_slot = TimeSlot.objects.get(id=time_slot_id)
        except TimeSlot.DoesNotExist:
            raise forms.ValidationError("Выбранный временной слот не существует")

        # Проверка доступности слота
        current_time_slot = getattr(self.current_appointment, "time_slot", None)
        appointment_date = self.cleaned_data.get("appointment_date")

        if time_slot != current_time_slot and not time_slot.is_available():
            raise forms.ValidationError("Выбранный временной слот уже занят")

        # Проверка принадлежности врачу
        doctor = getattr(self.current_appointment, "doctor", None)
        if doctor and time_slot.doctor != doctor:
            raise forms.ValidationError("Выбранный слот не принадлежит текущему врачу")

        # Проверка соответствия дате
        if appointment_date and time_slot.date != appointment_date:
            raise forms.ValidationError(
                f"Выбранный слот не соответствует выбранной дате. "
                f"Слот на {time_slot.date}, выбрана дата {appointment_date}"
            )

        needs_procedural = self.cleaned_data.get("needs_procedural", False)
        if needs_procedural and time_slot != current_time_slot:
            can_move_procedural = self._can_move_procedural_appointment(time_slot)
            if not can_move_procedural:
                raise forms.ValidationError(
                    "Невозможно перенести запись: выбранное время в процедурном кабинете уже занято. "
                    "Пожалуйста, выберите другое время или снимите галочку 'Занять окошко в процедурном кабинете'."
                )

        return time_slot

    def _can_move_procedural_appointment(self, new_time_slot):
        """Проверяет, можно ли перенести процедурную запись на новое время"""
        try:
            from .models import Cabinet

            # Находим процедурный кабинет №6
            procedural_cabinet = Cabinet.objects.get(number=6)

            # Проверяем, есть ли занятые конфликтующие слоты в процедурном кабинете
            occupied_conflicting_slots = TimeSlot.get_conflicting_slots(
                date=new_time_slot.date,
                start_time=new_time_slot.start_time,
                end_time=new_time_slot.end_time,
                cabinet=procedural_cabinet,
            ).filter(
                appointments__isnull=False
            )  # только занятые слоты

            return not occupied_conflicting_slots.exists()

        except Exception as e:
            print(f"Ошибка при проверке процедурного кабинета: {str(e)}")
            return False

    def save(self, commit=True):
        appointment = super().save(commit=False)

        # Обновление временного слота
        time_slot = self.cleaned_data.get("time_slot")
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

            print(
                f"Обновлена процедурная запись для {main_appointment.patient.surname}"
            )

        except Exception as e:
            print(f"Ошибка при обновлении процедурной записи: {e}")
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
