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

    # РАСШИРЯЕМ существующие choices (переносим из AppointmentBaseForm)
    APPOINTMENT_CHOICES = [
        ("none", "Только одна услуга"),
        ("additional", "Добавить вторую услугу к этому же врачу"),
        ("two_slots", "Занять два окошка для одной услуги"),
        ("another_doctor", "Добавить запись к другому врачу"),
        ("multiple", "Несколько записей к разным врачам"),
    ]

    def get_appointment_type_display(self, value):
        """Получить отображаемое название типа записи"""
        choices_dict = dict(self.APPOINTMENT_CHOICES)
        return choices_dict.get(value, value)

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
        from timetable.utils import validate_pishchelev_restrictions

        validate_pishchelev_restrictions(doctor, service, time_slot)
