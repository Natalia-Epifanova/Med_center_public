from django import forms
from django.forms import ModelForm

from .mixins import StyleFormMixin, PatientFieldsMixin, PatientHandlingMixin, ConsecutiveAppointmentMixin
from .models import TimeSlot, Appointment, MedicalService, Patient

#
# class AppointmentBaseForm(StyleFormMixin, PatientFieldsMixin, PatientHandlingMixin, ConsecutiveAppointmentMixin,
#                           ModelForm):
#     """Базовая форма для записи на прием"""
#
#     ADDITIONAL_SERVICE_CHOICES = [
#         ("none", "Только одна услуга"),
#         ("additional", "Добавить вторую услугу к этому же врачу"),
#         ("two_slots", "Занять два окошка для одной услуги"),
#     ]
#
#     service = forms.ModelChoiceField(
#         queryset=MedicalService.objects.none(),
#         label="Услуга*",
#         widget=forms.Select(attrs={"class": "form-select"}),
#     )
#
#     appointment_type = forms.ChoiceField(
#         choices=ADDITIONAL_SERVICE_CHOICES,
#         initial="none",
#         label="Тип записи",
#         widget=forms.RadioSelect(attrs={"class": "form-check-input"}),
#     )
#
#     additional_service = forms.ModelChoiceField(
#         queryset=MedicalService.objects.none(),
#         required=False,
#         label="Вторая услуга",
#         widget=forms.Select(attrs={"class": "form-select"}),
#     )
#
#     class Meta:
#         model = Appointment
#         fields = ["service", "insurance_type", "needs_reschedule", "comment"]
#         widgets = {
#             "insurance_type": forms.Select(attrs={"class": "form-select"}),
#             "needs_reschedule": forms.CheckboxInput(attrs={"class": "form-check-input"}),
#             "comment": forms.Textarea(
#                 attrs={"rows": 3, "placeholder": "Комментарий для администратора", "class": "form-control"}),
#         }
#         labels = {
#             "insurance_type": "Тип оплаты*",
#             "needs_reschedule": "Требуется перезапись на более ранний срок",
#             "comment": "Комментарий",
#         }
#
#     def __init__(self, *args, **kwargs):
#         self.doctor = kwargs.pop("doctor", None)
#         super().__init__(*args, **kwargs)
#
#         if self.doctor:
#             services = self.doctor.get_available_services()
#             self.fields["service"].queryset = services
#             self.fields["additional_service"].queryset = services
#
#     def clean(self):
#         cleaned_data = super().clean()
#         self.clean_patient_data()  # Используем миксин
#
#         appointment_type = cleaned_data.get("appointment_type")
#         additional_service = cleaned_data.get("additional_service")
#         time_slot = getattr(self, 'time_slot', None)
#
#         # Проверка для второй услуги
#         if appointment_type == "additional" and not additional_service:
#             raise forms.ValidationError({
#                 "additional_service": 'При выборе опции "Добавить вторую услугу" необходимо указать вторую услугу'
#             })
#
#         # Проверка последовательных записей
#         if appointment_type in ["additional", "two_slots"] and time_slot:
#             current_time_slot = getattr(self, 'current_time_slot', None)
#             self.validate_consecutive_slot(time_slot, current_time_slot)
#
#         return cleaned_data
#
#     def get_patient_data(self):
#         """Извлекает данные пациента из cleaned_data"""
#         return {
#             "surname": self.cleaned_data.get("surname"),
#             "first_name": self.cleaned_data.get("first_name"),
#             "last_name": self.cleaned_data.get("last_name"),
#             "phone_number": self.cleaned_data.get("phone_number"),
#             "card_number": self.cleaned_data.get("card_number"),
#             "date_of_birth": self.cleaned_data.get("date_of_birth"),
#         }

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


