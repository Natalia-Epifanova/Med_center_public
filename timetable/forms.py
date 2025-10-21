from django import forms
from django.forms import ModelForm

from .mixins import (
    StyleFormMixin,
    PatientFieldsMixin,
    PatientHandlingMixin,
    ConsecutiveAppointmentMixin,
)
from .models import TimeSlot, Appointment, MedicalService, Patient, Cabinet


class PatientForm(StyleFormMixin, ModelForm):
    """Форма для создания/редактирования пациента"""

    class Meta:
        model = Patient
        fields = [
            "surname",
            "first_name",
            "last_name",
            "phone_number",
            "card_number",
            "date_of_birth",
        ]
        widgets = {
            "date_of_birth": forms.DateInput(attrs={"type": "date"}),
        }
        labels = {
            "surname": "Фамилия*",
            "first_name": "Имя*",
            "last_name": "Отчество",
            "phone_number": "Телефон",
            "card_number": "Номер карты",
            "date_of_birth": "Дата рождения",
        }


class TimeSlotForm(StyleFormMixin, ModelForm):
    """Упрощенная форма для добавления временных слотов"""

    class Meta:
        model = TimeSlot
        fields = [
            "date",
            "cabinet",
            "doctor",
        ]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
        }
        labels = {
            "date": "Дата расписания",
            "cabinet": "Кабинет",
            "doctor": "Врач",
        }

    # Оставляем только кастомные поля
    ADD_TYPE_CHOICES = [
        ("single", "Добавить один слот"),
        ("multiple", "Добавить несколько слотов с интервалом"),
    ]
    add_type = forms.ChoiceField(
        label="Тип добавления",
        choices=ADD_TYPE_CHOICES,
        widget=forms.RadioSelect(attrs={"class": "form-check-input"}),
        initial="single",
    )

    # Поля для одиночного добавления
    single_start_time = forms.TimeField(
        label="Время начала",
        widget=forms.TimeInput(attrs={"type": "time"}),
        required=False,
    )
    single_end_time = forms.TimeField(
        label="Время окончания",
        widget=forms.TimeInput(attrs={"type": "time"}),
        required=False,
    )
    single_slot_type = forms.ChoiceField(
        label="Тип слота",
        choices=TimeSlot.SLOT_TYPE_CHOICES,
        initial="working",
        required=False,
    )
    single_description = forms.CharField(
        label="Описание",
        widget=forms.TextInput(attrs={"placeholder": "Например: Обед"}),
        required=False,
        max_length=200,
    )

    # Поля для множественного добавления
    multiple_start_time = forms.TimeField(
        label="Время начала диапазона",
        widget=forms.TimeInput(attrs={"type": "time"}),
        required=False,
    )
    multiple_end_time = forms.TimeField(
        label="Время окончания диапазона",
        widget=forms.TimeInput(attrs={"type": "time"}),
        required=False,
    )
    interval = forms.IntegerField(
        label="Интервал (минуты)",
        min_value=5,
        max_value=120,
        initial=20,
        widget=forms.NumberInput(),
        required=False,
    )

    def clean(self):
        cleaned_data = super().clean()
        add_type = cleaned_data.get("add_type")

        if add_type == "single":
            start_time = cleaned_data.get("single_start_time")
            end_time = cleaned_data.get("single_end_time")

            if not start_time or not end_time:
                raise forms.ValidationError(
                    "Для одиночного слота необходимо указать время начала и окончания"
                )

            if start_time >= end_time:
                raise forms.ValidationError(
                    "Время начала должно быть раньше времени окончания"
                )

        elif add_type == "multiple":
            start_time = cleaned_data.get("multiple_start_time")
            end_time = cleaned_data.get("multiple_end_time")
            interval = cleaned_data.get("interval")

            if not start_time or not end_time:
                raise forms.ValidationError(
                    "Для нескольких слотов необходимо указать время начала и окончания"
                )

            if start_time >= end_time:
                raise forms.ValidationError(
                    "Время начала должно быть раньше времени окончания"
                )

            if not interval or interval <= 0:
                raise forms.ValidationError("Интервал должен быть положительным числом")

        return cleaned_data


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
            "description": forms.TextInput(attrs={"placeholder": "Например: Обед"}),
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
    StyleFormMixin,
    PatientFieldsMixin,
    PatientHandlingMixin,
    ConsecutiveAppointmentMixin,
    ModelForm,
):
    """Базовая форма для записи на прием"""

    ADDITIONAL_SERVICE_CHOICES = [
        ("none", "Только одна услуга"),
        ("additional", "Добавить вторую услугу к этому же врачу"),
        ("two_slots", "Занять два окошка для одной услуги"),
    ]

    service = forms.ModelChoiceField(
        queryset=MedicalService.objects.none(),
        label="Услуга*",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    appointment_type = forms.ChoiceField(
        choices=ADDITIONAL_SERVICE_CHOICES,
        initial="none",
        label="Тип записи",
        widget=forms.RadioSelect(),
    )

    additional_service = forms.ModelChoiceField(
        queryset=MedicalService.objects.none(),
        required=False,
        label="Вторая услуга",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    needs_procedural = forms.BooleanField(
        required=False,
        label="Занять окошко в процедурном кабинете",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
        help_text="Автоматически займет такое же время в процедурном кабинете",
        initial=True,
    )

    class Meta:
        model = Appointment
        fields = ["service", "insurance_type", "needs_reschedule", "comment"]
        widgets = {
            "insurance_type": forms.Select(attrs={"class": "form-select"}),
            "needs_reschedule": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
            "comment": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": "Комментарий для администратора",
                    "class": "form-control",
                }
            ),
        }
        labels = {
            "insurance_type": "Тип оплаты*",
            "needs_reschedule": "Требуется перезапись на более ранний срок",
            "comment": "Комментарий",
        }

    def __init__(self, *args, **kwargs):
        self.doctor = kwargs.pop("doctor", None)
        super().__init__(*args, **kwargs)

        if self.doctor:
            services = self.doctor.get_available_services()
            self.fields["service"].queryset = services
            self.fields["additional_service"].queryset = services

    def clean(self):
        cleaned_data = super().clean()
        self.clean_patient_data()  # Используем миксин

        appointment_type = cleaned_data.get("appointment_type")
        additional_service = cleaned_data.get("additional_service")
        time_slot = getattr(self, "time_slot", None)

        # Проверка для второй услуги
        if appointment_type == "additional" and not additional_service:
            raise forms.ValidationError(
                {
                    "additional_service": 'При выборе опции "Добавить вторую услугу" необходимо указать вторую услугу'
                }
            )

        # Проверка последовательных записей
        if appointment_type in ["additional", "two_slots"] and time_slot:
            current_time_slot = getattr(self, "current_time_slot", None)
            self.validate_consecutive_slot(time_slot, current_time_slot)

        return cleaned_data

    def get_patient_data(self):
        """Извлекает данные пациента из cleaned_data"""
        return {
            "surname": self.cleaned_data.get("surname"),
            "first_name": self.cleaned_data.get("first_name"),
            "last_name": self.cleaned_data.get("last_name"),
            "phone_number": self.cleaned_data.get("phone_number"),
            "card_number": self.cleaned_data.get("card_number"),
            "date_of_birth": self.cleaned_data.get("date_of_birth"),
        }


