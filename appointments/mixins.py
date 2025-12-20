# patients/mixins.py (добавляем метод в класс PatientFieldsMixin)
from django import forms


class PatientFieldsMixin:
    """Миксин добавляет поля пациента к форме"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._add_patient_fields()

    def _add_patient_fields(self):
        """Добавление полей пациента с русскими метками"""
        self.fields.update(
            {
                "surname": forms.CharField(
                    max_length=50,
                    label="Фамилия*",
                    widget=forms.TextInput(attrs={"placeholder": "Введите фамилию"}),
                ),
                "first_name": forms.CharField(
                    max_length=20,
                    label="Имя*",
                    widget=forms.TextInput(attrs={"placeholder": "Введите имя"}),
                ),
                "last_name": forms.CharField(
                    max_length=30,
                    required=False,
                    label="Отчество",
                    widget=forms.TextInput(attrs={"placeholder": "Введите отчество"}),
                ),
                "phone_number": forms.CharField(
                    max_length=12,
                    required=False,
                    label="Телефон",
                    widget=forms.TextInput(
                        attrs={
                            "placeholder": "+79501234567",
                            "pattern": "^\\+7\\d{10}$",
                            "title": "Формат: +7XXXXXXXXXX (12 символов)",
                        }
                    ),
                ),
                "card_number": forms.IntegerField(
                    required=False,
                    label="Номер карты",
                    widget=forms.NumberInput(
                        attrs={"placeholder": "Номер карты пациента"}
                    ),
                ),
                "date_of_birth": forms.DateField(
                    required=False,
                    label="Дата рождения",
                    widget=forms.DateInput(attrs={"type": "date"}),
                ),
            }
        )

    # ДОБАВЛЯЕМ НОВЫЙ МЕТОД
    def get_patient_data(self):
        """Извлекает данные пациента из формы"""
        if hasattr(self, "cleaned_data"):
            data_source = self.cleaned_data
        else:
            data_source = self.data if hasattr(self, "data") else {}

        return {
            "surname": data_source.get("surname", "").strip(),
            "first_name": data_source.get("first_name", "").strip(),
            "last_name": data_source.get("last_name", "").strip(),
            "phone_number": data_source.get("phone_number", "").strip(),
            "card_number": data_source.get("card_number"),
            "date_of_birth": data_source.get("date_of_birth"),
        }


class AppointmentFormMixin:
    """Миксин с общими методами для форм записей"""

    APPOINTMENT_CHOICES = [
        ("none", "Только одна услуга"),
        ("additional", "Добавить вторую услугу к этому же врачу"),
        ("two_slots", "Занять два окошка для одной услуги"),
        ("another_doctor", "Добавить запись к этому или другому врачу"),
        ("multiple", "Несколько записей к этому врачу или разным врачам"),
    ]

    def get_appointment_type_display(self, value):
        """Получить отображаемое название типа записи"""
        choices_dict = dict(self.APPOINTMENT_CHOICES)
        return choices_dict.get(value, value)

    def _validate_pishchelev_restrictions(self, cleaned_data):
        """Проверка ограничений для врача Пищелева П.В. для ВСЕХ записей"""
        doctor = None

        # Получаем врача в зависимости от контекста
        if hasattr(self, "time_slot") and self.time_slot:
            doctor = self.time_slot.doctor
        elif hasattr(self, "current_appointment") and self.current_appointment:
            doctor = self.current_appointment.doctor
        elif hasattr(self, "doctor") and self.doctor:
            doctor = self.doctor

        # Если это не Пищелев, выходим
        if not doctor or "пищелев" not in doctor.surname.lower():
            return

        # Проверяем основную услугу
        service = cleaned_data.get("service")
        time_slot = getattr(self, "time_slot", None)

        from django.core.exceptions import ValidationError

        from timetable.utils import validate_pishchelev_restrictions

        try:
            validate_pishchelev_restrictions(doctor, service, time_slot)
        except ValidationError as e:
            # Перевыбрасываем исключение с более понятным сообщением
            raise ValidationError(
                f"Врач Пищелев П.В.: {str(e)}\n"
                f"Услуга: {service.name if service else 'не указана'}\n"
                f"Время: {time_slot.start_time if time_slot else 'не указано'}"
            )

        # Проверяем дополнительные услуги в цепочке
        self._validate_pishchelev_for_chain(doctor, cleaned_data)

    def _validate_pishchelev_for_chain(self, doctor, cleaned_data):
        """Проверка ограничений Пищелева для записей в цепочке"""
        appointment_chain_type = cleaned_data.get("appointment_chain_type")

        # Проверяем дополнительную услугу для того же врача
        if appointment_chain_type == "additional":
            additional_service = cleaned_data.get("additional_service")
            time_slot = getattr(self, "time_slot", None)

            if additional_service and time_slot:
                next_slot = time_slot.get_next_consecutive_slot()
                if next_slot:
                    from django.core.exceptions import ValidationError

                    from timetable.utils import validate_pishchelev_restrictions

                    try:
                        validate_pishchelev_restrictions(
                            doctor, additional_service, next_slot
                        )
                    except ValidationError as e:
                        raise ValidationError(
                            f"Ошибка для второй услуги ({additional_service.name}): {str(e)}"
                        )

        # Проверяем дополнительные записи к другим врачам/тому же врачу
        if appointment_chain_type in ["another_doctor", "multiple"]:
            additional_data = cleaned_data.get("additional_appointments_data")
            if additional_data:
                import json

                try:
                    appointments_list = json.loads(additional_data)
                    for i, appointment_data in enumerate(appointments_list):
                        # Если это запись к тому же врачу
                        if appointment_data.get("doctor_id") == doctor.id:
                            service_id = appointment_data.get("service_id")
                            time_slot_id = appointment_data.get("time_slot_id")

                            if service_id and time_slot_id:
                                from timetable.models import MedicalService, TimeSlot

                                try:
                                    service = MedicalService.objects.get(id=service_id)
                                    time_slot = TimeSlot.objects.get(id=time_slot_id)

                                    from timetable.utils import (
                                        validate_pishchelev_restrictions,
                                    )

                                    validate_pishchelev_restrictions(
                                        doctor, service, time_slot
                                    )
                                except (
                                    MedicalService.DoesNotExist,
                                    TimeSlot.DoesNotExist,
                                ):
                                    continue
                except (json.JSONDecodeError, KeyError):
                    pass
