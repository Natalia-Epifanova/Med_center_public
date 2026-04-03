import json
from datetime import date

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase
from django.urls import reverse

from patients.models import Patient


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