class AppointmentForm(AppointmentBaseForm):
    """Форма создания записи"""

    def __init__(self, *args, **kwargs):
        self.time_slot = kwargs.pop("time_slot", None)
        super().__init__(*args, **kwargs)
        print(f"🔔 Форма инициализирована. Time slot: {self.time_slot}")

    def save(self, commit=True):
        print("🔔 НАЧАЛО СОХРАНЕНИЯ ФОРМЫ")

        # Создаем/находим пациента
        patient_data = self.get_patient_data()
        print(f"🔔 Данные пациента: {patient_data}")

        patient, created = self.get_or_create_patient(patient_data)

        if not patient:
            raise forms.ValidationError("Не удалось создать или найти пациента")

        print(f"🔔 Пациент установлен: {patient}, created: {created}")

        # Создаем объект appointment
        appointment = super().save(commit=False)
        appointment.time_slot = self.time_slot
        appointment.patient = patient

        # ВАЖНО: Проверяем возможность создания процедурной записи ДО сохранения
        needs_procedural = self.cleaned_data.get("needs_procedural")
        print(f"🔔 Значение needs_procedural: {needs_procedural}")

        if needs_procedural:
            print("🔄 ПРЕДВАРИТЕЛЬНАЯ ПРОВЕРКА ПРОЦЕДУРНОЙ ЗАПИСИ")
            can_create_procedural = self.can_create_procedural_appointment(appointment)
            if not can_create_procedural:
                raise forms.ValidationError(
                    "Невозможно создать запись: выбранное время в процедурном кабинете уже занято. "
                    "Пожалуйста, выберите другое время или снимите галочку 'Занять окошко в процедурном кабинете'."
                )

        if commit:
            print("🔔 СОХРАНЕНИЕ COMMIT=True")

            # Сохраняем основную запись
            appointment.save()
            print(f"✅ Основная запись создана: ID={appointment.id}")

            # Обработка последовательных записей
            self.handle_consecutive_appointments(appointment)

        print("🔔 КОНЕЦ СОХРАНЕНИЯ ФОРМЫ")
        return appointment

    def can_create_procedural_appointment(self, main_appointment):
        """Проверяет, можно ли создать процедурную запись"""
        try:
            print(f"🔍 ДЕТАЛЬНАЯ проверка процедурной записи...")
            print(
                f"   Время проверки: {main_appointment.time_slot.start_time}-{main_appointment.time_slot.end_time}"
            )

            # Находим процедурный кабинет №6
            procedural_cabinet = Cabinet.objects.get(number=6)

            # Ищем ЗАНЯТЫЕ конфликтующие слоты
            occupied_conflicting_slots = TimeSlot.get_conflicting_slots(
                date=main_appointment.time_slot.date,
                start_time=main_appointment.time_slot.start_time,
                end_time=main_appointment.time_slot.end_time,
                cabinet=procedural_cabinet,
            ).filter(
                appointments__isnull=False
            )  # только занятые слоты

            if occupied_conflicting_slots.exists():
                print(
                    f"❌ Найдено {occupied_conflicting_slots.count()} занятых конфликтующих слотов:"
                )
                for slot in occupied_conflicting_slots:
                    print(f"   - {slot} - {slot.appointments.first()}")
                return False
            else:
                print("✅ Нет занятых конфликтующих слотов - можно создать")
                return True

        except Exception as e:
            print(f"❌ Ошибка при проверке: {str(e)}")
            return False

    def create_procedural_appointment(self, main_appointment):
        """Создает дублирующую запись в процедурном кабинете - УПРОЩЕННАЯ ВЕРСИЯ"""
        try:
            print(
                f"🔄 СОЗДАНИЕ процедурной записи для {main_appointment.patient.surname}"
            )

            # Находим процедурный кабинет №6
            procedural_cabinet = Cabinet.objects.get(number=6)

            # Ищем врача-медсестру
            from timetable.models import Doctor

            nurse_doctor = Doctor.objects.filter(specialization="nurse").first()
            if not nurse_doctor:
                nurse_doctor = main_appointment.doctor

            # ПРОСТАЯ ЛОГИКА: всегда создаем новый слот, но сначала проверяем конфликты
            conflicting_slots = TimeSlot.get_conflicting_slots(
                date=main_appointment.time_slot.date,
                start_time=main_appointment.time_slot.start_time,
                end_time=main_appointment.time_slot.end_time,
                cabinet=procedural_cabinet,
            ).filter(
                appointments__isnull=False
            )  # только занятые слоты

            if conflicting_slots.exists():
                print("❌ Найдены занятые конфликтующие слоты:")
                for slot in conflicting_slots:
                    print(f"   - {slot} - {slot.appointments.first()}")
                raise forms.ValidationError(
                    "Выбранное время в процедурном кабинете уже занято. "
                    "Пожалуйста, выберите другое время."
                )

            # Создаем новый слот
            procedural_slot = TimeSlot.objects.create(
                date=main_appointment.time_slot.date,
                cabinet=procedural_cabinet,
                doctor=nurse_doctor,
                start_time=main_appointment.time_slot.start_time,
                end_time=main_appointment.time_slot.end_time,
                slot_type="working",
                description="Процедурный кабинет",
            )
            print(f"✅ Создан новый слот: {procedural_slot}")

            # Создаем процедурную запись
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

            print(f"✅ УСПЕХ: создана процедурная запись {procedural_appointment.id}")
            return procedural_appointment

        except forms.ValidationError:
            raise
        except Exception as e:
            print(f"❌ КРИТИЧЕСКАЯ ОШИБКА: {str(e)}")
            import traceback

            print(f"❌ Traceback: {traceback.format_exc()}")
            return None

    def handle_consecutive_appointments(self, main_appointment):
        """Обработка последовательных записей"""
        appointment_type = self.cleaned_data.get("appointment_type")

        if appointment_type in ["additional", "two_slots"]:
            next_slot = main_appointment.time_slot.get_next_consecutive_slot()

            if next_slot and next_slot.is_available():
                consecutive_appointment = self.create_consecutive_appointment(
                    main_appointment,
                    appointment_type,
                    next_slot,
                    self.cleaned_data.get("additional_service"),
                )
                if consecutive_appointment:
                    consecutive_appointment.save()