class AppointmentUpdateForm(StyleFormMixin, ModelForm):
    """Форма для полного редактирования записи на прием"""

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

    # Новое поле для выбора даты
    appointment_date = forms.DateField(
        label="Дата приема*",
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )

    # Основная услуга (обязательная)
    service = forms.ModelChoiceField(
        queryset=MedicalService.objects.none(),
        label="Услуга*",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    # Новое поле для выбора временного слота
    time_slot = forms.CharField(
        label="Временной слот*",
        widget=forms.HiddenInput(),  # Скрытое поле, управляется через JavaScript
        required=True,
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
            "appointment_date",
            "time_slot",
            "service",
            "insurance_type",
            "needs_reschedule",
            "comment",
        ]
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
        self.current_appointment = kwargs.pop("current_appointment", None)
        super().__init__(*args, **kwargs)

        if self.current_appointment:
            doctor = self.current_appointment.doctor

            # Фильтруем услуги по специализации врача
            services = doctor.get_available_services()
            self.fields["service"].queryset = services
            self.fields["additional_service"].queryset = services

            # Устанавливаем начальную дату (текущая дата записи)
            if self.instance.pk:
                self.fields["appointment_date"].initial = self.instance.time_slot.date
                # Устанавливаем начальное значение для time_slot
                self.fields["time_slot"].initial = self.instance.time_slot.id

                # Определяем тип записи
                if self.instance.occupies_two_slots:
                    self.fields["appointment_type"].initial = "two_slots"
                elif (
                    self.instance.is_consecutive and self.instance.previous_appointment
                ):
                    self.fields["appointment_type"].initial = "additional"
                else:
                    self.fields["appointment_type"].initial = "none"

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

    def clean(self):
        cleaned_data = super().clean()
        appointment_type = cleaned_data.get("appointment_type")
        additional_service = cleaned_data.get("additional_service")
        time_slot = cleaned_data.get("time_slot")
        appointment_date = cleaned_data.get("appointment_date")

        # Проверка обязательных полей пациента
        surname = cleaned_data.get("surname")
        first_name = cleaned_data.get("first_name")
        if not surname or not first_name:
            raise forms.ValidationError(
                "Фамилия и имя пациента обязательны для заполнения"
            )

        # Проверка даты
        if not appointment_date:
            raise forms.ValidationError("Дата приема обязательна для заполнения")

        # Проверка для второй услуги
        if appointment_type == "additional" and not additional_service:
            raise forms.ValidationError(
                'При выборе опции "Добавить вторую услугу" необходимо указать вторую услугу'
            )

        # Проверка доступности следующего слота для последовательных записей
        if appointment_type in ["additional", "two_slots"] and time_slot:
            next_slot = time_slot.get_next_consecutive_slot()
            current_time_slot = getattr(self.current_appointment, "time_slot", None)

            if not next_slot:
                raise forms.ValidationError(
                    "Следующий временной слот недоступен для последовательной записи"
                )

            if not next_slot.is_available() and next_slot != current_time_slot:
                raise forms.ValidationError(
                    "Следующий временной слот уже занят другим пациентом"
                )

        return cleaned_data

    def save(self, commit=True):
        # Сохраняем основную запись
        appointment = super().save(commit=False)

        # Устанавливаем выбранный временной слот
        time_slot = self.cleaned_data.get("time_slot")
        if time_slot:
            appointment.time_slot = time_slot

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
            # Сохраняем основную запись
            appointment.save()

            # Обрабатываем последовательные записи
            self._handle_consecutive_appointments(appointment)

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

    def _handle_consecutive_appointments(self, main_appointment):
        """Обрабатывает последовательные записи"""
        appointment_type = self.cleaned_data.get("appointment_type")

        # Удаляем существующие последовательные записи
        consecutive_appointments = Appointment.objects.filter(
            previous_appointment=main_appointment
        )
        consecutive_appointments.delete()

        if appointment_type in ["additional", "two_slots"]:
            next_slot = main_appointment.time_slot.get_next_consecutive_slot()

            if next_slot and next_slot.is_available():
                if appointment_type == "additional":
                    # Вторая услуга на следующий слот
                    consecutive_appointment = Appointment(
                        time_slot=next_slot,
                        patient=main_appointment.patient,
                        service=self.cleaned_data["additional_service"],
                        insurance_type=main_appointment.insurance_type,
                        status=main_appointment.status,
                        is_consecutive=True,
                        previous_appointment=main_appointment,
                        comment=f"Последовательная запись к {main_appointment.service.name}",
                    )
                else:
                    # Та же услуга на два слота
                    consecutive_appointment = Appointment(
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
                consecutive_appointment.save()
