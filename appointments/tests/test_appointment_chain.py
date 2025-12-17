from appointments.models import Appointment, AppointmentChain

from django.test import TestCase
from appointments.models import Appointment, AppointmentChain
from timetable.models import TimeSlot, Doctor, MedicalService, Cabinet
from patients.models import Patient
from datetime import date, time


class AppointmentChainTestCase(TestCase):
    def setUp(self):
        # Создаем тестовые данные
        self.doctor1 = Doctor.objects.create(
            surname="Иванов",
            first_name="Иван",
            last_name="Иванович",
            specialization="rheumatologist",
        )

        self.doctor2 = Doctor.objects.create(
            surname="Петров",
            first_name="Петр",
            last_name="Петрович",
            specialization="neurologist",
        )

        self.cabinet = Cabinet.objects.create(number=1)

        self.service1 = MedicalService.objects.create(
            name="Консультация ревматолога", price=1000, category="consultation"
        )

        self.service2 = MedicalService.objects.create(
            name="Консультация невролога", price=1200, category="consultation"
        )

        self.patient = Patient.objects.create(
            surname="Сидоров", first_name="Сидор", phone_number="+79123456789"
        )

        # Создаем временные слоты
        self.slot1 = TimeSlot.objects.create(
            doctor=self.doctor1,
            cabinet=self.cabinet,
            date=date.today(),
            start_time=time(10, 0),
            end_time=time(10, 20),
            slot_type="working",
        )

        self.slot2 = TimeSlot.objects.create(
            doctor=self.doctor2,
            cabinet=self.cabinet,
            date=date.today(),
            start_time=time(11, 0),
            end_time=time(11, 20),
            slot_type="working",
        )

    def test_create_chain(self):
        """Тест создания цепочки записей"""
        # Создаем основную запись
        main_appointment = Appointment.objects.create(
            time_slot=self.slot1,
            patient=self.patient,
            service=self.service1,
            insurance_type="paid",
            is_chain_main=True,
            chain_type=Appointment.ChainType.SINGLE,
        )

        # Создаем связанную запись
        related_appointment = Appointment.objects.create(
            time_slot=self.slot2,
            patient=self.patient,
            service=self.service2,
            insurance_type="paid",
        )

        # Создаем связь
        chain = AppointmentChain.objects.create(
            main_appointment=main_appointment,
            related_appointment=related_appointment,
            chain_type=AppointmentChain.ChainType.ANOTHER_DOCTOR,
            order=1,
        )

        # Проверяем
        self.assertEqual(main_appointment.chain_type, Appointment.ChainType.SINGLE)

        # Обновляем тип цепочки
        main_appointment.chain_type = Appointment.ChainType.MULTIPLE_DOCTORS
        main_appointment.save()

        self.assertEqual(
            main_appointment.chain_type, Appointment.ChainType.MULTIPLE_DOCTORS
        )

        # ИСПРАВЛЕННАЯ ПРОВЕРКА
        chain_appointments = main_appointment.get_chain_appointments()
        self.assertEqual(len(chain_appointments), 2)

    def test_chain_methods(self):
        """Тест методов работы с цепочками"""
        main_appointment = Appointment.objects.create(
            time_slot=self.slot1,
            patient=self.patient,
            service=self.service1,
            insurance_type="paid",
            is_chain_main=True,
        )

        related_appointment = Appointment.objects.create(
            time_slot=self.slot2,
            patient=self.patient,
            service=self.service2,
            insurance_type="paid",
        )

        # Тестируем добавление связанной записи
        chain = main_appointment.add_related_appointment(
            related_appointment, chain_type=AppointmentChain.ChainType.ANOTHER_DOCTOR
        )

        self.assertIsNotNone(chain)
        self.assertEqual(
            main_appointment.chain_type, Appointment.ChainType.MULTIPLE_DOCTORS
        )
        self.assertTrue(main_appointment.has_related_appointments)

        # Тестируем получение цепочки
        chain_appointments = main_appointment.get_chain_appointments()
        self.assertEqual(len(chain_appointments), 2)
        self.assertIn(main_appointment, chain_appointments)
        self.assertIn(related_appointment, chain_appointments)

        # Тестируем удаление
        main_appointment.remove_related_appointment(related_appointment)
        self.assertFalse(main_appointment.has_related_appointments)
        self.assertEqual(main_appointment.chain_type, Appointment.ChainType.SINGLE)
