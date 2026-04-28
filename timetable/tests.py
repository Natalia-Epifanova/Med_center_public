from datetime import date, time
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from appointments.models import Appointment
from patients.models import Patient
from timetable.models import Cabinet, Doctor, MedicalService, MedicalServiceCategory, TimeSlot


class DoctorReportSummaryTests(TestCase):
    def setUp(self):
        self.User = get_user_model()
        self.admin_group, _ = Group.objects.get_or_create(name="Admin")
        self.user = self.User.objects.create_user(
            username="report_admin",
            password="testpass123",
        )
        self.user.groups.add(self.admin_group)
        self.client.force_login(self.user)

        self.cabinet = Cabinet.objects.create(number=101, name_of_cabinet="Тестовый")
        self.patient = Patient.objects.create(
            surname="Иванов",
            first_name="Иван",
            last_name="Иванович",
            phone_number="+79990001122",
            card_number="55555",
            date_of_birth=date(1980, 1, 1),
        )
        self.doctor = Doctor.objects.create(
            first_name="Анна",
            last_name="Ивановна",
            surname="Тестова",
            specialization=Doctor.DoctorSpecialization.RHEUMATOLOGIST,
            provided_services=[
                MedicalServiceCategory.ANALYZES,
                MedicalServiceCategory.XRAY,
                MedicalServiceCategory.PHYSIO_PROCEDURES,
                MedicalServiceCategory.MEDICAL_BLOCKADES,
            ],
        )
        self.report_date = date(2026, 4, 20)

    def create_service(self, *, code, name, price, category):
        return MedicalService.objects.create(
            code=code,
            name=name,
            price=price,
            category=category,
            is_active=True,
        )

    def create_completed_appointment(self, *, service, start_time_value):
        slot = TimeSlot.objects.create(
            doctor=self.doctor,
            cabinet=self.cabinet,
            date=self.report_date,
            start_time=start_time_value,
            end_time=time(start_time_value.hour, start_time_value.minute + 10),
            slot_type="working",
        )
        return Appointment.objects.create(
            time_slot=slot,
            patient=self.patient,
            service=service,
            status=Appointment.AppointmentStatus.COMPLETED,
            insurance_type=Appointment.InsuranceType.PAID,
        )

    def test_doctor_report_period_summary_contains_new_service_totals(self):
        analysis_service = self.create_service(
            code="AN-001",
            name="Общий анализ",
            price=Decimal("100.00"),
            category=MedicalServiceCategory.ANALYZES,
        )
        xray_service = self.create_service(
            code="XR-001",
            name="Рентген кисти",
            price=Decimal("200.00"),
            category=MedicalServiceCategory.XRAY,
        )
        magnetolaser_service = self.create_service(
            code="A22.01.005",
            name="Магнитолазерная терапия (одна область)",
            price=Decimal("300.00"),
            category=MedicalServiceCategory.PHYSIO_PROCEDURES,
        )
        intramuscular_service = self.create_service(
            code="A11.02.002",
            name="Внутримышечное введение лекарственных препаратов (без учета стоимости препарата)",
            price=Decimal("400.00"),
            category=MedicalServiceCategory.MEDICAL_BLOCKADES,
        )
        intramuscular_diclofenac_service = self.create_service(
            code="A11.02.002",
            name="Внутримышечное введение лекарственных препаратов (с учетом стоимости препарата) - диклофенак",
            price=Decimal("500.00"),
            category=MedicalServiceCategory.MEDICAL_BLOCKADES,
        )
        subcutaneous_service = self.create_service(
            code="A11.01.002",
            name="Подкожное и внутрикожное введение лекарственных препаратов",
            price=Decimal("600.00"),
            category=MedicalServiceCategory.MEDICAL_BLOCKADES,
        )
        continuous_intravenous_service = self.create_service(
            code="A11.12.003.001",
            name="Непрерывное внутривенное введение лекарственных препаратов (без учета стоимости препарата). За одну инъекцию",
            price=Decimal("700.00"),
            category=MedicalServiceCategory.MEDICAL_BLOCKADES,
        )
        intravenous_service = self.create_service(
            code="A11.12.003",
            name="Внутривенное введение лекарственных препаратов",
            price=Decimal("800.00"),
            category=MedicalServiceCategory.MEDICAL_BLOCKADES,
        )

        self.create_completed_appointment(
            service=analysis_service, start_time_value=time(9, 0)
        )
        self.create_completed_appointment(
            service=xray_service, start_time_value=time(9, 20)
        )
        self.create_completed_appointment(
            service=magnetolaser_service, start_time_value=time(9, 40)
        )
        self.create_completed_appointment(
            service=intramuscular_service, start_time_value=time(10, 0)
        )
        self.create_completed_appointment(
            service=intramuscular_diclofenac_service, start_time_value=time(10, 20)
        )
        self.create_completed_appointment(
            service=subcutaneous_service, start_time_value=time(10, 40)
        )
        self.create_completed_appointment(
            service=continuous_intravenous_service, start_time_value=time(11, 0)
        )
        self.create_completed_appointment(
            service=intravenous_service, start_time_value=time(11, 20)
        )

        response = self.client.get(
            reverse("timetable:doctor_report"),
            {
                "start_date": self.report_date.isoformat(),
                "end_date": self.report_date.isoformat(),
            },
        )

        self.assertEqual(response.status_code, 200)
        cards = {
            card["key"]: card["amount"] for card in response.context["period_summary_cards"]
        }

        self.assertEqual(cards["analyses"], Decimal("100.00"))
        self.assertEqual(cards["xray"], Decimal("200.00"))
        self.assertEqual(cards["magnetolaser"], Decimal("300.00"))
        self.assertEqual(cards["intramuscular"], Decimal("400.00"))
        self.assertEqual(cards["subcutaneous"], Decimal("600.00"))
        self.assertEqual(cards["continuous_intravenous"], Decimal("700.00"))
        self.assertEqual(cards["intravenous"], Decimal("800.00"))

        self.assertContains(response, "Магнитолазерная терапия")
        self.assertContains(response, "Внутримышечные инъекции")
        self.assertContains(response, "Подкожные и внутрикожные")
        self.assertContains(response, "Непрерывное внутривенное")
        self.assertContains(response, "Внутривенные инъекции")
