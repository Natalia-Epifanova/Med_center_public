import json
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.messages import get_messages
from django.core.cache import cache
from datetime import date, time

from django.middleware.csrf import _get_new_csrf_string
from django.test import Client, TestCase
from django.urls import reverse

from appointments.forms.forms import AppointmentSimpleEditForm, AppointmentForm
from appointments.models import Appointment, AppointmentChain
from patients.models import Patient
from timetable.models import (
    Cabinet,
    Doctor,
    MedicalService,
    MedicalServiceCategory,
    TimeSlot,
)


class AppointmentSimpleEditFormTests(TestCase):
    def setUp(self):
        cache.clear()
        self.visit_date = date(2026, 3, 17)

        self.doctor_cabinet = Cabinet.objects.create(
            number=1,
            name_of_cabinet="Кабинет врача",
        )
        self.procedural_cabinet = Cabinet.objects.create(
            number=6,
            name_of_cabinet="Процедурный кабинет",
        )

        self.doctor = Doctor.objects.create(
            first_name="Иван",
            last_name="Иванович",
            surname="Петров",
            specialization=Doctor.DoctorSpecialization.RHEUMATOLOGIST,
            provided_services=[
                MedicalServiceCategory.MEDICAL_BLOCKADES,
                MedicalServiceCategory.JOINT_ULTRASOUND,
            ],
        )

        self.nurse = Doctor.objects.create(
            first_name="Анна",
            last_name="Сергеевна",
            surname="Медсестра",
            specialization=Doctor.DoctorSpecialization.NURSE,
            provided_services=[],
        )

        self.blockade_service = MedicalService.objects.create(
            code="BL-001",
            name="Околосуставное введение препарата",
            price=1500,
            category=MedicalServiceCategory.MEDICAL_BLOCKADES,
            is_active=True,
        )

        self.us_service = MedicalService.objects.create(
            code="US-001",
            name="УЗИ коленного сустава",
            price=1200,
            category=MedicalServiceCategory.JOINT_ULTRASOUND,
            is_active=True,
        )

        self.patient = Patient.objects.create(
            surname="Сидорова",
            first_name="Мария",
            last_name="Ивановна",
            date_of_birth=date(1985, 5, 20),
        )

        self.main_slot = TimeSlot.objects.create(
            doctor=self.doctor,
            cabinet=self.doctor_cabinet,
            date=self.visit_date,
            start_time=time(9, 0),
            end_time=time(9, 10),
            slot_type="working",
        )

        self.main_appointment = Appointment.objects.create(
            time_slot=self.main_slot,
            patient=self.patient,
            service=self.blockade_service,
            insurance_type=Appointment.InsuranceType.PAID,
            status=Appointment.AppointmentStatus.SCHEDULED,
            comment="Основная запись",
        )

        self.procedural_slot = TimeSlot.objects.create(
            doctor=self.nurse,
            cabinet=self.procedural_cabinet,
            date=self.visit_date,
            start_time=time(9, 0),
            end_time=time(9, 10),
            slot_type="working",
        )

        self.procedural_appointment = Appointment.objects.create(
            time_slot=self.procedural_slot,
            patient=self.patient,
            service=self.blockade_service,
            insurance_type=Appointment.InsuranceType.PAID,
            status=Appointment.AppointmentStatus.SCHEDULED,
            comment=self.doctor.surname,
            is_consecutive=True,
            previous_appointment=self.main_appointment,
        )

    def test_changing_procedural_service_to_regular_deletes_procedural_appointment(
        self,
    ):
        form = AppointmentSimpleEditForm(
            instance=self.main_appointment,
            data={
                "service": self.us_service.id,
                "insurance_type": Appointment.InsuranceType.PAID,
                "comment": "Меняем услугу на обычную",
                "allow_time_change": "",
                "new_time_slot_id": self.main_slot.id,
                "new_appointment_date": self.visit_date.isoformat(),
            },
        )

        self.assertTrue(form.is_valid(), form.errors)

        updated_appointment = form.save()

        self.assertEqual(updated_appointment.service_id, self.us_service.id)

        self.assertFalse(
            Appointment.objects.filter(
                previous_appointment=updated_appointment,
                time_slot__cabinet__number=6,
            ).exists()
        )

        self.assertFalse(TimeSlot.objects.filter(id=self.procedural_slot.id).exists())

    def test_changing_regular_service_to_procedural_creates_procedural_appointment(
        self,
    ):
        self.procedural_appointment.delete()
        self.procedural_slot.delete()

        self.main_appointment.service = self.us_service
        self.main_appointment.save()

        form = AppointmentSimpleEditForm(
            instance=self.main_appointment,
            data={
                "service": self.blockade_service.id,
                "insurance_type": Appointment.InsuranceType.PAID,
                "comment": "Меняем услугу на процедурную",
                "allow_time_change": "",
                "new_time_slot_id": self.main_slot.id,
                "new_appointment_date": self.visit_date.isoformat(),
            },
        )

        self.assertTrue(form.is_valid(), form.errors)

        updated_appointment = form.save()

        self.assertEqual(updated_appointment.service_id, self.blockade_service.id)

        procedural_appointment = Appointment.objects.filter(
            previous_appointment=updated_appointment,
            time_slot__cabinet__number=6,
        ).first()

        self.assertIsNotNone(procedural_appointment)
        self.assertEqual(procedural_appointment.patient_id, self.patient.id)
        self.assertEqual(procedural_appointment.service_id, self.blockade_service.id)
        self.assertEqual(procedural_appointment.time_slot.date, self.visit_date)
        self.assertEqual(procedural_appointment.time_slot.start_time, time(9, 0))
        self.assertEqual(procedural_appointment.time_slot.end_time, time(9, 10))

    def test_changing_time_moves_linked_procedural_appointment(self):
        """При изменении времени основной записи связанная процедурная запись переносится на новый слот."""
        new_main_slot = TimeSlot.objects.create(
            doctor=self.doctor,
            cabinet=self.doctor_cabinet,
            date=self.visit_date,
            start_time=time(9, 10),
            end_time=time(9, 20),
            slot_type="working",
        )

        old_procedural_slot_id = self.procedural_slot.id
        procedural_appointment_id = self.procedural_appointment.id

        form = AppointmentSimpleEditForm(
            instance=self.main_appointment,
            data={
                "service": self.blockade_service.id,
                "insurance_type": Appointment.InsuranceType.PAID,
                "comment": "Меняем время записи",
                "allow_time_change": "on",
                "new_time_slot_id": new_main_slot.id,
                "new_appointment_date": self.visit_date.isoformat(),
                "needs_procedural": "on",
            },
        )

        self.assertTrue(form.is_valid(), form.errors)

        updated_appointment = form.save()

        self.assertEqual(updated_appointment.time_slot_id, new_main_slot.id)

        procedural_appointment = Appointment.objects.get(id=procedural_appointment_id)
        self.assertEqual(
            procedural_appointment.previous_appointment_id, updated_appointment.id
        )
        self.assertEqual(procedural_appointment.time_slot.date, self.visit_date)
        self.assertEqual(procedural_appointment.time_slot.start_time, time(9, 10))
        self.assertEqual(procedural_appointment.time_slot.end_time, time(9, 20))
        self.assertEqual(procedural_appointment.time_slot.cabinet.number, 6)

        self.assertFalse(TimeSlot.objects.filter(id=old_procedural_slot_id).exists())


