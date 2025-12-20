import json

from django import forms
from django.core.exceptions import ValidationError

from appointments.forms.base import AppointmentChainBaseForm
from patients.services import PatientService
from timetable.models import BloodTest, MedicalService, MedicalServiceCategory


class ProceduralAppointmentBaseForm(AppointmentChainBaseForm):
    """Базовая форма для процедурных записей с поддержкой цепочек"""

    # ПЕРЕОПРЕДЕЛЯЕМ CHOICES для процедурной формы
    APPOINTMENT_CHOICES = [
        ("none", "Только одна услуга"),
        ("another_doctor", "Добавить запись к другому врачу"),
        ("multiple", "Несколько записей к разным врачам"),
    ]

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

    selected_blood_tests_input = forms.CharField(
        required=False,
        widget=forms.HiddenInput(attrs={"id": "id_selected_blood_tests"}),
        label="Выбранные анализы крови",
    )

    def __init__(self, *args, **kwargs):
        self.selected_date = kwargs.pop("selected_date", None)

        # Сохраняем doctor и time_slot из kwargs перед передачей в родительский класс
        doctor = kwargs.pop("doctor", None)
        time_slot = kwargs.pop("time_slot", None)

        super().__init__(*args, **kwargs, doctor=doctor, time_slot=time_slot)

        # Устанавливаем services для медсестры
        self._set_nurse_services()

        # Скрываем ненужные поля для процедурной формы
        self._hide_unnecessary_fields()

        # ПЕРЕОПРЕДЕЛЯЕМ CHOICES в поле appointment_chain_type
        self.fields["appointment_chain_type"].choices = self.APPOINTMENT_CHOICES
        self.fields["appointment_chain_type"].initial = "none"

    def _hide_unnecessary_fields(self):
        """Скрывает поля, которые не нужны для процедурной формы"""
        fields_to_remove = [
            "needs_procedural",
            "additional_service",
            "needs_procedural_additional",
        ]

        for field_name in fields_to_remove:
            if field_name in self.fields:
                del self.fields[field_name]

    def _set_nurse_services(self):
        """Устанавливает queryset услуг, доступных для медсестры"""
        nurse_categories = [
            MedicalServiceCategory.MEDICAL_BLOCKADES,
            MedicalServiceCategory.ANALYZES,
        ]

        nurse_services = MedicalService.objects.filter(
            category__in=nurse_categories, is_active=True
        )

        # Обновляем queryset для поля service
        self.fields["service"].queryset = nurse_services

    def clean(self):
        """Дополнительная валидация для процедурной формы"""
        cleaned_data = super().clean()

        # Валидация времени
        start_time = cleaned_data.get("procedural_start_time")
        end_time = cleaned_data.get("procedural_end_time")

        if start_time and end_time and start_time >= end_time:
            raise forms.ValidationError(
                "Время окончания должно быть позже времени начала"
            )

        # Валидация для услуги "Забор крови"
        service = cleaned_data.get("service")
        selected_blood_tests_input = cleaned_data.get("selected_blood_tests_input", "")

        if service and "забор крови" in service.name.lower():
            if not selected_blood_tests_input.strip():
                raise forms.ValidationError(
                    "Для услуги 'Забор крови' необходимо выбрать хотя бы один анализ"
                )
            else:
                # Проверяем, что хотя бы один анализ выбран
                test_ids = [
                    int(id.strip())
                    for id in selected_blood_tests_input.split(",")
                    if id.strip() and id.strip().isdigit()
                ]
                if not test_ids:
                    raise forms.ValidationError(
                        "Для услуги 'Забор крови' необходимо выбрать хотя бы один анализ"
                    )

        # ДОБАВЛЯЕМ: валидацию дополнительных записей к другим врачам
        appointment_chain_type = cleaned_data.get("appointment_chain_type")
        if appointment_chain_type in ["another_doctor", "multiple"]:
            additional_data = cleaned_data.get("additional_appointments_data")
            if additional_data:
                try:
                    appointments_list = json.loads(additional_data)
                    if not appointments_list:
                        raise ValidationError(
                            f'При выборе опции "{self.get_appointment_type_display(appointment_chain_type)}" необходимо добавить хотя бы одну дополнительную запись'
                        )

                    # Используем существующую логику валидации
                    self._validate_additional_appointments(appointments_list)

                except json.JSONDecodeError:
                    raise ValidationError(
                        "Неверный формат данных дополнительных записей"
                    )

        # ВАЖНОЕ ДОБАВЛЕНИЕ: проверка доступности времени в процедурном кабинете
        if start_time and end_time and self.selected_date:
            if not self._check_procedural_time_availability(start_time, end_time):
                raise forms.ValidationError(
                    "Выбранное время в процедурном кабинете уже занято. "
                    "Пожалуйста, выберите другое время."
                )

        return cleaned_data

    def _check_procedural_time_availability(self, start_time, end_time):
        """Проверяет доступность времени в процедурном кабинете (метод для clean)"""
        try:
            from timetable.models import Cabinet, TimeSlot

            procedural_cabinet = Cabinet.objects.get(number=6)

            conflicting_slots = TimeSlot.get_conflicting_slots(
                date=self.selected_date,
                start_time=start_time,
                end_time=end_time,
                cabinet=procedural_cabinet,
            ).filter(appointments__isnull=False)

            return not conflicting_slots.exists()

        except Exception:
            return False

    def get_patient_data(self):
        """Извлекает данные пациента из формы"""
        # Используем cleaned_data если форма прошла валидацию
        if hasattr(self, "cleaned_data") and self.cleaned_data:
            data_source = self.cleaned_data
        else:
            # Иначе используем data
            data_source = self.data if hasattr(self, "data") else {}

        return {
            "surname": data_source.get("surname", "").strip(),
            "first_name": data_source.get("first_name", "").strip(),
            "last_name": data_source.get("last_name", "").strip(),
            "phone_number": data_source.get("phone_number", "").strip(),
            "card_number": data_source.get("card_number"),
            "date_of_birth": data_source.get("date_of_birth"),
        }
