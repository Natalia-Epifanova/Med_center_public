from django import forms
from django.forms import ModelForm


from .models import Cabinet, Doctor, TimeSlot, Appointment, MedicalService, Patient


class StyleFormMixin:
    """
    Миксин для стилизации форм. Добавляет CSS-класс 'form-control' ко всем полям формы.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if "class" not in field.widget.attrs:
                field.widget.attrs["class"] = "form-control"


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


class AppointmentForm(StyleFormMixin, ModelForm):
    """Форма записи на прием с встроенными полями пациента"""

    # Поля пациента (встроенные в форму записи)
    surname = forms.CharField(
        max_length=50,
        label="Фамилия*",
        widget=forms.TextInput(attrs={"placeholder": "Введите фамилию"}),
    )
    first_name = forms.CharField(
        max_length=20,
        label="Имя*",
        widget=forms.TextInput(attrs={"placeholder": "Введите имя"}),
    )
    last_name = forms.CharField(
        max_length=30,
        required=False,
        label="Отчество",
        widget=forms.TextInput(attrs={"placeholder": "Введите отчество"}),
    )
    phone_number = forms.CharField(
        max_length=12,
        required=False,
        label="Телефон",
        widget=forms.TextInput(attrs={"placeholder": "+7XXXXXXXXXX"}),
    )
    card_number = forms.IntegerField(
        required=False,
        label="Номер карты",
        widget=forms.NumberInput(attrs={"placeholder": "Номер карты пациента"}),
    )
    date_of_birth = forms.DateField(
        required=False,
        label="Дата рождения",
        widget=forms.DateInput(attrs={"type": "date"}),
    )

    # Основная услуга (обязательная)
    service = forms.ModelChoiceField(
        queryset=MedicalService.objects.none(),
        label="Услуга*",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    # Опция для добавления второй услуги
    ADDITIONAL_SERVICE_CHOICES = [
        ("none", "Только одна услуга"),
        ("additional", "Добавить вторую услугу к этому же врачу"),
        ("two_slots", "Занять два окошка для одной услуги"),
    ]

    appointment_type = forms.ChoiceField(
        choices=ADDITIONAL_SERVICE_CHOICES,
        initial="none",
        label="Тип записи",
        widget=forms.RadioSelect(attrs={"class": "form-check-input"}),
    )

    # Вторая услуга (опциональная)
    additional_service = forms.ModelChoiceField(
        queryset=MedicalService.objects.none(),
        required=False,
        label="Вторая услуга",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    class Meta:
        model = Appointment
        fields = [
            "service",
            "insurance_type",
            "needs_reschedule",
            "comment",
        ]  # Добавлено service в fields
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
        self.time_slot = kwargs.pop("time_slot", None)
        self.doctor = kwargs.pop("doctor", None)
        super().__init__(*args, **kwargs)

        # ИСПРАВЛЕНИЕ: Используем get_available_services() вместо прямого фильтра
        if self.doctor:
            # Получаем услуги с учетом исключенных
            services = self.doctor.get_available_services()
            self.fields["service"].queryset = services
            self.fields["additional_service"].queryset = services

    def clean(self):
        cleaned_data = super().clean()
        appointment_type = cleaned_data.get("appointment_type")
        additional_service = cleaned_data.get("additional_service")
        time_slot = self.time_slot

        # Проверка обязательных полей пациента
        surname = cleaned_data.get("surname")
        first_name = cleaned_data.get("first_name")
        if not surname or not first_name:
            raise forms.ValidationError(
                "Фамилия и имя пациента обязательны для заполнения"
            )

        # Проверка для второй услуги
        if appointment_type == "additional" and not additional_service:
            raise forms.ValidationError(
                {
                    "additional_service": 'При выборе опции "Добавить вторую услугу" необходимо указать вторую услугу'
                }
            )

        # Проверка доступности следующего слота для последовательных записей
        if appointment_type in ["additional", "two_slots"] and time_slot:
            next_slot = time_slot.get_next_consecutive_slot()

            if not next_slot:
                raise forms.ValidationError(
                    "Следующий временной слот недоступен для последовательной записи"
                )

            if not next_slot.is_available():
                raise forms.ValidationError(
                    "Следующий временной слот уже занят другим пациентом"
                )

        return cleaned_data

    def save(self, commit=True):
        # Сохраняем основную запись
        appointment = super().save(commit=False)
        appointment.time_slot = self.time_slot

        # Получаем данные пациента
        patient_data = {
            "surname": self.cleaned_data.get("surname"),
            "first_name": self.cleaned_data.get("first_name"),
            "last_name": self.cleaned_data.get("last_name"),
            "phone_number": self.cleaned_data.get("phone_number"),
            "card_number": self.cleaned_data.get("card_number"),
            "date_of_birth": self.cleaned_data.get("date_of_birth"),
        }

        # Создаем или находим пациента
        patient, created = self._get_or_create_patient(patient_data)
        appointment.patient = patient

        if commit:
            appointment.save()

            # Создание последовательных записей
            appointment_type = self.cleaned_data.get("appointment_type")
            if appointment_type in ["additional", "two_slots"]:
                next_slot = self.time_slot.get_next_consecutive_slot()

                if next_slot:
                    if appointment_type == "additional":
                        # Вторая услуга на следующий слот
                        consecutive_appointment = Appointment(
                            time_slot=next_slot,
                            patient=appointment.patient,
                            service=self.cleaned_data["additional_service"],
                            insurance_type=appointment.insurance_type,
                            status=appointment.status,
                            is_consecutive=True,
                            previous_appointment=appointment,
                            comment=f"Последовательная запись к {appointment.service.name}",
                        )
                    else:
                        # Та же услуга на два слота
                        consecutive_appointment = Appointment(
                            time_slot=next_slot,
                            patient=appointment.patient,
                            service=appointment.service,  # Используем ту же услугу
                            insurance_type=appointment.insurance_type,
                            status=appointment.status,
                            is_consecutive=True,
                            previous_appointment=appointment,
                            occupies_two_slots=True,
                            comment=f"Продолжение услуги {appointment.service.name} (занято 2 слота)",
                        )
                    consecutive_appointment.save()

        return appointment

    def _get_or_create_patient(self, patient_data):
        """Находит существующего пациента или создает нового"""
        surname = patient_data.get("surname")
        first_name = patient_data.get("first_name")
        date_of_birth = patient_data.get("date_of_birth")

        # Проверяем, существует ли пациент
        if surname and first_name and date_of_birth:
            existing_patient = Patient.objects.filter(
                surname__iexact=surname,
                first_name__iexact=first_name,
                date_of_birth=date_of_birth,
            ).first()

            if existing_patient:
                # Пациент уже существует - возвращаем его
                return existing_patient, False

        # Создаем нового пациента
        patient = Patient.objects.create(**patient_data)
        return patient, True
