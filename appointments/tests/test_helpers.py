# В отдельном файле test_helpers.py или в начале test_forms.py
from django.test import TestCase
from timetable.models import Doctor, MedicalService, Cabinet, TimeSlot
from django.utils import timezone


class AppointmentTestMixin:
    """Миксин для создания тестовых данных записей"""

    @classmethod
    def create_test_doctor(
        cls, specialization="rheumatologist", provided_services=None
    ):
        """Создает тестового врача"""
        if provided_services is None:
            provided_services = ["joint_us"]

        return Doctor.objects.create(
            first_name="Тест",
            last_name="Тестович",
            surname=f"Доктор-{specialization}",
            specialization=specialization,
            provided_services=provided_services,
        )

    @classmethod
    def create_test_service(cls, category="joint_us", name=None, price=1000.00):
        """Создает тестовую услугу"""
        if name is None:
            name = f"Тестовая услуга {category}"

        return MedicalService.objects.create(
            code=f"TEST-{category.upper()}", name=name, price=price, category=category
        )

    @classmethod
    def create_test_time_slot(cls, doctor, cabinet, days_from_today=1):
        """Создает тестовый временной слот"""
        date = timezone.now().date() + timezone.timedelta(days=days_from_today)

        return TimeSlot.objects.create(
            doctor=doctor,
            cabinet=cabinet,
            date=date,
            start_time="09:00:00",
            end_time="10:00:00",
            slot_type="working",
        )