class AppointmentUpdateForm(AppointmentBaseForm):
    """Форма редактирования записи"""

    appointment_date = forms.DateField(
        label="Дата приема*",
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )

    time_slot = forms.CharField(
        label="Временной слот*",
        widget=forms.HiddenInput(),
        required=True,
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
            self.current_time_slot = self.instance.time_slot
            self.fields["appointment_date"].initial = self.instance.time_slot.date
            self.fields["time_slot"].initial = self.instance.time_slot.id

            # Устанавливаем начальное значение для услуги
            self.fields["service"].initial = self.instance.service

            # Определяем тип записи
            if self.instance.occupies_two_slots:
                self.fields["appointment_type"].initial = "two_slots"
            elif self.instance.is_consecutive and self.instance.previous_appointment:
                self.fields["appointment_type"].initial = "additional"

            # Устанавливаем начальное значение для процедурного кабинета
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

        # Проверяем, доступен ли слот (если это не текущий слот)
        current_time_slot = getattr(self.current_appointment, "time_slot", None)
        appointment_date = self.cleaned_data.get("appointment_date")

        # Если слот изменился и не доступен
        if time_slot != current_time_slot and not time_slot.is_available():
            raise forms.ValidationError("Выбранный временной слот уже занят")

        # Проверяем, что слот принадлежит правильному врачу
        doctor = getattr(self.current_appointment, "doctor", None)
        if doctor and time_slot.doctor != doctor:
            raise forms.ValidationError("Выбранный слот не принадлежит текущему врачу")

        # Проверяем, что слот соответствует выбранной дате
        if appointment_date and time_slot.date != appointment_date:
            raise forms.ValidationError(
                f"Выбранный слот не соответствует выбранной дате. Слот на {time_slot.date}, выбрана дата {appointment_date}"
            )

        return time_slot

    def save(self, commit=True):
        appointment = super().save(commit=False)

        # Обновляем временной слот
        time_slot = self.cleaned_data.get("time_slot")
        if time_slot:
            appointment.time_slot = time_slot

        # Обновляем пациента
        patient_data = self.get_patient_data()
        patient, created = self.get_or_create_patient(patient_data)
        appointment.patient = patient

        if commit:
            appointment.save()

            # Обрабатываем процедурный кабинет
            needs_procedural = self.cleaned_data.get("needs_procedural", False)
            self.handle_procedural_appointment(appointment, needs_procedural)

            self.handle_consecutive_appointments(appointment)

        return appointment

    def handle_procedural_appointment(self, main_appointment, needs_procedural):
        """Обрабатывает создание/удаление записи в процедурном кабинете"""
        # Удаляем существующие записи в процедурном кабинете
        procedural_appointments = Appointment.objects.filter(
            previous_appointment=main_appointment, time_slot__cabinet__number=6
        )
        procedural_appointments.delete()

        # Если нужно создать новую запись
        if needs_procedural:
            self.create_procedural_appointment(main_appointment)

    def create_procedural_appointment(self, main_appointment):
        """Создает дублирующую запись в процедурном кабинете"""
        try:
            # Находим процедурный кабинет №6
            procedural_cabinet = Cabinet.objects.get(number=6)

            # Ищем существующий слот в процедурном кабинете на это же время
            procedural_slot = TimeSlot.objects.filter(
                date=main_appointment.time_slot.date,
                cabinet=procedural_cabinet,
                start_time=main_appointment.time_slot.start_time,
                end_time=main_appointment.time_slot.end_time,
                slot_type="working",
            ).first()

            # Если слота нет - создаем его
            if not procedural_slot:
                procedural_slot = TimeSlot.objects.create(
                    date=main_appointment.time_slot.date,
                    cabinet=procedural_cabinet,
                    doctor=main_appointment.doctor,
                    start_time=main_appointment.time_slot.start_time,
                    end_time=main_appointment.time_slot.end_time,
                    slot_type="working",
                    description=f"Процедурный кабинет - {main_appointment.doctor.surname}",
                )

            # Создаем дублирующую запись
            Appointment.objects.create(
                time_slot=procedural_slot,
                patient=main_appointment.patient,
                service=main_appointment.service,
                insurance_type=main_appointment.insurance_type,
                status=main_appointment.status,
                comment=f"Процедура у врача: {main_appointment.doctor.surname}",
                is_consecutive=True,
                previous_appointment=main_appointment,
            )
            print(
                f"Создана запись в процедурном кабинете для {main_appointment.patient.surname}"
            )

        except Exception as e:
            print(f"Ошибка при создании записи в процедурном кабинете: {e}")
