from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Max
from django.utils import timezone
from phonenumber_field.phonenumber import PhoneNumber

from patients.models import Patient


class PatientService:
    """Сервис для работы с пациентами с поддержкой PhoneNumberField"""

    @staticmethod
    @transaction.atomic
    def get_or_create_patient(patient_data: Dict[str, Any]) -> Tuple[Patient, bool]:
        """Создание или поиск пациента с обновлением данных"""
        cleaned_data = PatientService.clean_patient_data(patient_data)

        surname = cleaned_data.get("surname")
        first_name = cleaned_data.get("first_name")
        date_of_birth = cleaned_data.get("date_of_birth")
        last_name = cleaned_data.get("last_name", "")

        # Валидация обязательных полей
        if not surname or not first_name:
            raise ValidationError("Фамилия и имя обязательны")

        # ВАЖНОЕ ИЗМЕНЕНИЕ: Сначала ищем по ФИО + дате рождения
        if date_of_birth:
            # Строгий поиск: ФИО + дата рождения
            query = Patient.objects.filter(
                surname__iexact=surname,
                first_name__iexact=first_name,
                date_of_birth=date_of_birth,
            )

            if last_name:
                query = query.filter(last_name__iexact=last_name)
            else:
                query = query.filter(
                    models.Q(last_name="") | models.Q(last_name__isnull=True)
                )

            existing_patient = query.first()

            if existing_patient:
                # Нашли пациента с такими ФИО и датой рождения
                update_fields = []

                # Обновляем только пустые поля
                phone = cleaned_data.get("phone_number")
                if phone and (
                    not existing_patient.phone_number
                    or existing_patient.phone_number == ""
                ):
                    existing_patient.phone_number = phone
                    update_fields.append("phone_number")

                card_number = cleaned_data.get("card_number")
                if card_number and not existing_patient.card_number:
                    existing_patient.card_number = card_number
                    update_fields.append("card_number")

                if update_fields:
                    existing_patient.save(update_fields=update_fields)
                    print(
                        f"DEBUG: Обновлен пациент {existing_patient.id}: {update_fields}"
                    )

                return existing_patient, False

        # Если дата рождения не указана или не нашли - ищем только по ФИО
        query = Patient.objects.filter(
            surname__iexact=surname,
            first_name__iexact=first_name,
        )

        if last_name:
            query = query.filter(last_name__iexact=last_name)
        else:
            query = query.filter(
                models.Q(last_name="") | models.Q(last_name__isnull=True)
            )

        # НОВОЕ: Если дата рождения УКАЗАНА, исключаем пациентов с другой датой рождения
        if date_of_birth:
            query = query.filter(
                models.Q(date_of_birth=date_of_birth)
                | models.Q(date_of_birth__isnull=True)
            )

        existing_patient = query.first()

        if existing_patient:
            # Проверяем, совпадает ли дата рождения
            if existing_patient.date_of_birth and date_of_birth:
                if existing_patient.date_of_birth != date_of_birth:
                    # РАЗНЫЕ пациенты - создаем нового
                    patient = Patient.objects.create(**cleaned_data)
                    print(
                        f"DEBUG: Создан новый пациент (разные даты рождения): {patient.id}"
                    )
                    return patient, True

            # Обновляем существующего пациента
            update_fields = []

            # Обновляем дату рождения, если она есть в новых данных
            if date_of_birth and not existing_patient.date_of_birth:
                existing_patient.date_of_birth = date_of_birth
                update_fields.append("date_of_birth")

            # Обновляем телефон, если он есть в новых данных и пустой у пациента
            phone = cleaned_data.get("phone_number")
            if phone and (
                not existing_patient.phone_number or existing_patient.phone_number == ""
            ):
                existing_patient.phone_number = phone
                update_fields.append("phone_number")

            # Обновляем номер карты, если он есть в новых данных и пустой у пациента
            card_number = cleaned_data.get("card_number")
            if card_number and not existing_patient.card_number:
                existing_patient.card_number = card_number
                update_fields.append("card_number")

            if update_fields:
                existing_patient.save(update_fields=update_fields)
                print(f"DEBUG: Обновлен пациент {existing_patient.id}: {update_fields}")

            return existing_patient, False

        # Создание нового пациента
        patient = Patient.objects.create(**cleaned_data)
        print(f"DEBUG: Создан новый пациент {patient.id}")
        return patient, True

    @staticmethod
    def clean_patient_data(patient_data: Dict[str, Any]) -> Dict[str, Any]:
        """Очистка данных пациента для новой модели"""
        cleaned_data = patient_data.copy()

        # Обработка телефона (поддержка PhoneNumberField)
        phone = cleaned_data.get("phone_number")
        if phone:
            if isinstance(phone, str):
                # Очистка строки телефона
                phone_clean = "".join(c for c in phone if c.isdigit() or c == "+")
                if phone_clean and not phone_clean.startswith("+"):
                    if phone_clean.startswith("8"):
                        phone_clean = "+7" + phone_clean[1:]
                    elif phone_clean.startswith("7"):
                        phone_clean = "+" + phone_clean
                    else:
                        phone_clean = "+7" + phone_clean
                cleaned_data["phone_number"] = phone_clean

        # Конвертация пустых строк в None для числовых полей
        numeric_fields = ["card_number", "card_number_IP", "card_number_OMS"]
        for field in numeric_fields:
            if field in cleaned_data and cleaned_data[field] == "":
                cleaned_data[field] = None

        # Конвертация пустых строк в пустые строки (не None) для текстовых полей
        text_fields = [
            "last_name",
            "area",
            "locality",
            "city",
            "district",
            "street",
            "home",
            "building",
            "apartment",
            "passport_series",
            "passport_number",
            "who_issued_the_passport",
            "polis_oms",
            "snils",
            "insurance_company",
        ]

        for field in text_fields:
            if field in cleaned_data:
                if cleaned_data[field] is None:
                    cleaned_data[field] = ""
                else:
                    cleaned_data[field] = str(cleaned_data[field]).strip()

        return cleaned_data