class AppointmentFormTests(TestCase):
    def setUp(self):
        cache.clear()
        self.visit_date = date(2026, 3, 17)

        self.doctor_cabinet = Cabinet.objects.create(
            number=1,
            name_of_cabinet="Кабинет врача",
        )
        self.procedural_cabinet = Cabinet.objects.create(
            number=6,
            name_of_cabinet="Процедурный кабинет",
        )

        self.doctor = Doctor.objects.create(
            first_name="Иван",
            last_name="Иванович",
            surname="Петров",
            specialization=Doctor.DoctorSpecialization.RHEUMATOLOGIST,
            provided_services=[
                MedicalServiceCategory.MEDICAL_BLOCKADES,
                MedicalServiceCategory.JOINT_ULTRASOUND,
            ],
        )

        self.nurse = Doctor.objects.create(
            first_name="Анна",
            last_name="Сергеевна",
            surname="Медсестра",
            specialization=Doctor.DoctorSpecialization.NURSE,
            provided_services=[],
        )

        self.us_service = MedicalService.objects.create(
            code="US-001",
            name="УЗИ коленного сустава",
            price=1200,
            category=MedicalServiceCategory.JOINT_ULTRASOUND,
            is_active=True,
        )

        self.main_slot = TimeSlot.objects.create(
            doctor=self.doctor,
            cabinet=self.doctor_cabinet,
            date=self.visit_date,
            start_time=time(10, 0),
            end_time=time(10, 10),
            slot_type="working",
        )

    def test_creating_regular_appointment_does_not_create_procedural_appointment(self):
        """Создание обычной записи не должно создавать связанную процедурную запись."""
        form = AppointmentForm(
            time_slot=self.main_slot,
            doctor=self.doctor,
            data={
                "service": self.us_service.id,
                "insurance_type": Appointment.InsuranceType.PAID,
                "needs_reschedule": "",
                "comment": "Обычная запись без процедурки",
                "appointment_chain_type": "none",
                "additional_appointments_data": "",
                "procedural_appointments_data": "",
                "needs_procedural": "",
                "allow_time_change": "",
                "new_time_slot_id": self.main_slot.id,
                "new_appointment_date": self.visit_date.isoformat(),
                "selected_blood_tests_input": "",
                "total_sum": "1200.00",
                "surname": "Сидорова",
                "first_name": "Мария",
                "last_name": "Ивановна",
                "date_of_birth": "1985-05-20",
                "phone": "",
            },
        )

        self.assertTrue(form.is_valid(), form.errors)

        appointment = form.save()

        self.assertEqual(appointment.service_id, self.us_service.id)
        self.assertEqual(appointment.time_slot_id, self.main_slot.id)

        self.assertFalse(
            Appointment.objects.filter(
                previous_appointment=appointment,
                time_slot__cabinet__number=6,
            ).exists()
        )

    def test_creating_appointment_with_needs_procedural_creates_linked_procedural_appointment(
        self,
    ):
        """Создание записи с флагом needs_procedural должно создавать связанную процедурную запись."""
        blockade_service = MedicalService.objects.create(
            code="BL-001",
            name="Блокада коленного сустава",
            price=1500,
            category=MedicalServiceCategory.MEDICAL_BLOCKADES,
            is_active=True,
        )

        form = AppointmentForm(
            time_slot=self.main_slot,
            doctor=self.doctor,
            data={
                "service": blockade_service.id,
                "insurance_type": Appointment.InsuranceType.PAID,
                "needs_reschedule": "",
                "comment": "Запись с процедуркой",
                "appointment_chain_type": "none",
                "additional_appointments_data": "",
                "procedural_appointments_data": "",
                "needs_procedural": "on",
                "allow_time_change": "",
                "new_time_slot_id": self.main_slot.id,
                "new_appointment_date": self.visit_date.isoformat(),
                "selected_blood_tests_input": "",
                "total_sum": "1500.00",
                "surname": "Сидорова",
                "first_name": "Мария",
                "last_name": "Ивановна",
                "date_of_birth": "1985-05-20",
                "phone": "",
            },
        )

        self.assertTrue(form.is_valid(), form.errors)

        appointment = form.save()

        self.assertEqual(appointment.service_id, blockade_service.id)
        self.assertEqual(appointment.time_slot_id, self.main_slot.id)

        procedural_appointment = Appointment.objects.filter(
            previous_appointment=appointment,
            time_slot__cabinet__number=6,
        ).first()

        self.assertIsNotNone(procedural_appointment)
        self.assertEqual(procedural_appointment.patient_id, appointment.patient_id)
        self.assertEqual(procedural_appointment.service_id, blockade_service.id)
        self.assertEqual(procedural_appointment.time_slot.date, self.visit_date)
        self.assertEqual(procedural_appointment.time_slot.start_time, time(10, 0))
        self.assertEqual(procedural_appointment.time_slot.end_time, time(10, 10))

    def test_creating_appointment_with_additional_doctor_creates_chain_and_related_appointment(
        self,
    ):
        """Создание записи с дополнительным врачом должно создавать связанную дополнительную запись и цепочку."""
        second_doctor_cabinet = Cabinet.objects.create(
            number=2,
            name_of_cabinet="Кабинет второго врача",
        )

        second_doctor = Doctor.objects.create(
            first_name="Елена",
            last_name="Петровна",
            surname="Епифанова",
            specialization=Doctor.DoctorSpecialization.RHEUMATOLOGIST,
            provided_services=[MedicalServiceCategory.JOINT_ULTRASOUND],
        )

        second_service = MedicalService.objects.create(
            code="US-002",
            name="УЗИ плечевого сустава",
            price=2000,
            category=MedicalServiceCategory.JOINT_ULTRASOUND,
            is_active=True,
        )

        second_slot = TimeSlot.objects.create(
            doctor=second_doctor,
            cabinet=second_doctor_cabinet,
            date=self.visit_date,
            start_time=time(10, 10),
            end_time=time(10, 20),
            slot_type="working",
        )

        additional_data = json.dumps(
            [
                {
                    "index": 1,
                    "doctor_id": second_doctor.id,
                    "service_id": second_service.id,
                    "time_slot_id": second_slot.id,
                    "comment": "Доп. запись к другому врачу",
                    "insurance_type": Appointment.InsuranceType.PAID,
                }
            ]
        )

        form = AppointmentForm(
            time_slot=self.main_slot,
            doctor=self.doctor,
            data={
                "service": self.us_service.id,
                "insurance_type": Appointment.InsuranceType.PAID,
                "needs_reschedule": "",
                "comment": "Основная запись",
                "appointment_chain_type": "another_doctor",
                "additional_appointments_data": additional_data,
                "procedural_appointments_data": "[]",
                "needs_procedural": "",
                "allow_time_change": "",
                "new_time_slot_id": self.main_slot.id,
                "new_appointment_date": self.visit_date.isoformat(),
                "selected_blood_tests_input": "",
                "total_sum": "1200.00",
                "surname": "Сидорова",
                "first_name": "Мария",
                "last_name": "Ивановна",
                "date_of_birth": "1985-05-20",
                "phone": "",
            },
        )

        self.assertTrue(form.is_valid(), form.errors)

        main_appointment = form.save()

        related_appointment = Appointment.objects.filter(
            patient=main_appointment.patient,
            time_slot=second_slot,
            is_chain_main=False,
        ).first()

        self.assertIsNotNone(related_appointment)
        self.assertEqual(related_appointment.service_id, second_service.id)

        chain = AppointmentChain.objects.filter(
            main_appointment=main_appointment,
            related_appointment=related_appointment,
        ).first()

        self.assertIsNotNone(chain)
        self.assertEqual(chain.order, 1)


