import os
import tempfile
from datetime import date, time
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase
from django.urls import reverse

from appointments.models import Appointment
from patients.models import Patient
from timetable.models import Cabinet, Doctor, MedicalService, MedicalServiceCategory, TimeSlot
from treatment.models import DoctorTreatment, MKB10Diagnosis


class TreatmentBaseTestCase(TestCase):
    def setUp(self):
        self.User = get_user_model()
        self.admin_group, _ = Group.objects.get_or_create(name="Admin")
        self.med_admin_group, _ = Group.objects.get_or_create(
            name="Medical Center Administrator"
        )
        self.doctors_group, _ = Group.objects.get_or_create(name="Doctors")

        self.admin_user = self.User.objects.create_user(
            username="admin_user",
            password="testpass123",
        )
        self.admin_user.groups.add(self.admin_group)

        self.med_admin_user = self.User.objects.create_user(
            username="med_admin_user",
            password="testpass123",
        )
        self.med_admin_user.groups.add(self.med_admin_group)

        self.doctor_user = self.User.objects.create_user(
            username="doctor_user",
            password="testpass123",
        )
        self.doctor_user.groups.add(self.doctors_group)

        self.no_group_user = self.User.objects.create_user(
            username="plain_user",
            password="testpass123",
        )

        self.cabinet = Cabinet.objects.create(
            number=1,
            name_of_cabinet="Кабинет врача",
        )
        self.doctor = Doctor.objects.create(
            first_name="Иван",
            last_name="Иванович",
            surname="Петров",
            specialization=Doctor.DoctorSpecialization.RHEUMATOLOGIST,
            provided_services=[
                MedicalServiceCategory.FIRST_CONSULTATION,
                MedicalServiceCategory.SECOND_CONSULTATION,
            ],
        )
        self.service = MedicalService.objects.create(
            code="CONS-001",
            name="Консультация ревматолога",
            price=2500,
            category=MedicalServiceCategory.FIRST_CONSULTATION,
            is_active=True,
        )
        self.patient = Patient.objects.create(
            surname="Сидорова",
            first_name="Мария",
            last_name="Ивановна",
            phone_number="+79990000011",
            card_number=88801,
            date_of_birth=date(1985, 5, 20),
        )

        self.previous_slot = TimeSlot.objects.create(
            doctor=self.doctor,
            cabinet=self.cabinet,
            date=date(2026, 3, 10),
            start_time=time(9, 0),
            end_time=time(9, 10),
            slot_type="working",
        )
        self.current_slot = TimeSlot.objects.create(
            doctor=self.doctor,
            cabinet=self.cabinet,
            date=date(2026, 3, 17),
            start_time=time(9, 0),
            end_time=time(9, 10),
            slot_type="working",
        )
        self.create_slot = TimeSlot.objects.create(
            doctor=self.doctor,
            cabinet=self.cabinet,
            date=date(2026, 3, 25),
            start_time=time(9, 0),
            end_time=time(9, 10),
            slot_type="working",
        )

        self.previous_appointment = Appointment.objects.create(
            time_slot=self.previous_slot,
            patient=self.patient,
            service=self.service,
            insurance_type=Appointment.InsuranceType.PAID,
            status=Appointment.AppointmentStatus.COMPLETED,
        )
        self.current_appointment = Appointment.objects.create(
            time_slot=self.current_slot,
            patient=self.patient,
            service=self.service,
            insurance_type=Appointment.InsuranceType.PAID,
            status=Appointment.AppointmentStatus.SCHEDULED,
        )
        self.create_appointment = Appointment.objects.create(
            time_slot=self.create_slot,
            patient=self.patient,
            service=self.service,
            insurance_type=Appointment.InsuranceType.PAID,
            status=Appointment.AppointmentStatus.SCHEDULED,
        )

        self.diagnosis = MKB10Diagnosis.objects.create(
            code="M05.8",
            name="Другие серопозитивные ревматоидные артриты",
            chapter="Болезни костно-мышечной системы",
            block="Артриты",
            is_active=True,
        )
        self.extra_diagnoses = [
            MKB10Diagnosis.objects.create(
                code=f"M10.{index}",
                name=f"Тестовый диагноз {index}",
                chapter="Глава",
                block="Блок",
                is_active=True,
            )
            for index in range(12)
        ]

        self.previous_treatment = DoctorTreatment.objects.create(
            appointment=self.previous_appointment,
            complaints="Старые жалобы",
            life_anamnesis="Анамнез жизни",
            disease_anamnesis="Анамнез заболевания",
            objective_status="Объективный статус",
            additional_surveys="Анализы",
            diagnosis="Основной диагноз",
            recommendations="Старые рекомендации",
        )
        self.previous_treatment.mkb10_diagnoses.add(self.diagnosis)

        self.current_treatment = DoctorTreatment.objects.create(
            appointment=self.current_appointment,
            complaints="Текущие жалобы",
            recommendations="Текущие рекомендации",
        )

    def login(self, user):
        client = Client()
        client.force_login(user)
        return client

    def get_treatment_form_data(self, **overrides):
        data = {
            "complaints": "Новые жалобы",
            "life_anamnesis": "Новый анамнез жизни",
            "disease_anamnesis": "Новое течение заболевания",
            "objective_status": "Новый объективный статус",
            "additional_surveys": "Новые обследования",
            "diagnosis": "Новый диагноз",
            "mkb10_diagnoses": [str(self.diagnosis.id)],
            "recommendations": "Новые рекомендации",
            "copy_from_treatment": "",
            "copy_fields": "",
        }
        data.update(overrides)
        return data


