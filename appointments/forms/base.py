import json

from django import forms
from django.core.exceptions import ValidationError
from django.forms import ModelForm

from appointments.mixins import PatientFieldsMixin, AppointmentFormMixin
from appointments.models import Appointment
from appointments.validators import AppointmentValidator
from patients.services import PatientService
from timetable.mixins import StyleFormMixin, ServiceBasedFormMixin
from timetable.models import MedicalService


class AppointmentBaseForm(
    StyleFormMixin,
    PatientFieldsMixin,
    ServiceBasedFormMixin,
    ModelForm,
    AppointmentFormMixin,
):
    """Базовая форма для записи на прием"""

    service = forms.ModelChoiceField(
        queryset=MedicalService.objects.none(),
        widget=forms.Select(attrs={"class": "form-select"}),
        label="Услуга",
    )

    # ЗАМЕНЯЕМ appointment_type на appointment_chain_type
    appointment_chain_type = forms.ChoiceField(
        choices=AppointmentFormMixin.APPOINTMENT_CHOICES,
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
    procedural_appointments_data = forms.CharField(
        required=False,
        widget=forms.HiddenInput(attrs={"id": "id_procedural_appointments_data"}),
        label="Данные процедурных записей",
    )

    total_sum = forms.DecimalField(
        required=False,
        widget=forms.HiddenInput(attrs={"id": "id_total_sum"}),
        decimal_places=2,
        max_digits=10,
        label="Итоговая сумма",
    )

    # НОВОЕ: Поле для хранения JSON данных дополнительных записей
    additional_appointments_data = forms.CharField(
        required=False,
        widget=forms.HiddenInput(attrs={"id": "id_additional_appointments_data"}),
        label="Данные дополнительных записей",
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._set_initial_appointment_chain_type()

    def _set_initial_appointment_chain_type(self):
        """Устанавливает начальное значение для типа цепочки записей"""
        if self.instance and self.instance.pk:
            if self.instance.chain_type == Appointment.ChainType.MULTIPLE_DOCTORS:
                self.fields["appointment_chain_type"].initial = "multiple"
            elif self.instance.chain_type == Appointment.ChainType.SAME_DOCTOR:
                if self.instance.occupies_two_slots:
                    self.fields["appointment_chain_type"].initial = "two_slots"
                else:
                    self.fields["appointment_chain_type"].initial = "additional"
            else:
                self.fields["appointment_chain_type"].initial = "none"

    def clean(self):
        cleaned_data = super().clean()

        # Валидация данных пациента
        patient_data = self.get_patient_data()
        cleaned_patient_data = PatientService.clean_patient_data(patient_data)

        # Валидация дополнительной услуги для того же врача
        appointment_chain_type = cleaned_data.get("appointment_chain_type")
        additional_service = cleaned_data.get("additional_service")

        if appointment_chain_type == "additional" and not additional_service:
            raise ValidationError(
                'При выборе опции "Добавить вторую услугу к этому же врачу" необходимо указать вторую услугу'
            )

        # Валидация для записи к другому врачу
        if appointment_chain_type in ["another_doctor", "multiple"]:
            additional_data = cleaned_data.get("additional_appointments_data")
            if additional_data:
                try:
                    appointments_list = json.loads(additional_data)
                    if not appointments_list:
                        raise ValidationError(
                            f'При выборе опции "{self.get_appointment_type_display(appointment_chain_type)}" необходимо добавить хотя бы одну дополнительную запись'
                        )
                except json.JSONDecodeError:
                    raise ValidationError(
                        "Неверный формат данных дополнительных записей"
                    )

        # Валидация последовательных записей
        time_slot = getattr(self, "time_slot", None)
        if appointment_chain_type in ["additional", "two_slots"] and time_slot:
            current_time_slot = getattr(self, "current_time_slot", None)
            AppointmentValidator.validate_consecutive_slot(time_slot, current_time_slot)

        # ВАЛИДАЦИЯ ДЛЯ ВРАЧА ПИЩЕЛЕВА П.В.
        self._validate_pishchelev_restrictions(cleaned_data)

        return cleaned_data