class AppointmentAjaxSecurityAndStatusTests(TestCase):
    def setUp(self):
        cache.clear()
        self.User = get_user_model()
        self.admin_group, _ = Group.objects.get_or_create(name="Admin")
        self.med_admin_group, _ = Group.objects.get_or_create(
            name="Medical Center Administrator"
        )
        self.doctors_group, _ = Group.objects.get_or_create(name="Doctors")

        self.admin_user = self.User.objects.create_user(
            username="appointment_admin",
            password="testpass123",
        )
        self.admin_user.groups.add(self.admin_group)

        self.med_admin_user = self.User.objects.create_user(
            username="appointment_med_admin",
            password="testpass123",
        )
        self.med_admin_user.groups.add(self.med_admin_group)

        self.doctor_user = self.User.objects.create_user(
            username="appointment_doctor",
            password="testpass123",
        )
        self.doctor_user.groups.add(self.doctors_group)

        self.no_group_user = self.User.objects.create_user(
            username="appointment_plain",
            password="testpass123",
        )

        self.visit_date = date(2026, 3, 17)
        self.doctor_cabinet = Cabinet.objects.create(
            number=1,
            name_of_cabinet="Кабинет врача",
        )
        self.procedural_cabinet = Cabinet.objects.create(
            number=6,
            name_of_cabinet="Процедурный кабинет",
        )

        self.doctor = Doctor.objects.create(
            first_name="Иван",
            last_name="Иванович",
            surname="Петров",
            specialization=Doctor.DoctorSpecialization.RHEUMATOLOGIST,
            provided_services=[MedicalServiceCategory.JOINT_ULTRASOUND],
        )
        self.nurse = Doctor.objects.create(
            first_name="Анна",
            last_name="Сергеевна",
            surname="Медсестра",
            specialization=Doctor.DoctorSpecialization.NURSE,
            provided_services=[],
        )

        self.service = MedicalService.objects.create(
            code="US-100",
            name="УЗИ сустава",
            price=1200,
            category=MedicalServiceCategory.JOINT_ULTRASOUND,
            is_active=True,
        )

        self.patient = Patient.objects.create(
            surname="Сидоров",
            first_name="Семен",
            last_name="Ильич",
            date_of_birth=date(1985, 5, 20),
        )

        self.main_slot = TimeSlot.objects.create(
            doctor=self.doctor,
            cabinet=self.doctor_cabinet,
            date=self.visit_date,
            start_time=time(9, 0),
            end_time=time(9, 10),
            slot_type="working",
        )
        self.next_slot = TimeSlot.objects.create(
            doctor=self.doctor,
            cabinet=self.doctor_cabinet,
            date=self.visit_date,
            start_time=time(9, 10),
            end_time=time(9, 20),
            slot_type="working",
        )
        self.procedural_slot = TimeSlot.objects.create(
            doctor=self.nurse,
            cabinet=self.procedural_cabinet,
            date=self.visit_date,
            start_time=time(9, 0),
            end_time=time(9, 10),
            slot_type="working",
        )

        self.appointment = Appointment.objects.create(
            time_slot=self.main_slot,
            patient=self.patient,
            service=self.service,
            insurance_type=Appointment.InsuranceType.PAID,
            status=Appointment.AppointmentStatus.SCHEDULED,
        )
        self.procedural_appointment = Appointment.objects.create(
            time_slot=self.procedural_slot,
            patient=self.patient,
            service=self.service,
            insurance_type=Appointment.InsuranceType.PAID,
            status=Appointment.AppointmentStatus.SCHEDULED,
            is_consecutive=True,
            previous_appointment=self.appointment,
        )

    def login(self, user, enforce_csrf_checks=False):
        client = Client(enforce_csrf_checks=enforce_csrf_checks)
        client.force_login(user)
        return client

    def add_csrf(self, client):
        token = _get_new_csrf_string()
        client.cookies["csrftoken"] = token
        return token

    def test_post_without_csrf_returns_403_for_sensitive_ajax_endpoints(self):
        client = self.login(self.admin_user, enforce_csrf_checks=True)

        endpoints = [
            (
                reverse("appointments:api_doctor_services"),
                {"doctor_id": self.doctor.id, "date": self.visit_date.isoformat()},
                "application/json",
            ),
            (
                reverse("appointments:api_available_slots_for_doctor"),
                {"doctor_id": self.doctor.id, "date": self.visit_date.isoformat()},
                "application/json",
            ),
            (
                reverse("appointments:api_get_next_slot"),
                {
                    "doctor_id": self.doctor.id,
                    "date": self.visit_date.isoformat(),
                    "current_slot_id": self.main_slot.id,
                },
                "application/json",
            ),
            (
                reverse("appointments:api_check_procedural_availability"),
                {"date": self.visit_date.isoformat(), "time_slot_id": self.next_slot.id},
                "application/json",
            ),
            (
                reverse(
                    "appointments:appointment_update_status",
                    kwargs={"pk": self.appointment.pk},
                ),
                {"status": Appointment.AppointmentStatus.CONFIRMED},
                None,
            ),
            (
                reverse("patients:api_check_patient"),
                {
                    "surname": self.patient.surname,
                    "first_name": self.patient.first_name,
                },
                "application/json",
            ),
        ]

        for url, payload, content_type in endpoints:
            with self.subTest(url=url):
                if content_type == "application/json":
                    response = client.post(
                        url,
                        data=json.dumps(payload),
                        content_type=content_type,
                    )
                else:
                    response = client.post(url, data=payload)
                self.assertEqual(response.status_code, 403)

    def test_post_with_csrf_passes_for_sensitive_ajax_endpoints(self):
        client = self.login(self.admin_user, enforce_csrf_checks=True)
        token = self.add_csrf(client)

        doctor_services_response = client.post(
            reverse("appointments:api_doctor_services"),
            data=json.dumps(
                {"doctor_id": self.doctor.id, "date": self.visit_date.isoformat()}
            ),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=token,
        )
        slots_response = client.post(
            reverse("appointments:api_available_slots_for_doctor"),
            data=json.dumps(
                {"doctor_id": self.doctor.id, "date": self.visit_date.isoformat()}
            ),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=token,
        )
        next_slot_response = client.post(
            reverse("appointments:api_get_next_slot"),
            data=json.dumps(
                {
                    "doctor_id": self.doctor.id,
                    "date": self.visit_date.isoformat(),
                    "current_slot_id": self.main_slot.id,
                }
            ),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=token,
        )
        procedural_response = client.post(
            reverse("appointments:api_check_procedural_availability"),
            data=json.dumps(
                {"date": self.visit_date.isoformat(), "time_slot_id": self.next_slot.id}
            ),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=token,
        )
        status_response = client.post(
            reverse(
                "appointments:appointment_update_status",
                kwargs={"pk": self.appointment.pk},
            ),
            data={
                "status": Appointment.AppointmentStatus.CONFIRMED,
                "csrfmiddlewaretoken": token,
            },
            HTTP_X_CSRFTOKEN=token,
        )
        patient_check_response = client.post(
            reverse("patients:api_check_patient"),
            data=json.dumps(
                {
                    "surname": self.patient.surname,
                    "first_name": self.patient.first_name,
                }
            ),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=token,
        )

        self.assertEqual(doctor_services_response.status_code, 200)
        self.assertEqual(slots_response.status_code, 200)
        self.assertEqual(next_slot_response.status_code, 200)
        self.assertEqual(procedural_response.status_code, 200)
        self.assertEqual(status_response.status_code, 200)
        self.assertEqual(patient_check_response.status_code, 200)

    def test_check_procedural_availability_returns_conflict_data_without_server_error(
        self,
    ):
        client = self.login(self.admin_user, enforce_csrf_checks=True)
        token = self.add_csrf(client)

        conflicting_patient = Patient.objects.create(
            surname="Конфликтов",
            first_name="Петр",
            last_name="Пациентович",
            date_of_birth=date(1991, 1, 1),
        )
        conflicting_slot = TimeSlot.objects.create(
            doctor=self.nurse,
            cabinet=self.procedural_cabinet,
            date=self.visit_date,
            start_time=time(9, 10),
            end_time=time(9, 20),
            slot_type="working",
        )
        Appointment.objects.create(
            time_slot=conflicting_slot,
            patient=conflicting_patient,
            service=self.service,
            insurance_type=Appointment.InsuranceType.PAID,
            status=Appointment.AppointmentStatus.SCHEDULED,
        )

        response = client.post(
            reverse("appointments:api_check_procedural_availability"),
            data=json.dumps(
                {"date": self.visit_date.isoformat(), "time_slot_id": self.next_slot.id}
            ),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=token,
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertFalse(payload["is_available"])
        self.assertEqual(len(payload["occupied_slots"]), 1)
        self.assertEqual(payload["occupied_slots"][0]["patient"], conflicting_patient.full_name)

    def test_update_appointment_status_updates_status_successfully(self):
        client = self.login(self.admin_user)

        response = client.post(
            reverse(
                "appointments:appointment_update_status",
                kwargs={"pk": self.appointment.pk},
            ),
            data={"status": Appointment.AppointmentStatus.CONFIRMED},
        )

        self.assertEqual(response.status_code, 200)
        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.status, Appointment.AppointmentStatus.CONFIRMED)
        self.assertTrue(response.json()["success"])

    def test_update_appointment_status_syncs_linked_procedural_appointment(self):
        client = self.login(self.admin_user)

        response = client.post(
            reverse(
                "appointments:appointment_update_status",
                kwargs={"pk": self.appointment.pk},
            ),
            data={"status": Appointment.AppointmentStatus.COMPLETED},
        )

        self.assertEqual(response.status_code, 200)
        self.procedural_appointment.refresh_from_db()
        self.assertEqual(
            self.procedural_appointment.status,
            Appointment.AppointmentStatus.COMPLETED,
        )
        self.assertIn("synced_procedural", response.json())

    def test_update_appointment_status_rejects_invalid_status(self):
        client = self.login(self.admin_user)

        response = client.post(
            reverse(
                "appointments:appointment_update_status",
                kwargs={"pk": self.appointment.pk},
            ),
            data={"status": "invalid_status"},
        )

        self.assertEqual(response.status_code, 400)
        self.appointment.refresh_from_db()
        self.assertEqual(
            self.appointment.status, Appointment.AppointmentStatus.SCHEDULED
        )

    def test_update_appointment_status_denies_anonymous_and_user_without_permissions(
        self,
    ):
        anonymous_response = self.client.post(
            reverse(
                "appointments:appointment_update_status",
                kwargs={"pk": self.appointment.pk},
            ),
            data={"status": Appointment.AppointmentStatus.CONFIRMED},
        )

        client = self.login(self.no_group_user)
        no_group_response = client.post(
            reverse(
                "appointments:appointment_update_status",
                kwargs={"pk": self.appointment.pk},
            ),
            data={"status": Appointment.AppointmentStatus.CONFIRMED},
        )

        self.assertEqual(anonymous_response.status_code, 302)
        self.assertIn(reverse("users:login"), anonymous_response.url)
        self.assertEqual(no_group_response.status_code, 403)