class TreatmentViewTests(TreatmentBaseTestCase):
    def test_create_treatment(self):
        client = self.login(self.doctor_user)

        response = client.post(
            reverse(
                "treatment:treatment_create",
                kwargs={"appointment_id": self.create_appointment.pk},
            ),
            data=self.get_treatment_form_data(),
        )

        created_treatment = DoctorTreatment.objects.get(appointment=self.create_appointment)
        self.assertRedirects(
            response,
            reverse("treatment:treatment_detail", kwargs={"pk": created_treatment.pk}),
        )
        self.assertEqual(created_treatment.complaints, "Новые жалобы")
        self.assertEqual(created_treatment.recommendations, "Новые рекомендации")
        self.assertEqual(created_treatment.mkb10_diagnoses.count(), 1)

    def test_create_view_redirects_to_existing_treatment_on_get(self):
        client = self.login(self.doctor_user)

        response = client.get(
            reverse(
                "treatment:treatment_create",
                kwargs={"appointment_id": self.current_appointment.pk},
            )
        )

        self.assertRedirects(
            response,
            reverse("treatment:treatment_detail", kwargs={"pk": self.current_treatment.pk}),
        )

    def test_create_view_redirects_to_existing_treatment_on_post_without_duplicate(self):
        client = self.login(self.doctor_user)
        initial_count = DoctorTreatment.objects.count()

        response = client.post(
            reverse(
                "treatment:treatment_create",
                kwargs={"appointment_id": self.current_appointment.pk},
            ),
            data=self.get_treatment_form_data(
                complaints="РџРѕРІС‚РѕСЂРЅР°СЏ РѕС‚РїСЂР°РІРєР° С„РѕСЂРјС‹",
            ),
        )

        self.assertRedirects(
            response,
            reverse("treatment:treatment_detail", kwargs={"pk": self.current_treatment.pk}),
        )
        self.assertEqual(DoctorTreatment.objects.count(), initial_count)

    def test_detail_view(self):
        client = self.login(self.doctor_user)

        response = client.get(
            reverse("treatment:treatment_detail", kwargs={"pk": self.current_treatment.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["treatment"].pk, self.current_treatment.pk)

    def test_update_treatment(self):
        client = self.login(self.med_admin_user)

        response = client.post(
            reverse("treatment:treatment_update", kwargs={"pk": self.current_treatment.pk}),
            data=self.get_treatment_form_data(
                complaints="Обновленные жалобы",
                recommendations="Обновленные рекомендации",
            ),
        )

        self.assertRedirects(
            response,
            reverse("treatment:treatment_detail", kwargs={"pk": self.current_treatment.pk}),
        )
        self.current_treatment.refresh_from_db()
        self.assertEqual(self.current_treatment.complaints, "Обновленные жалобы")
        self.assertEqual(
            self.current_treatment.recommendations, "Обновленные рекомендации"
        )

    def test_delete_treatment(self):
        client = self.login(self.doctor_user)

        response = client.post(
            reverse("treatment:treatment_delete", kwargs={"pk": self.current_treatment.pk})
        )

        self.assertRedirects(
            response,
            reverse(
                "treatment:patient_treatments",
                kwargs={"patient_id": self.patient.pk},
            ),
        )
        self.assertFalse(
            DoctorTreatment.objects.filter(pk=self.current_treatment.pk).exists()
        )

    def test_print_treatment_document(self):
        client = self.login(self.doctor_user)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as temp_file:
            temp_file.write(b"fake docx content")
            temp_path = temp_file.name

        try:
            with patch(
                "treatment.views.TreatmentDocumentGenerator.generate_treatment_docx",
                return_value=(temp_path, "treatment.docx"),
            ) as mocked_generator:
                response = client.get(
                    reverse(
                        "treatment:treatment_print",
                        kwargs={"pk": self.current_treatment.pk},
                    )
                )

            self.assertEqual(response.status_code, 200)
            self.assertEqual(
                response["Content-Type"],
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
            self.assertIn("treatment.docx", response["Content-Disposition"])
            mocked_generator.assert_called_once_with(self.current_treatment)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_patient_treatments_list(self):
        client = self.login(self.doctor_user)

        response = client.get(
            reverse(
                "treatment:patient_treatments",
                kwargs={"patient_id": self.patient.pk},
            )
        )

        self.assertEqual(response.status_code, 200)
        treatments = list(response.context["treatments"])
        self.assertEqual(len(treatments), 2)
        self.assertEqual(response.context["patient"].pk, self.patient.pk)


class TreatmentCopyAndSearchTests(TreatmentBaseTestCase):
    def test_patient_treatments_for_copy_returns_previous_treatments_and_excludes_current(self):
        client = self.login(self.doctor_user)

        response = client.get(
            reverse(
                "treatment:patient_treatments_for_copy",
                kwargs={"patient_id": self.patient.pk},
            ),
            {"current_appointment": self.current_appointment.pk},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()["treatments"]
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["id"], self.previous_treatment.pk)
        self.assertTrue(payload[0]["has_mkb10"])

    def test_get_previous_treatment_data_returns_expected_fields(self):
        client = self.login(self.med_admin_user)

        response = client.get(
            reverse(
                "treatment:get_previous_treatment_data",
                kwargs={"pk": self.previous_treatment.pk},
            )
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["complaints"], "Старые жалобы")
        self.assertEqual(payload["diagnosis"], "Основной диагноз")
        self.assertEqual(payload["recommendations"], "Старые рекомендации")
        self.assertEqual(payload["mkb10_diagnoses"][0]["code"], self.diagnosis.code)

    def test_copy_endpoints_allow_only_medical_staff(self):
        anonymous_copy_response = self.client.get(
            reverse(
                "treatment:patient_treatments_for_copy",
                kwargs={"patient_id": self.patient.pk},
            ),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        anonymous_previous_response = self.client.get(
            reverse(
                "treatment:get_previous_treatment_data",
                kwargs={"pk": self.previous_treatment.pk},
            )
        )

        self.assertEqual(anonymous_copy_response.status_code, 302)
        self.assertIn("login", anonymous_copy_response.url)
        self.assertEqual(anonymous_previous_response.status_code, 302)
        self.assertIn("login", anonymous_previous_response.url)

        client = self.login(self.no_group_user)
        forbidden_copy_response = client.get(
            reverse(
                "treatment:patient_treatments_for_copy",
                kwargs={"patient_id": self.patient.pk},
            ),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        forbidden_previous_response = client.get(
            reverse(
                "treatment:get_previous_treatment_data",
                kwargs={"pk": self.previous_treatment.pk},
            )
        )

        self.assertEqual(forbidden_copy_response.status_code, 403)
        self.assertEqual(forbidden_previous_response.status_code, 403)

    def test_mkb10_search_short_query_returns_empty_list(self):
        client = self.login(self.doctor_user)

        response = client.get(reverse("treatment:mkb10_search"), {"q": "M"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_mkb10_search_returns_not_more_than_ten_results(self):
        client = self.login(self.doctor_user)

        response = client.get(reverse("treatment:mkb10_search"), {"q": "Тестовый"})

        self.assertEqual(response.status_code, 200)
        results = response.json()
        self.assertLessEqual(len(results), 10)
        self.assertEqual(results[0]["name"], "Тестовый диагноз 0")

    def test_mkb10_search_allows_only_medical_staff(self):
        anonymous_response = self.client.get(
            reverse("treatment:mkb10_search"), {"q": "Тестовый"}
        )
        self.assertEqual(anonymous_response.status_code, 302)
        self.assertIn("login", anonymous_response.url)

        client = self.login(self.no_group_user)
        forbidden_response = client.get(
            reverse("treatment:mkb10_search"), {"q": "Тестовый"}
        )
        self.assertEqual(forbidden_response.status_code, 403)
