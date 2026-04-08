import json
from datetime import date

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase
from django.urls import reverse

from patients.models import Patient, ReserveList, ReservePatient, WaitlistPatient
from timetable.models import Doctor


class PatientAccessBaseTestCase(TestCase):
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

        self.patient = Patient.objects.create(
            surname="Иванов",
            first_name="Иван",
            last_name="Иванович",
            phone_number="+79991234567",
            card_number="12345",
            card_number_IP="54321",
            card_number_OMS="777777",
            date_of_birth=date(1980, 3, 19),
        )

    def login(self, user, enforce_csrf_checks=False):
        client = Client(enforce_csrf_checks=enforce_csrf_checks)
        client.force_login(user)
        return client


class PatientPageAccessTests(PatientAccessBaseTestCase):
    def test_admin_sees_edit_and_delete_buttons_on_patient_list(self):
        client = self.login(self.admin_user)

        response = client.get(reverse("patients:patient_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response, reverse("patients:patient_update", kwargs={"pk": self.patient.pk})
        )
        self.assertContains(
            response, reverse("patients:patient_delete", kwargs={"pk": self.patient.pk})
        )

    def test_medical_admin_sees_edit_but_not_delete_button_on_patient_list(self):
        client = self.login(self.med_admin_user)

        response = client.get(reverse("patients:patient_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response, reverse("patients:patient_update", kwargs={"pk": self.patient.pk})
        )
        self.assertNotContains(
            response, reverse("patients:patient_delete", kwargs={"pk": self.patient.pk})
        )

    def test_doctor_does_not_see_edit_and_delete_buttons_on_patient_list(self):
        client = self.login(self.doctor_user)

        response = client.get(reverse("patients:patient_list"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(
            response, reverse("patients:patient_update", kwargs={"pk": self.patient.pk})
        )
        self.assertNotContains(
            response, reverse("patients:patient_delete", kwargs={"pk": self.patient.pk})
        )

    def test_user_without_group_gets_403_on_patient_pages(self):
        client = self.login(self.no_group_user)

        list_response = client.get(reverse("patients:patient_list"))
        detail_response = client.get(
            reverse("patients:patient_detail", kwargs={"pk": self.patient.pk})
        )
        update_response = client.get(
            reverse("patients:patient_update", kwargs={"pk": self.patient.pk})
        )

        self.assertEqual(list_response.status_code, 403)
        self.assertEqual(detail_response.status_code, 403)
        self.assertEqual(update_response.status_code, 403)


class PatientApiAccessTests(PatientAccessBaseTestCase):
    def test_check_patient_api_is_available_for_admin_med_admin_and_doctor(self):
        payload = {
            "surname": self.patient.surname,
            "first_name": self.patient.first_name,
            "last_name": self.patient.last_name,
            "date_of_birth": self.patient.date_of_birth.isoformat(),
        }

        for user in (self.admin_user, self.med_admin_user, self.doctor_user):
            with self.subTest(user=user.username):
                client = self.login(user)
                response = client.post(
                    reverse("patients:api_check_patient"),
                    data=json.dumps(payload),
                    content_type="application/json",
                )

                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.json()["exists"])

    def test_search_patients_api_is_available_for_admin_med_admin_and_doctor(self):
        for user in (self.admin_user, self.med_admin_user, self.doctor_user):
            with self.subTest(user=user.username):
                client = self.login(user)
                response = client.get(
                    reverse("patients:api_search_patients"), {"q": "Иванов"}
                )

                self.assertEqual(response.status_code, 200)
                self.assertGreaterEqual(response.json()["count"], 1)

    def test_anonymous_user_is_redirected_to_login_for_patient_apis(self):
        check_response = self.client.post(
            reverse("patients:api_check_patient"),
            data=json.dumps({"surname": "Иванов", "first_name": "Иван"}),
            content_type="application/json",
        )
        search_response = self.client.get(
            reverse("patients:api_search_patients"), {"q": "Иванов"}
        )

        self.assertEqual(check_response.status_code, 302)
        self.assertIn(reverse("users:login"), check_response.url)
        self.assertEqual(search_response.status_code, 302)
        self.assertIn(reverse("users:login"), search_response.url)

    def test_user_without_group_gets_403_for_patient_apis(self):
        client = self.login(self.no_group_user)

        check_response = client.post(
            reverse("patients:api_check_patient"),
            data=json.dumps({"surname": "Иванов", "first_name": "Иван"}),
            content_type="application/json",
        )
        search_response = client.get(
            reverse("patients:api_search_patients"), {"q": "Иванов"}
        )

        self.assertEqual(check_response.status_code, 403)
        self.assertEqual(search_response.status_code, 403)


class PatientSearchApiTests(PatientAccessBaseTestCase):
    def setUp(self):
        super().setUp()
        self.client = self.login(self.admin_user)

        self.second_patient = Patient.objects.create(
            surname="Петров",
            first_name="Петр",
            last_name="Петрович",
            phone_number="+78880001122",
            card_number="67890",
            card_number_IP="1001",
            card_number_OMS="2002",
            date_of_birth=date(1990, 9, 6),
        )

    def test_search_patients_by_full_name(self):
        response = self.client.get(
            reverse("patients:api_search_patients"), {"q": "Иванов"}
        )

        self.assertEqual(response.status_code, 200)
        patients = response.json()["patients"]
        self.assertTrue(any(p["id"] == self.patient.id for p in patients))

    def test_search_patients_by_phone(self):
        response = self.client.get(
            reverse("patients:api_search_patients"),
            {"q": self.second_patient.phone_number[-6:]},
        )

        self.assertEqual(response.status_code, 200)
        patients = response.json()["patients"]
        self.assertTrue(any(p["id"] == self.second_patient.id for p in patients))

    def test_search_patients_by_card_number(self):
        response = self.client.get(
            reverse("patients:api_search_patients"),
            {"q": self.second_patient.card_number},
        )

        self.assertEqual(response.status_code, 200)
        patients = response.json()["patients"]
        self.assertTrue(any(p["id"] == self.second_patient.id for p in patients))

    def test_search_patients_by_date_of_birth(self):
        response = self.client.get(
            reverse("patients:api_search_patients"), {"q": "19.03.1980"}
        )

        self.assertEqual(response.status_code, 200)
        patients = response.json()["patients"]
        self.assertTrue(any(p["id"] == self.patient.id for p in patients))

    def test_short_search_query_returns_400_but_does_not_crash(self):
        response = self.client.get(reverse("patients:api_search_patients"), {"q": "И"})

        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())


class PatientCrudViewTests(PatientAccessBaseTestCase):
    def test_medical_admin_can_create_patient_and_gets_redirect(self):
        client = self.login(self.med_admin_user)

        response = client.post(
            reverse("patients:patient_create"),
            data={
                "surname": "Смирнова",
                "first_name": "Анна",
                "last_name": "Игоревна",
                "phone_number": "+79990001122",
                "card_number": "99901",
                "date_of_birth": "1992-04-15",
            },
        )

        self.assertRedirects(response, reverse("patients:patient_list"))
        created_patient = Patient.objects.get(card_number=99901)
        self.assertEqual(created_patient.surname, "Смирнова")
        self.assertEqual(created_patient.phone_number, "+79990001122")

    def test_medical_admin_can_update_patient_and_gets_redirect_to_detail(self):
        client = self.login(self.med_admin_user)

        response = client.post(
            reverse("patients:patient_update", kwargs={"pk": self.patient.pk}),
            data={
                "surname": "Иванова",
                "first_name": "Ирина",
                "last_name": "Ивановна",
                "date_of_birth": "1980-03-19",
                "gender": "female",
                "phone_number": "+79995554433",
                "email": "patient@example.com",
                "trusted_person": "Супруг",
                "card_number": "12345",
                "card_number_IP": "65432",
                "card_number_OMS": "OMS-65432",
                "area": "НО",
                "locality": "Поселок",
                "city": "Новосибирск",
                "district": "Центральный",
                "street": "Ленина",
                "home": "10",
                "building": "2",
                "apartment": "15",
                "passport_series": "",
                "passport_number": "",
                "passport_issue_date": "",
                "who_issued_the_passport": "",
                "polis_oms": "1234567890",
                "snils": "123-456-789 00",
                "insurance_company": "СОГАЗ",
            },
        )

        self.assertRedirects(
            response, reverse("patients:patient_detail", kwargs={"pk": self.patient.pk})
        )
        self.patient.refresh_from_db()
        self.assertEqual(self.patient.surname, "Иванова")
        self.assertEqual(self.patient.first_name, "Ирина")
        self.assertEqual(self.patient.phone_number, "+79995554433")
        self.assertEqual(self.patient.city, "Новосибирск")
        self.assertEqual(self.patient.card_number_IP, 65432)

    def test_only_admin_can_delete_patient(self):
        med_admin_client = self.login(self.med_admin_user)
        forbidden_response = med_admin_client.post(
            reverse("patients:patient_delete", kwargs={"pk": self.patient.pk})
        )
        self.assertEqual(forbidden_response.status_code, 403)
        self.assertTrue(Patient.objects.filter(pk=self.patient.pk).exists())

        admin_client = self.login(self.admin_user)
        response = admin_client.post(
            reverse("patients:patient_delete", kwargs={"pk": self.patient.pk})
        )

        self.assertRedirects(response, reverse("patients:patient_list"))
        self.assertFalse(Patient.objects.filter(pk=self.patient.pk).exists())


class ReserveAndWaitlistViewTests(PatientAccessBaseTestCase):
    def setUp(self):
        super().setUp()
        self.reserve_doctor = Doctor.objects.create(
            first_name="Иван",
            last_name="Иванович",
            surname="Петров",
            specialization=Doctor.DoctorSpecialization.RHEUMATOLOGIST,
            provided_services=[],
        )
        self.reserve_list = ReserveList.objects.create(
            doctor=self.reserve_doctor,
            month=4,
            year=2026,
        )
        self.reserve_entry = ReservePatient.objects.create(
            reserve_list=self.reserve_list,
            patient=self.patient,
            surname=self.patient.surname,
            first_name=self.patient.first_name,
            last_name=self.patient.last_name,
            phone_number=self.patient.phone_number,
            date_of_birth=self.patient.date_of_birth,
            comment="тестовый комментарий",
        )
        self.waitlist_entry = WaitlistPatient.objects.create(
            doctor=self.reserve_doctor,
            patient=self.patient,
            surname=self.patient.surname,
            first_name=self.patient.first_name,
            last_name=self.patient.last_name,
            phone_number=self.patient.phone_number,
            date_of_birth=self.patient.date_of_birth,
            comment="Ожидание",
        )

    def test_reserve_create_creates_new_patient_and_entry(self):
        client = self.login(self.med_admin_user)

        response = client.post(
            reverse("patients:reserve_patient_create"),
            data={
                "doctor": self.reserve_doctor.id,
                "month": "5",
                "year": "2026",
                "surname": "Новиков",
                "first_name": "Олег",
                "last_name": "Олегович",
                "phone_number": "+79998887766",
                "date_of_birth": "1991-01-10",
                "comment": "Новый пациент",
            },
        )

        self.assertRedirects(response, reverse("patients:reserve_main"))
        created_patient = Patient.objects.get(
            surname="Новиков",
            first_name="Олег",
            date_of_birth=date(1991, 1, 10),
        )
        reserve_entry = ReservePatient.objects.get(
            surname="Новиков",
            first_name="Олег",
            reserve_list__doctor=self.reserve_doctor,
            reserve_list__month=5,
            reserve_list__year=2026,
        )
        self.assertEqual(reserve_entry.patient_id, created_patient.id)
        self.assertEqual(reserve_entry.comment, "Новый пациент")

    def test_reserve_create_reuses_existing_patient(self):
        client = self.login(self.med_admin_user)
        initial_patient_count = Patient.objects.count()

        response = client.post(
            reverse("patients:reserve_patient_create"),
            data={
                "doctor": self.reserve_doctor.id,
                "month": "6",
                "year": "2026",
                "surname": self.patient.surname,
                "first_name": self.patient.first_name,
                "last_name": self.patient.last_name,
                "phone_number": self.patient.phone_number,
                "date_of_birth": self.patient.date_of_birth.isoformat(),
                "comment": "Используем существующего",
            },
        )

        self.assertRedirects(response, reverse("patients:reserve_main"))
        self.assertEqual(Patient.objects.count(), initial_patient_count)
        reserve_entry = ReservePatient.objects.get(
            reserve_list__doctor=self.reserve_doctor,
            reserve_list__month=6,
            reserve_list__year=2026,
            patient=self.patient,
        )
        self.assertEqual(reserve_entry.patient_id, self.patient.id)

    def test_reserve_update_changes_only_comment(self):
        client = self.login(self.doctor_user)

        response = client.post(
            reverse(
                "patients:reserve_patient_update", kwargs={"pk": self.reserve_entry.pk}
            ),
            data={"comment": "Обновленный комментарий"},
        )

        self.assertRedirects(response, reverse("patients:reserve_main"))
        self.reserve_entry.refresh_from_db()
        self.assertEqual(self.reserve_entry.comment, "Обновленный комментарий")
        self.assertEqual(self.reserve_entry.patient_id, self.patient.id)

    def test_waitlist_create_update_and_delete_work(self):
        doctor_client = self.login(self.doctor_user)

        create_response = doctor_client.post(
            reverse("patients:waitlist_create"),
            data={
                "doctor": self.reserve_doctor.id,
                "surname": "Волков",
                "first_name": "Павел",
                "last_name": "Павлович",
                "phone_number": "+79997776655",
                "date_of_birth": "1988-08-08",
                "comment": "Позвонить при отмене",
            },
        )
        self.assertEqual(create_response.status_code, 302)
        self.assertEqual(
            create_response.url, reverse("timetable:reschedule_requests")
        )

        waitlist_patient = WaitlistPatient.objects.get(
            surname="Волков",
            first_name="Павел",
        )

        update_response = doctor_client.post(
            reverse("patients:waitlist_update", kwargs={"pk": waitlist_patient.pk}),
            data={
                "doctor": self.reserve_doctor.id,
                "surname": "Волков",
                "first_name": "Павел",
                "last_name": "Павлович",
                "phone_number": "+79997776655",
                "date_of_birth": "1988-08-08",
                "comment": "Обновленный комментарий",
            },
        )
        self.assertEqual(update_response.status_code, 302)
        self.assertEqual(
            update_response.url, reverse("timetable:reschedule_requests")
        )
        waitlist_patient.refresh_from_db()
        self.assertEqual(waitlist_patient.comment, "Обновленный комментарий")

        delete_client = self.login(self.med_admin_user)
        delete_response = delete_client.post(
            reverse("patients:waitlist_delete", kwargs={"pk": waitlist_patient.pk})
        )
        self.assertEqual(delete_response.status_code, 302)
        self.assertEqual(
            delete_response.url, reverse("timetable:reschedule_requests")
        )
        self.assertFalse(WaitlistPatient.objects.filter(pk=waitlist_patient.pk).exists())

    def test_roles_without_access_get_403_on_reserve_and_waitlist_views(self):
        no_group_client = self.login(self.no_group_user)

        self.assertEqual(
            no_group_client.get(reverse("patients:reserve_main")).status_code, 403
        )
        self.assertEqual(
            no_group_client.get(reverse("patients:reserve_patient_create")).status_code,
            403,
        )
        self.assertEqual(
            no_group_client.get(reverse("patients:waitlist_list")).status_code, 403
        )
        self.assertEqual(
            no_group_client.get(reverse("patients:waitlist_create")).status_code, 403
        )

    def test_doctor_cannot_delete_reserve_or_waitlist_entries(self):
        client = self.login(self.doctor_user)

        reserve_delete_response = client.post(
            reverse(
                "patients:reserve_patient_delete", kwargs={"pk": self.reserve_entry.pk}
            )
        )
        waitlist_delete_response = client.post(
            reverse("patients:waitlist_delete", kwargs={"pk": self.waitlist_entry.pk})
        )

        self.assertEqual(reserve_delete_response.status_code, 403)
        self.assertEqual(waitlist_delete_response.status_code, 403)