class AppointmentBlacklistWarningTests(TestCase):
    def setUp(self):
        cache.clear()
        self.User = get_user_model()
        self.med_admin_group, _ = Group.objects.get_or_create(
            name="Medical Center Administrator"
        )
        self.med_admin_user = self.User.objects.create_user(
            username="blacklist_med_admin",
            password="testpass123",
        )
        self.med_admin_user.groups.add(self.med_admin_group)

        self.visit_date = date(2026, 3, 17)

        self.doctor_cabinet = Cabinet.objects.create(
            number=1,
            name_of_cabinet="Кабинет врача",
        )
        self.procedural_cabinet = Cabinet.objects.create(
            number=6,
            name_of_cabinet="Процедурный кабинет",
        )

        self.doctor = Doctor.objects.create(
            first_name="Иван",
            last_name="Иванович",
            surname="Петров",
            specialization=Doctor.DoctorSpecialization.RHEUMATOLOGIST,
            provided_services=[
                MedicalServiceCategory.JOINT_ULTRASOUND,
                MedicalServiceCategory.MEDICAL_BLOCKADES,
            ],
        )
        self.nurse = Doctor.objects.create(
            first_name="Анна",
            last_name="Сергеевна",
            surname="Медсестра",
            specialization=Doctor.DoctorSpecialization.NURSE,
            provided_services=[],
        )

        self.us_service = MedicalService.objects.create(
            code="US-BLACKLIST",
            name="УЗИ сустава",
            price=1200,
            category=MedicalServiceCategory.JOINT_ULTRASOUND,
            is_active=True,
        )
        self.blockade_service = MedicalService.objects.create(
            code="BL-BLACKLIST",
            name="Блокада сустава",
            price=1500,
            category=MedicalServiceCategory.MEDICAL_BLOCKADES,
            is_active=True,
        )

        self.main_slot = TimeSlot.objects.create(
            doctor=self.doctor,
            cabinet=self.doctor_cabinet,
            date=self.visit_date,
            start_time=time(10, 0),
            end_time=time(10, 10),
            slot_type="working",
        )

        self.blacklisted_patient = Patient.objects.create(
            surname="Сидоров",
            first_name="Семен",
            last_name="Ильич",
            date_of_birth=date(1985, 5, 20),
            is_blacklisted=True,
            blacklist_comment="Не явился на прошлый прием без предупреждения",
        )

    def login(self):
        client = Client()
        client.force_login(self.med_admin_user)
        return client

    def test_regular_appointment_create_shows_blacklist_warning_message(self):
        client = self.login()

        response = client.post(
            reverse(
                "appointments:appointment_create",
                kwargs={"time_slot_id": self.main_slot.id},
            ),
            data={
                "service": self.us_service.id,
                "insurance_type": Appointment.InsuranceType.PAID,
                "needs_reschedule": "",
                "comment": "Обычная запись",
                "appointment_chain_type": "none",
                "additional_appointments_data": "",
                "procedural_appointments_data": "",
                "needs_procedural": "",
                "allow_time_change": "",
                "new_time_slot_id": self.main_slot.id,
                "new_appointment_date": self.visit_date.isoformat(),
                "selected_blood_tests_input": "",
                "total_sum": "1200.00",
                "surname": self.blacklisted_patient.surname,
                "first_name": self.blacklisted_patient.first_name,
                "last_name": self.blacklisted_patient.last_name,
                "date_of_birth": self.blacklisted_patient.date_of_birth.isoformat(),
                "phone_number": "",
                "card_number": self.blacklisted_patient.card_number or "",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        messages = [str(message) for message in get_messages(response.wsgi_request)]
        self.assertTrue(
            any(
                "Пациент в черном списке. Причина: Не явился на прошлый прием без предупреждения"
                in message
                for message in messages
            ),
            messages,
        )

    def test_procedural_appointment_create_shows_blacklist_warning_message(self):
        client = self.login()

        response = client.post(
            reverse("appointments:appointment_create_procedural"),
            data={
                "service": self.blockade_service.id,
                "insurance_type": Appointment.InsuranceType.PAID,
                "needs_reschedule": "",
                "comment": "Процедурная запись",
                "appointment_chain_type": "none",
                "additional_appointments_data": "",
                "procedural_appointments_data": "",
                "selected_blood_tests_input": "",
                "total_sum": "1500.00",
                "surname": self.blacklisted_patient.surname,
                "first_name": self.blacklisted_patient.first_name,
                "last_name": self.blacklisted_patient.last_name,
                "date_of_birth": self.blacklisted_patient.date_of_birth.isoformat(),
                "phone_number": "",
                "card_number": self.blacklisted_patient.card_number or "",
                "procedural_start_time": "10:00",
                "procedural_end_time": "10:10",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        messages = [str(message) for message in get_messages(response.wsgi_request)]
        self.assertTrue(
            any(
                "Пациент в черном списке. Причина: Не явился на прошлый прием без предупреждения"
                in message
                for message in messages
            ),
            messages,
        )
