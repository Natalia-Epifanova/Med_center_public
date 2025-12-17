from django.test import TestCase
from appointments.forms import AppointmentForm
from timetable.models import Doctor, TimeSlot, MedicalService, Cabinet
from patients.models import Patient
from django.utils import timezone


class SimpleFormTest(TestCase):
    def setUp(self):
        # Создаем тестовые объекты
        self.cabinet = Cabinet.objects.create(number=1)

        self.doctor = Doctor.objects.create(
            first_name="Иван",
            last_name="Иванович",
            surname="Иванов",
            specialization="rheumatologist",
            provided_services=["joint_us"],
        )

        self.service = MedicalService.objects.create(
            code="TEST001", name="Тестовая услуга", price=1000.00, category="joint_us"
        )

        self.time_slot = TimeSlot.objects.create(
            doctor=self.doctor,
            cabinet=self.cabinet,
            date=timezone.now().date(),
            start_time="09:00:00",
            end_time="10:00:00",
            slot_type="working",
        )

        self.patient_data = {
            "surname": "Петров",
            "first_name": "Петр",
            "last_name": "Петрович",
            "phone_number": "+79991112233",
            "card_number": "12345",
            "date_of_birth": "1990-01-01",
        }

    def test_simple_form_validation(self):
        """Простой тест валидации формы"""

        form_data = {
            "doctor": self.doctor.id,
            "service": self.service.id,
            "appointment_date": "2025-12-17",
            "time_slot": self.time_slot.id,
            "comment": "",
            "insurance_type": "paid",
            "surname": "Петров",
            "first_name": "Петр",
            "last_name": "Петрович",
            "phone_number": "+79991112233",
            "card_number": "12345",
            "date_of_birth": "1990-01-01",
            # ДОБАВЛЯЕМ обязательное поле
            "appointment_chain_type": "none",  # или "additional", "two_slots", и т.д.
        }

        # Создаем форму с time_slot и doctor
        form = AppointmentForm(
            data=form_data, time_slot=self.time_slot, doctor=self.doctor
        )

        # Ручное заполнение queryset'ов для полей формы
        from timetable.utils import get_doctor_services

        # Устанавливаем queryset для service
        services_queryset = get_doctor_services(self.doctor)
        form.fields["service"].queryset = services_queryset

        # Устанавливаем queryset для time_slot (хотя это поле может быть скрыто)
        if "time_slot" in form.fields:
            form.fields["time_slot"].queryset = TimeSlot.objects.filter(
                doctor=self.doctor
            )

        print(f"Form data: {form_data}")
        print(f"Form is bound: {form.is_bound}")
        print(f"Form errors: {form.errors}")
        print(
            f"Form cleaned_data keys: {form.cleaned_data.keys() if hasattr(form, 'cleaned_data') else 'No cleaned_data'}"
        )

        self.assertTrue(form.is_valid())
