from django.test import TestCase
from appointments.forms.forms import AdditionalAppointmentForm
from appointments.tests.test_helpers import AppointmentTestMixin
from timetable.models import TimeSlot, Cabinet
from django.utils import timezone


class AppointmentChainFormsTestCase(TestCase, AppointmentTestMixin):
    def setUp(self):
        # Создаем кабинет
        self.cabinet = Cabinet.objects.create(number=1)

        # Создаем врачей
        self.doctor1 = self.create_test_doctor("rheumatologist", ["joint_us"])
        self.doctor2 = self.create_test_doctor("neurologist", ["first_consult"])

        # Создаем услуги
        self.service1 = self.create_test_service("joint_us")
        self.service2 = self.create_test_service("first_consult")

        # Создаем временные слоты
        self.time_slot1 = self.create_test_time_slot(self.doctor1, self.cabinet, 0)
        self.time_slot2 = self.create_test_time_slot(self.doctor2, self.cabinet, 1)

    def test_additional_appointment_form_valid(self):
        """Тест валидной формы дополнительной записи"""
        tomorrow = timezone.now().date() + timezone.timedelta(days=1)

        form_data = {
            "doctor": self.doctor2.id,
            "service": self.service2.id,
            "appointment_date": tomorrow.strftime("%Y-%m-%d"),
            "time_slot": self.time_slot2.id,
            "comment": "Тестовый комментарий",
        }

        form = AdditionalAppointmentForm(
            data=form_data, initial_doctor=self.doctor2, initial_date=tomorrow
        )

        # Ручное заполнение queryset'ов
        from timetable.utils import get_doctor_services

        # Устанавливаем queryset для service
        services_queryset = get_doctor_services(self.doctor2)
        form.fields["service"].queryset = services_queryset

        # Устанавливаем queryset для time_slot
        available_slots = TimeSlot.objects.filter(
            doctor=self.doctor2,
            date=tomorrow,
            slot_type="working",
            appointments__isnull=True,
        ).order_by("start_time")
        form.fields["time_slot"].queryset = available_slots

        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["doctor"], self.doctor2)
        self.assertEqual(form.cleaned_data["service"], self.service2)
        self.assertEqual(form.cleaned_data["time_slot"], self.time_slot2)