class CardNumberService:
    """Сервис для работы с номерами карт пациентов"""

    # Добавляем минимальные стартовые номера для каждого типа карт
    MIN_START_NUMBERS = {
        "regular": 1,  # обычные карты - НЕ ИСПОЛЬЗУЕТСЯ, т.к. обычные карты по логике max+1
        "ip": 169,  # карты ИП - начинаем с 169 и ищем свободный
        "oms": 1593,  # карты ОМС - начинаем с 1593 и ищем свободный
    }

    @staticmethod
    def get_max_card_number(card_type="regular"):
        """Получить максимальный номер карты указанного типа"""
        if card_type == "ip":
            # Для ИП - целое число
            max_number = Patient.objects.aggregate(
                max_card_number=Max("card_number_IP")
            )["max_card_number"]
        elif card_type == "oms":
            # Для ОМС - строки, находим максимальное ЧИСЛО до слеша или полностью
            try:
                # Получаем все номера ОМС
                oms_numbers = (
                    Patient.objects.exclude(card_number_OMS__isnull=True)
                    .exclude(card_number_OMS="")
                    .values_list("card_number_OMS", flat=True)
                )

                max_numeric = 0
                for num in oms_numbers:
                    if num:
                        try:
                            # Если есть слеш, берем часть до него
                            if "/" in str(num):
                                num_part = str(num).split("/")[0]
                            else:
                                num_part = str(num)

                            num_int = int(num_part)
                            if num_int > max_numeric:
                                max_numeric = num_int
                        except (ValueError, AttributeError):
                            continue

                return max_numeric
            except Exception:
                return 0
        else:
            # Обычная карта - целое число
            max_number = Patient.objects.aggregate(max_card_number=Max("card_number"))[
                "max_card_number"
            ]

        return max_number or 0

    @staticmethod
    def get_next_card_number(card_type="regular"):
        """Получить следующий доступный номер карты указанного типа"""

        # ОБЫЧНЫЕ КАРТЫ (платные) - логика "максимальный + 1"
        if card_type == "regular":
            max_number = CardNumberService.get_max_card_number("regular")
            # Если нет ни одного номера, начинаем с 1
            if max_number == 0:
                return 1
            return max_number + 1

        # КАРТЫ ИП и ОМС - логика "начать с минимального и найти первый свободный"
        else:
            # Получаем минимальный стартовый номер для этого типа карты
            min_start = CardNumberService.MIN_START_NUMBERS.get(card_type, 1)

            # Получаем все существующие номера для этого типа карты
            existing_numbers = set()

            if card_type == "ip":
                existing_numbers = set(
                    Patient.objects.exclude(card_number_IP__isnull=True).values_list(
                        "card_number_IP", flat=True
                    )
                )
            elif card_type == "oms":
                # Для ОМС извлекаем числовую часть до слеша
                oms_numbers = Patient.objects.exclude(
                    card_number_OMS__isnull=True
                ).exclude(card_number_OMS="")
                for num in oms_numbers.values_list("card_number_OMS", flat=True):
                    try:
                        if num:
                            if "/" in str(num):
                                num_part = str(num).split("/")[0]
                            else:
                                num_part = str(num)
                            existing_numbers.add(int(num_part))
                    except (ValueError, AttributeError):
                        continue

            # Ищем первый свободный номер, начиная с min_start
            current_number = min_start
            while current_number in existing_numbers:
                current_number += 1

            if card_type == "oms":
                return str(current_number)

            return current_number

    @staticmethod
    def get_free_regular_card_numbers_in_range(
        start_number: int, end_number: int
    ) -> List[int]:
        """Получить список свободных обычных номеров карт в диапазоне"""
        if start_number > end_number:
            raise ValidationError(
                "Начальный номер диапазона не может быть больше конечного"
            )

        used_numbers = set(
            Patient.objects.filter(card_number__isnull=False)
            .filter(card_number__gte=start_number, card_number__lte=end_number)
            .values_list("card_number", flat=True)
        )

        return [
            number
            for number in range(start_number, end_number + 1)
            if number not in used_numbers
        ]


