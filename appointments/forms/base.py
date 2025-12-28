import json

from django import forms
from django.core.exceptions import ValidationError

from appointments.mixins import AppointmentFormMixin, PatientFieldsMixin
from appointments.models import Appointment
from appointments.utils_for_caches import get_cached_doctor_services
from appointments.validators import AppointmentValidator
from timetable.mixins import ServiceBasedFormMixin, StyleFormMixin
from timetable.models import MedicalService


class AppointmentChainBaseForm(
    StyleFormMixin,
    PatientFieldsMixin,
    ServiceBasedFormMixin,
    AppointmentFormMixin,
    forms.ModelForm,
):
    """Базовая форма для записей с поддержкой цепочек"""

    class Meta:
        model = Appointment
        fields = []  # Будем определять в дочерних формах

    # Основные поля (будут переопределены в дочерних формах)
    service = forms.ModelChoiceField(
        queryset=MedicalService.objects.none(),
        widget=forms.Select(attrs={"class": "form-select"}),
        label="Услуга",
    )

    insurance_type = forms.ChoiceField(
        choices=Appointment.InsuranceType.choices,
        widget=forms.Select(attrs={"class": "form-select"}),
        label="Тип оплаты",
    )

    # Поля для цепочек записей
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

    # Поля для записей к другим врачам
    additional_appointments_data = forms.CharField(
        required=False,
        widget=forms.HiddenInput(attrs={"id": "id_additional_appointments_data"}),
        label="Данные дополнительных записей",
    )

    # Поля для процедурных записей в цепочке
    procedural_appointments_data = forms.CharField(
        required=False,
        widget=forms.HiddenInput(attrs={"id": "id_procedural_appointments_data"}),
        label="Данные процедурных записей",
    )

    needs_procedural = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
        label="Занять окошко в процедурном кабинете",
        help_text="Автоматически займет такое же время в процедурном кабинете",
    )

    # Общие поля
    needs_reschedule = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
        label="Требуется перезапись на более ранний срок",
    )

    comment = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3, "class": "form-control"}),
        label="Комментарий",
    )

    total_sum = forms.DecimalField(
        required=False,
        widget=forms.HiddenInput(attrs={"id": "id_total_sum"}),
        decimal_places=2,
        max_digits=10,
        label="Итоговая сумма",
    )

    def __init__(self, *args, **kwargs):
        self.time_slot = kwargs.pop("time_slot", None)
        self.doctor = kwargs.pop("doctor", None)
        super().__init__(*args, **kwargs)

        # Инициализация полей
        self._set_initial_appointment_chain_type()
        self._initialize_service_queryset()

    def _set_initial_appointment_chain_type(self):
        """Устанавливает начальное значение для типа цепочки записей"""
        if hasattr(self, "instance") and self.instance and self.instance.pk:
            if self.instance.chain_type == Appointment.ChainType.MULTIPLE_DOCTORS:
                self.fields["appointment_chain_type"].initial = "multiple"
            elif self.instance.chain_type == Appointment.ChainType.SAME_DOCTOR:
                if self.instance.occupies_two_slots:
                    self.fields["appointment_chain_type"].initial = "two_slots"
            else:
                self.fields["appointment_chain_type"].initial = "none"

    def _initialize_service_queryset(self):
        """Инициализирует queryset услуг"""

        doctor_to_use = self.doctor or (
            self.time_slot.doctor if self.time_slot else None
        )

        if doctor_to_use:
            services = doctor_to_use.get_available_services()
            self.fields["service"].queryset = services

    def clean(self):
        """Общая валидация для всех форм с цепочками"""
        cleaned_data = super().clean()

        # Валидация дополнительной услуги для того же врача
        appointment_chain_type = cleaned_data.get("appointment_chain_type")

        # Валидация для записей к другим врачам
        if appointment_chain_type in ["another_doctor", "multiple"]:
            additional_data = cleaned_data.get("additional_appointments_data")
            if additional_data:
                try:
                    appointments_list = json.loads(additional_data)
                    if not appointments_list:
                        raise ValidationError(
                            f'При выборе опции "{self.get_appointment_type_display(appointment_chain_type)}" '
                            f"необходимо добавить хотя бы одну дополнительную запись"
                        )

                    # Валидация всех дополнительных записей
                    self._validate_additional_appointments(appointments_list)

                except json.JSONDecodeError:
                    raise ValidationError(
                        "Неверный формат данных дополнительных записей"
                    )

        # Валидация последовательных записей
        if appointment_chain_type == "two_slots" and self.time_slot:
            AppointmentValidator.validate_consecutive_slot(self.time_slot)

        return cleaned_data

    def _validate_additional_appointments(self, appointments_list):
        """Валидация дополнительных записей"""
        for i, appointment_data in enumerate(appointments_list, start=1):
            doctor_id = appointment_data.get("doctor_id")
            service_id = appointment_data.get("service_id")
            time_slot_id = appointment_data.get("time_slot_id")

            if not all([doctor_id, service_id, time_slot_id]):
                continue

            try:
                from timetable.models import Doctor, MedicalService, TimeSlot

                doctor = Doctor.objects.get(id=doctor_id)
                service = MedicalService.objects.get(id=service_id)
                time_slot = TimeSlot.objects.get(id=time_slot_id)

                # Проверка доступности слота
                if not time_slot.is_available():
                    raise ValidationError(
                        f"Ошибка в дополнительной записи #{i}: "
                        f"Слот {time_slot.start_time} у врача {doctor.surname} уже занят"
                    )

                # ИСПРАВЛЕНИЕ: Используем существующую функцию вместо can_perform_service
                # Проверяем, что услуга доступна врачу через get_doctor_services
                available_services = get_cached_doctor_services(doctor)
                if not available_services.filter(id=service.id).exists():
                    raise ValidationError(
                        f"Ошибка в дополнительной записи #{i}: "
                        f"Услуга '{service.name}' недоступна врачу {doctor.surname}"
                    )

            except (
                Doctor.DoesNotExist,
                MedicalService.DoesNotExist,
                TimeSlot.DoesNotExist,
            ) as e:
                raise ValidationError(f"Ошибка в дополнительной записи #{i}: {str(e)}")

    def save(self, commit=True):
        """Базовый метод сохранения"""
        # Сохраняем только базовые поля ModelForm
        return super(forms.ModelForm, self).save(commit)
