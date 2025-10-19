from django import forms
from .models import Patient, Appointment


class StyleFormMixin:
    """
    Миксин для стилизации форм. Добавляет CSS-класс 'form-control' ко всем полям формы.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if "class" not in field.widget.attrs:
                field.widget.attrs["class"] = "form-control"


class PatientFieldsMixin:
    """Миксин добавляет поля пациента к форме"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Добавляем поля пациента динамически
        self.fields.update(
            {
                "surname": forms.CharField(
                    max_length=50,
                    label="Фамилия*",
                    widget=forms.TextInput(
                        attrs={
                            "placeholder": "Введите фамилию",
                            "class": "form-control",
                        }
                    ),
                ),
                "first_name": forms.CharField(
                    max_length=20,
                    label="Имя*",
                    widget=forms.TextInput(
                        attrs={"placeholder": "Введите имя", "class": "form-control"}
                    ),
                ),
                "last_name": forms.CharField(
                    max_length=30,
                    required=False,
                    label="Отчество",
                    widget=forms.TextInput(
                        attrs={
                            "placeholder": "Введите отчество",
                            "class": "form-control",
                        }
                    ),
                ),
                "phone_number": forms.CharField(
                    max_length=12,
                    required=False,
                    label="Телефон",
                    widget=forms.TextInput(
                        attrs={"placeholder": "+7XXXXXXXXXX", "class": "form-control"}
                    ),
                ),
                "card_number": forms.IntegerField(
                    required=False,
                    label="Номер карты",
                    widget=forms.NumberInput(
                        attrs={
                            "placeholder": "Номер карты пациента",
                            "class": "form-control",
                        }
                    ),
                ),
                "date_of_birth": forms.DateField(
                    required=False,
                    label="Дата рождения",
                    widget=forms.DateInput(
                        attrs={"type": "date", "class": "form-control"}
                    ),
                ),
            }
        )


class PatientHandlingMixin:
    """Миксин для обработки пациентов"""

    def clean_patient_data(self):
        """Валидация данных пациента"""
        cleaned_data = self.cleaned_data
        surname = cleaned_data.get("surname")
        first_name = cleaned_data.get("first_name")

        if not surname or not first_name:
            raise forms.ValidationError(
                "Фамилия и имя пациента обязательны для заполнения"
            )
        return cleaned_data

    def get_or_create_patient(self, patient_data):
        """Универсальный метод для поиска/создания пациента"""
        surname = patient_data.get("surname")
        first_name = patient_data.get("first_name")
        date_of_birth = patient_data.get("date_of_birth")

        if surname and first_name and date_of_birth:
            existing_patient = Patient.objects.filter(
                surname__iexact=surname,
                first_name__iexact=first_name,
                date_of_birth=date_of_birth,
            ).first()
            if existing_patient:
                return existing_patient, False

        patient = Patient.objects.create(**patient_data)
        return patient, True


class ConsecutiveAppointmentMixin:
    """Миксин для обработки последовательных записей"""

    def create_consecutive_appointment(
        self, main_appointment, appointment_type, next_slot, additional_service=None
    ):
        """Создание последовательной записи"""
        if appointment_type == "additional":
            return Appointment(
                time_slot=next_slot,
                patient=main_appointment.patient,
                service=additional_service,
                insurance_type=main_appointment.insurance_type,
                status=main_appointment.status,
                is_consecutive=True,
                previous_appointment=main_appointment,
                comment=f"Последовательная запись к {main_appointment.service.name}",
            )
        elif appointment_type == "two_slots":
            return Appointment(
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
        return None

    def validate_consecutive_slot(self, time_slot, current_time_slot=None):
        """Валидация доступности следующего слота"""
        next_slot = time_slot.get_next_consecutive_slot()

        if not next_slot:
            raise forms.ValidationError(
                "Следующий временной слот недоступен для последовательной записи"
            )

        if not next_slot.is_available() and next_slot != current_time_slot:
            raise forms.ValidationError(
                "Следующий временной слот уже занят другим пациентом"
            )
        return next_slot