TAX_INFO_START_YEAR = 2026


def get_tax_info_years() -> list[int]:
    """Список доступных годов для расчета суммы для налоговой."""
    current_year = timezone.now().year
    return list(range(TAX_INFO_START_YEAR, current_year + 1))


def get_taxable_appointment_amount(appointment) -> Decimal:
    """Возвращает сумму записи по приоритету полей для налогового расчета."""
    if appointment.total_with_blood_tests is not None:
        return appointment.total_with_blood_tests
    if appointment.price_at_appointment is not None:
        return appointment.price_at_appointment
    if appointment.service and appointment.service.price is not None:
        return appointment.service.price
    return Decimal("0.00")


def _is_excluded_from_tax_info(appointment) -> bool:
    service = getattr(appointment, "service", None)
    service_name = (service.name if service else "").strip().lower()
    return service_name == "плантография"


def get_patient_tax_info_for_year(patient: Patient, year: int) -> dict[str, object]:
    """Возвращает сумму и список учтенных записей пациента за год."""
    from appointments.models import Appointment

    appointments = (
        Appointment.objects.filter(
            patient=patient,
            status=Appointment.AppointmentStatus.COMPLETED,
            insurance_type=Appointment.InsuranceType.PAID,
            time_slot__date__year=year,
        )
        .select_related("time_slot__doctor", "time_slot__cabinet", "service")
        .order_by("time_slot__date", "time_slot__start_time", "pk")
    )

    included_appointments = []
    last_kept_specialist_consultation = {}

    for appointment in appointments:
        if _is_excluded_from_tax_info(appointment):
            continue

        if _is_linked_procedural_appointment(appointment):
            continue

        amount = get_taxable_appointment_amount(appointment)

        if _is_specialist_consultation(appointment):
            signature = _get_specialist_consultation_signature(appointment, amount)
            previous_appointment = last_kept_specialist_consultation.get(signature)

            if previous_appointment and _are_neighboring_slots(
                previous_appointment, appointment
            ):
                continue

            last_kept_specialist_consultation[signature] = appointment

        appointment.tax_amount = amount
        appointment.tax_bucket = (
            "ИП"
            if _is_specialist_doctor_appointment(appointment)
            else "Клиника"
        )
        included_appointments.append(appointment)

    total_amount = sum(
        (appointment.tax_amount for appointment in included_appointments),
        Decimal("0.00"),
    )
    ip_total_amount = sum(
        (
            appointment.tax_amount
            for appointment in included_appointments
            if _is_specialist_doctor_appointment(appointment)
        ),
        Decimal("0.00"),
    )
    clinic_total_amount = sum(
        (
            appointment.tax_amount
            for appointment in included_appointments
            if not _is_specialist_doctor_appointment(appointment)
        ),
        Decimal("0.00"),
    )

    return {
        "total": total_amount,
        "ip_total": ip_total_amount,
        "clinic_total": clinic_total_amount,
        "appointments": included_appointments,
    }


def calculate_patient_paid_total_for_year(patient: Patient, year: int) -> Decimal:
    """Считает сумму оплаченных завершенных записей пациента за год."""
    return get_patient_tax_info_for_year(patient, year)["total"]


def _is_linked_procedural_appointment(appointment) -> bool:
    cabinet = getattr(getattr(appointment, "time_slot", None), "cabinet", None)
    return bool(
        appointment.previous_appointment_id
        and cabinet
        and cabinet.number == 6
    )


def _is_specialist_consultation(appointment) -> bool:
    doctor = getattr(getattr(appointment, "time_slot", None), "doctor", None)
    service = getattr(appointment, "service", None)

    if not doctor or not service:
        return False

    service_name = (service.name or "").strip().lower()
    if "консультац" not in service_name:
        return False

    return _is_specialist_doctor_appointment(appointment)


def _is_specialist_doctor_appointment(appointment) -> bool:
    doctor = getattr(getattr(appointment, "time_slot", None), "doctor", None)

    if not doctor:
        return False

    return (
        (doctor.surname or "").strip().lower() == "епифанова"
        and (doctor.first_name or "").strip().lower().startswith("о")
        and (doctor.last_name or "").strip().lower().startswith("е")
    )


def _get_specialist_consultation_signature(
    appointment, amount: Decimal
) -> tuple[int, int, object, int | None, Decimal]:
    return (
        appointment.patient_id,
        appointment.doctor.id,
        appointment.date,
        appointment.service_id,
        amount,
    )


def _are_neighboring_slots(left, right) -> bool:
    if not left.time_slot or not right.time_slot:
        return False

    return left.date == right.date and left.end_time == right.start_time
