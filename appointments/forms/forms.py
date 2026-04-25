import json
import logging
from datetime import date as date_cls

from django import forms
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from appointments.forms.base import AppointmentChainBaseForm
from appointments.forms.procedural_base import ProceduralAppointmentBaseForm
from appointments.models import Appointment, AppointmentBloodTest, AppointmentChain
from appointments.services import (
    AppointmentService,
    ConsecutiveAppointmentService,
    ProceduralAppointmentService,
)
from appointments.utils_for_caches import (
    get_cached_doctor_services,
    get_procedural_cabinet,
)
from patients.services import PatientService
from timetable.models import BloodTest, Doctor, MedicalService, TimeSlot
from timetable.services import get_service_price_on_date


logger = logging.getLogger(__name__)


class AppointmentForm(AppointmentChainBaseForm, forms.ModelForm):
    """Форма создания записи с возможностью изменения времени"""

    class Meta:
        model = Appointment
        fields = [
            "service",
            "insurance_type",
            "needs_reschedule",
            "comment",
            "selected_blood_tests_input",
            "total_sum",
        ]

    allow_time_change = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.HiddenInput(attrs={"id": "id_allow_time_change"}),
        label="Разрешить изменение времени",
    )
    new_time_slot_id = forms.IntegerField(
        required=False,
        widget=forms.HiddenInput(attrs={"id": "id_new_time_slot_id"}),
        label="Новый временной слот",
    )
    new_appointment_date = forms.DateField(
        required=False,
        widget=forms.HiddenInput(attrs={"id": "id_new_appointment_date"}),
        label="Новая дата приема",
    )
    selected_blood_tests_input = forms.CharField(
        required=False,
        widget=forms.HiddenInput(attrs={"id": "id_selected_blood_tests"}),
        label="Выбранные анализы крови",
    )

    total_sum = forms.DecimalField(
        required=False,
        max_digits=10,
        decimal_places=2,
        widget=forms.HiddenInput(attrs={"id": "id_total_sum"}),
        label="Итоговая сумма",
    )

    def __init__(self, *args, **kwargs):
        self.time_slot = kwargs.pop("time_slot", None)
        self.doctor = kwargs.pop("doctor", None)

        super().__init__(*args, **kwargs, time_slot=self.time_slot, doctor=self.doctor)
        self.fields["insurance_type"].initial = "paid"

        if self.time_slot:
            self.fields["new_time_slot_id"].initial = self.time_slot.id
            self.fields["new_appointment_date"].initial = self.time_slot.date

        doctor_to_use = self.doctor or (
            self.time_slot.doctor if self.time_slot else None
        )

        AppointmentService.initialize_service_queryset(self, doctor_to_use)

        logger.info(
            "Инициализация AppointmentForm: doctor_id=%s time_slot_id=%s date=%s instance_id=%s",
            getattr(doctor_to_use, "id", None),
            getattr(self.time_slot, "id", None),
            getattr(self.time_slot, "date", None),
            getattr(getattr(self, "instance", None), "id", None),
        )

    def clean(self):
        cleaned_data = super().clean()

        allow_time_change = cleaned_data.get("allow_time_change")
        new_time_slot_id = cleaned_data.get("new_time_slot_id")
        target_time_slot = self.time_slot

        logger.info(
            "AppointmentForm.clean: allow_time_change=%s new_time_slot_id=%s service_id=%s insurance_type=%s needs_procedural=%s",
            allow_time_change,
            new_time_slot_id,
            getattr(cleaned_data.get("service"), "id", None),
            cleaned_data.get("insurance_type"),
            cleaned_data.get("needs_procedural"),
        )

        if allow_time_change and new_time_slot_id:
            target_time_slot = None
            try:
                new_time_slot = TimeSlot.objects.get(id=new_time_slot_id)
                target_time_slot = new_time_slot

                if not new_time_slot.is_available():
                    logger.warning(
                        "AppointmentForm.clean: выбранный слот занят new_time_slot_id=%s doctor_id=%s date=%s",
                        new_time_slot_id,
                        getattr(new_time_slot.doctor, "id", None),
                        getattr(new_time_slot, "date", None),
                    )
                    raise forms.ValidationError(
                        "Выбранный временной слот уже занят. Пожалуйста, выберите другой слот."
                    )

                if self.doctor and new_time_slot.doctor != self.doctor:
                    logger.warning(
                        "AppointmentForm.clean: слот принадлежит другому врачу new_time_slot_id=%s expected_doctor_id=%s actual_doctor_id=%s",
                        new_time_slot_id,
                        getattr(self.doctor, "id", None),
                        getattr(new_time_slot.doctor, "id", None),
                    )
                    raise forms.ValidationError(
                        "Выбранный слот не принадлежит текущему врачу."
                    )

                cleaned_data["new_time_slot"] = new_time_slot

                logger.info(
                    "AppointmentForm.clean: новый слот принят new_time_slot_id=%s date=%s start=%s end=%s",
                    new_time_slot.id,
                    new_time_slot.date,
                    new_time_slot.start_time,
                    new_time_slot.end_time,
                )

            except TimeSlot.DoesNotExist:
                logger.warning(
                    "AppointmentForm.clean: новый слот не существует new_time_slot_id=%s",
                    new_time_slot_id,
                )
                raise forms.ValidationError("Выбранный временной слот не существует")

        if target_time_slot and not target_time_slot.is_available():
            logger.warning(
                "AppointmentForm.clean: исходный слот уже занят time_slot_id=%s doctor_id=%s date=%s",
                getattr(target_time_slot, "id", None),
                getattr(getattr(target_time_slot, "doctor", None), "id", None),
                getattr(target_time_slot, "date", None),
            )
            raise forms.ValidationError(
                "Выбранный временной слот уже занят. Пожалуйста, обновите страницу и выберите другое время."
            )

        return cleaned_data

    def _lock_target_time_slot(self, appointment):
        """Блокирует слот и повторно проверяет его доступность перед сохранением."""
        target_slot = TimeSlot.objects.select_for_update().get(pk=appointment.time_slot_id)
        conflicting_appointments = Appointment.objects.select_for_update().filter(
            time_slot=target_slot
        )

        if appointment.pk:
            conflicting_appointments = conflicting_appointments.exclude(pk=appointment.pk)

        if conflicting_appointments.exists():
            logger.warning(
                "AppointmentForm._lock_target_time_slot: слот уже занят time_slot_id=%s appointment_id=%s",
                target_slot.id,
                conflicting_appointments.first().id,
            )
            raise forms.ValidationError(
                "Невозможно создать запись: выбранное время уже занято. Пожалуйста, обновите страницу и попробуйте снова."
            )

        return target_slot

    def _validate_consecutive_for_pishchelev(
        self, main_appointment, appointment_chain_type
    ):
        """Дополнительная валидация для последовательных записей Пищелева"""
        if not hasattr(main_appointment, "doctor") or not main_appointment.doctor:
            logger.info(
                "AppointmentForm._validate_consecutive_for_pishchelev: врач отсутствует appointment_id=%s",
                getattr(main_appointment, "id", None),
            )
            return

        is_pishchelev = "пищелев" in main_appointment.doctor.surname.lower()
        if not is_pishchelev:
            logger.info(
                "AppointmentForm._validate_consecutive_for_pishchelev: врач не Пищелев appointment_id=%s doctor=%s",
                getattr(main_appointment, "id", None),
                getattr(main_appointment.doctor, "surname", None),
            )
            return

        if appointment_chain_type == "two_slots":
            next_slot = main_appointment.time_slot.get_next_consecutive_slot()
            logger.info(
                "AppointmentForm._validate_consecutive_for_pishchelev: проверка следующего слота appointment_id=%s next_slot_id=%s",
                getattr(main_appointment, "id", None),
                getattr(next_slot, "id", None),
            )
            if not next_slot:
                return

    @transaction.atomic
    def save(self, commit=True):
        """Сохраняет запись с транзакционной безопасность."""
        if not commit:
            logger.info("AppointmentForm.save: commit=False")
            return super(AppointmentChainBaseForm, self).save(commit=False)

        try:
            with transaction.atomic():
                patient_data = self.get_patient_data()
                logger.info(
                    "AppointmentForm.save: получение/создание пациента full_name=%s birth_date=%s",
                    (
                        patient_data.get("full_name")
                        if isinstance(patient_data, dict)
                        else None
                    ),
                    (
                        patient_data.get("date_of_birth")
                        if isinstance(patient_data, dict)
                        else None
                    ),
                )
                patient, created = PatientService.get_or_create_patient(patient_data)

                appointment = super(AppointmentChainBaseForm, self).save(commit=False)
                appointment.patient = patient

                allow_time_change = self.cleaned_data.get("allow_time_change", False)
                new_time_slot = self.cleaned_data.get("new_time_slot")

                if allow_time_change and new_time_slot:
                    appointment.time_slot = new_time_slot
                    logger.info(
                        "AppointmentForm.save: используется новый слот appointment_temp_id=%s new_time_slot_id=%s",
                        getattr(appointment, "id", None),
                        new_time_slot.id,
                    )
                else:
                    appointment.time_slot = self.time_slot
                    logger.info(
                        "AppointmentForm.save: используется исходный слот appointment_temp_id=%s time_slot_id=%s",
                        getattr(appointment, "id", None),
                        getattr(self.time_slot, "id", None),
                    )

                appointment.time_slot = self._lock_target_time_slot(appointment)

                appointment.is_chain_main = True

                appointment_chain_type = self.cleaned_data.get("appointment_chain_type")
                if appointment_chain_type == "two_slots":
                    appointment.chain_type = Appointment.ChainType.SAME_DOCTOR
                    appointment.occupies_two_slots = True
                elif appointment_chain_type in ["another_doctor", "multiple"]:
                    appointment.chain_type = Appointment.ChainType.MULTIPLE_DOCTORS
                else:
                    appointment.chain_type = Appointment.ChainType.SINGLE

                logger.info(
                    "AppointmentForm.save: определён тип цепочки appointment_chain_type=%s chain_type=%s occupies_two_slots=%s patient_created=%s",
                    appointment_chain_type,
                    appointment.chain_type,
                    appointment.occupies_two_slots,
                    created,
                )

                self._set_appointment_price(appointment)

                total_sum = self.cleaned_data.get("total_sum")
                if total_sum:
                    appointment.total_with_blood_tests = total_sum
                    logger.info(
                        "AppointmentForm.save: установлена total_sum=%s",
                        total_sum,
                    )

                appointment.save()

                logger.info(
                    "AppointmentForm.save: основная запись сохранена appointment_id=%s patient_id=%s doctor_id=%s time_slot_id=%s service_id=%s",
                    appointment.id,
                    getattr(patient, "id", None),
                    getattr(appointment.doctor, "id", None),
                    getattr(appointment.time_slot, "id", None),
                    getattr(appointment.service, "id", None),
                )

                selected_blood_tests_input = self.cleaned_data.get(
                    "selected_blood_tests_input", ""
                )
                selected_test_ids = []

                if selected_blood_tests_input and selected_blood_tests_input.strip():
                    try:
                        test_ids = [
                            int(id.strip())
                            for id in selected_blood_tests_input.split(",")
                            if id.strip() and id.strip().isdigit()
                        ]
                        selected_test_ids = test_ids

                        logger.info(
                            "AppointmentForm.save: добавление анализов appointment_id=%s tests_count=%s test_ids=%s",
                            appointment.id,
                            len(selected_test_ids),
                            selected_test_ids,
                        )

                        for test_id in selected_test_ids:
                            AppointmentBloodTest.objects.create(
                                appointment=appointment, blood_test_id=test_id
                            )

                        if selected_test_ids and appointment.comment:
                            tests = BloodTest.objects.filter(id__in=selected_test_ids)
                            if tests.exists():
                                tests_list = ", ".join([test.name for test in tests])
                                if "Анализы:" not in appointment.comment:
                                    appointment.comment = (
                                        f"{appointment.comment}\nАнализы: {tests_list}"
                                    )
                                    appointment.save()
                                    logger.info(
                                        "AppointmentForm.save: комментарий дополнен анализами appointment_id=%s",
                                        appointment.id,
                                    )

                    except (ValueError, TypeError) as e:
                        logger.warning(
                            "AppointmentForm.save: ошибка разбора анализов appointment_id=%s raw=%s error=%s",
                            appointment.id,
                            selected_blood_tests_input,
                            str(e),
                        )

                if appointment_chain_type in ["another_doctor", "multiple"]:
                    if not appointment.comment:
                        appointment.comment = ""

                    chain_comment = "Основная запись в цепочке"
                    if appointment.comment and chain_comment not in appointment.comment:
                        appointment.comment = f"{appointment.comment}\n{chain_comment}"
                    appointment.save()

                    logger.info(
                        "AppointmentForm.save: основная запись помечена как цепочка appointment_id=%s chain_type=%s",
                        appointment.id,
                        appointment_chain_type,
                    )

                if appointment_chain_type == "two_slots":
                    logger.info(
                        "AppointmentForm.save: проверка последовательной записи appointment_id=%s",
                        appointment.id,
                    )
                    self._validate_consecutive_for_pishchelev(
                        appointment, appointment_chain_type
                    )

                if self.cleaned_data.get("needs_procedural"):
                    logger.info(
                        "AppointmentForm.save: требуется процедурная запись appointment_id=%s",
                        appointment.id,
                    )
                    if not ProceduralAppointmentService.can_create_procedural_appointment(
                        appointment
                    ):
                        logger.warning(
                            "AppointmentForm.save: процедурная запись не может быть создана appointment_id=%s",
                            appointment.id,
                        )
                        raise forms.ValidationError(
                            "Невозможно создать запись: выбранное время в процедурном кабинете уже занято. "
                            "Пожалуйста, выберите другое время."
                        )

                if self.cleaned_data.get("needs_procedural"):
                    procedural_appointment = (
                        ProceduralAppointmentService.create_procedural_appointment(
                            appointment
                        )
                    )
                    if procedural_appointment:
                        if not procedural_appointment.price_at_appointment:
                            procedural_appointment.price_at_appointment = (
                                get_service_price_on_date(
                                    procedural_appointment.service,
                                    procedural_appointment.time_slot.date,
                                )
                            )
                        procedural_appointment.total_with_blood_tests = (
                            procedural_appointment.price_at_appointment
                        )
                        procedural_appointment.save()

                        logger.info(
                            "AppointmentForm.save: процедурная запись создана/обновлена main_appointment_id=%s procedural_appointment_id=%s procedural_slot_id=%s",
                            appointment.id,
                            procedural_appointment.id,
                            getattr(procedural_appointment.time_slot, "id", None),
                        )

                if appointment_chain_type == "two_slots":
                    logger.info(
                        "AppointmentForm.save: создание последовательной записи appointment_id=%s",
                        appointment.id,
                    )
                    self._handle_consecutive_appointments(
                        appointment, appointment_chain_type
                    )

                if appointment_chain_type in ["another_doctor", "multiple"]:
                    logger.info(
                        "AppointmentForm.save: обработка дополнительных записей appointment_id=%s",
                        appointment.id,
                    )
                    self._handle_additional_appointments(appointment)

                logger.info(
                    "AppointmentForm.save: успешно завершено appointment_id=%s",
                    appointment.id,
                )
                return appointment

        except forms.ValidationError:
            logger.warning("AppointmentForm.save: ValidationError", exc_info=True)
            raise
        except IntegrityError as e:
            logger.exception(
                "AppointmentForm.save: IntegrityError error=%s",
                str(e),
            )
            if "unique_doctor_time_slot" in str(e):
                raise forms.ValidationError(
                    "Невозможно создать запись: выбранное время уже занято другим пациентом. "
                    "Пожалуйста, обновите страницу и выберите другое время."
                )
            raise

    @staticmethod
    def _set_appointment_price(appointment, service=None):
        """Устанавливает цену услуги для записи на дату визита (time_slot.date)."""
        visit_date = appointment.time_slot.date if appointment.time_slot else None
        svc = service or appointment.service

        if svc and visit_date:
            appointment.price_at_appointment = get_service_price_on_date(
                svc, visit_date
            )
        elif svc:
            appointment.price_at_appointment = svc.price

        if not appointment.total_with_blood_tests:
            appointment.total_with_blood_tests = appointment.price_at_appointment

    @staticmethod
    def _handle_consecutive_appointments(main_appointment, appointment_chain_type):
        """Обработка последовательных записей к тому же врачу (только для two_slots)"""
        if appointment_chain_type == "two_slots":
            try:
                logger.info(
                    "AppointmentForm._handle_consecutive_appointments: main_appointment_id=%s",
                    main_appointment.id,
                )
                ConsecutiveAppointmentService.create_consecutive_appointment(
                    main_appointment=main_appointment,
                    appointment_chain_type=appointment_chain_type,
                    additional_service=None,
                )
            except ValidationError as e:
                logger.warning(
                    "AppointmentForm._handle_consecutive_appointments: ошибка main_appointment_id=%s error=%s",
                    getattr(main_appointment, "id", None),
                    str(e),
                )
                raise forms.ValidationError(str(e))

    def _handle_additional_appointments(self, main_appointment):
        """Обработка дополнительных записей к другим врачам"""
        appointment_chain_type = self.cleaned_data.get("appointment_chain_type")

        if appointment_chain_type in ["another_doctor", "multiple"]:
            additional_data = self.cleaned_data.get("additional_appointments_data")
            procedural_data = self.cleaned_data.get("procedural_appointments_data")

            logger.info(
                "AppointmentForm._handle_additional_appointments: main_appointment_id=%s chain_type=%s has_additional_data=%s has_procedural_data=%s",
                main_appointment.id,
                appointment_chain_type,
                bool(additional_data),
                bool(procedural_data),
            )

            if additional_data:
                try:
                    appointments_list = json.loads(additional_data)
                    procedural_list = (
                        json.loads(procedural_data) if procedural_data else []
                    )
                    additional_doctors = []

                    logger.info(
                        "AppointmentForm._handle_additional_appointments: parsed additional_count=%s procedural_count=%s",
                        len(appointments_list),
                        len(procedural_list),
                    )

                    for i, appointment_data in enumerate(appointments_list, start=1):
                        if "insurance_type" not in appointment_data:
                            appointment_data["insurance_type"] = "paid"

                        additional_appointment = self._create_additional_appointment(
                            main_appointment, appointment_data, i
                        )

                        logger.info(
                            "AppointmentForm._handle_additional_appointments: создана дополнительная запись main_appointment_id=%s additional_appointment_id=%s order=%s",
                            main_appointment.id,
                            additional_appointment.id,
                            i,
                        )

                        if additional_appointment.doctor:
                            additional_doctors.append(
                                additional_appointment.doctor.surname
                            )

                        procedural_info = None
                        if procedural_list:
                            for item in procedural_list:
                                if str(item.get("index")) == str(
                                    appointment_data.get("index")
                                ):
                                    procedural_info = item
                                    break

                        if procedural_info and procedural_info.get("needs_procedural"):
                            logger.info(
                                "AppointmentForm._handle_additional_appointments: создаётся процедурная запись для дополнительной additional_appointment_id=%s",
                                additional_appointment.id,
                            )
                            ProceduralAppointmentService.create_procedural_for_appointment(
                                additional_appointment,
                                main_appointment=additional_appointment,
                            )

                    if additional_doctors:
                        unique_doctors = []
                        for doctor in additional_doctors:
                            if doctor not in unique_doctors:
                                unique_doctors.append(doctor)

                        if len(unique_doctors) == 1:
                            chain_comment = f"Доп. запись к врачу {unique_doctors[0]}"
                        else:
                            doctors_str = ", ".join(unique_doctors)
                            chain_comment = f"Доп. записи к врачам: {doctors_str}"

                        current_comment = main_appointment.comment or ""

                        lines = current_comment.split("\n")
                        filtered_lines = []
                        for line in lines:
                            if not any(
                                phrase in line
                                for phrase in [
                                    "Доп. запись к врачу",
                                    "Доп. записи к врачам:",
                                    "Основная запись в цепочке",
                                ]
                            ):
                                filtered_lines.append(line)

                        cleaned_comment = "\n".join(filtered_lines).strip()

                        if cleaned_comment:
                            main_appointment.comment = (
                                f"{cleaned_comment}\n{chain_comment}"
                            )
                        else:
                            main_appointment.comment = chain_comment

                        main_appointment.save()

                        logger.info(
                            "AppointmentForm._handle_additional_appointments: обновлён комментарий основной записи main_appointment_id=%s comment=%s",
                            main_appointment.id,
                            main_appointment.comment,
                        )

                except (json.JSONDecodeError, KeyError) as e:
                    logger.warning(
                        "AppointmentForm._handle_additional_appointments: ошибка обработки JSON main_appointment_id=%s error=%s",
                        getattr(main_appointment, "id", None),
                        str(e),
                    )
                    raise forms.ValidationError(
                        f"Ошибка обработки данных дополнительных записей: {str(e)}"
                    )

    def _create_additional_appointment(self, main_appointment, appointment_data, order):
        """Создание одной дополнительной записи с проверкой времени"""
        try:
            doctor_id = appointment_data.get("doctor_id")
            service_id = appointment_data.get("service_id")
            time_slot_id = appointment_data.get("time_slot_id")
            comment = appointment_data.get("comment", "")
            insurance_type = appointment_data.get("insurance_type", "paid")

            logger.info(
                "AppointmentForm._create_additional_appointment: main_appointment_id=%s order=%s doctor_id=%s service_id=%s time_slot_id=%s insurance_type=%s",
                getattr(main_appointment, "id", None),
                order,
                doctor_id,
                service_id,
                time_slot_id,
                insurance_type,
            )

            if not all([doctor_id, service_id, time_slot_id]):
                logger.warning(
                    "AppointmentForm._create_additional_appointment: не все обязательные поля заполнены order=%s",
                    order,
                )
                raise ValueError("Не все обязательные поля заполнены")

            doctor = Doctor.objects.get(id=doctor_id)
            service = MedicalService.objects.get(id=service_id)
            time_slot = TimeSlot.objects.get(id=time_slot_id)

            if "пищелев" in doctor.surname.lower():
                from django.core.exceptions import ValidationError
                from appointments.utils import validate_pishchelev_restrictions

                try:
                    validate_pishchelev_restrictions(doctor, service, time_slot)
                except ValidationError as e:
                    logger.warning(
                        "AppointmentForm._create_additional_appointment: ограничение Пищелева order=%s doctor_id=%s error=%s",
                        order,
                        doctor_id,
                        str(e),
                    )
                    raise forms.ValidationError(
                        f"Ошибка в дополнительной записи #{order} (к врачу {doctor.surname}): {str(e)}"
                    )

            if time_slot.date == main_appointment.date:
                main_start = main_appointment.start_time
                main_end = main_appointment.end_time
                add_start = time_slot.start_time
                add_end = time_slot.end_time

                def time_to_minutes(t):
                    return t.hour * 60 + t.minute + t.second / 60

                main_start_minutes = time_to_minutes(main_start)
                main_end_minutes = time_to_minutes(main_end)
                add_start_minutes = time_to_minutes(add_start)
                add_end_minutes = time_to_minutes(add_end)

                is_overlapping = (
                    add_start_minutes < main_end_minutes
                    and add_end_minutes > main_start_minutes
                )

                if is_overlapping:
                    logger.warning(
                        "AppointmentForm._create_additional_appointment: пересечение времени main_appointment_id=%s order=%s add_slot_id=%s",
                        getattr(main_appointment, "id", None),
                        order,
                        time_slot_id,
                    )
                    raise forms.ValidationError(
                        f"Ошибка: Время дополнительной записи пересекается с основной записью.\n"
                        f"Основная запись: {main_appointment.date.strftime('%d.%m.%Y')} "
                        f"{main_start.strftime('%H:%M')}-{main_end.strftime('%H:%M')}\n"
                        f"Дополнительная запись: {time_slot.date.strftime('%d.%m.%Y')} "
                        f"{add_start.strftime('%H:%M')}-{add_end.strftime('%H:%M')}\n\n"
                        f"Выберите другое время для дополнительной записи."
                    )

            if not time_slot.is_available():
                logger.warning(
                    "AppointmentForm._create_additional_appointment: слот занят order=%s time_slot_id=%s doctor_id=%s",
                    order,
                    time_slot_id,
                    doctor_id,
                )
                raise forms.ValidationError(
                    f"Слот {time_slot.start_time} у врача {doctor.surname} уже занят"
                )

            main_doctor_surname = main_appointment.doctor.surname
            additional_comment = comment or f"Доп. запись к врачу {main_doctor_surname}"

            additional_appointment = Appointment.objects.create(
                time_slot=time_slot,
                patient=main_appointment.patient,
                service=service,
                insurance_type=insurance_type,
                status=main_appointment.status,
                comment=additional_comment,
                chain_type=Appointment.ChainType.MULTIPLE_DOCTORS,
                is_chain_main=False,
            )

            self._set_appointment_price(additional_appointment, service)

            AppointmentChain.objects.create(
                main_appointment=main_appointment,
                related_appointment=additional_appointment,
                chain_type=AppointmentChain.ChainType.ANOTHER_DOCTOR,
                order=order,
            )

            logger.info(
                "AppointmentForm._create_additional_appointment: успешно создана additional_appointment_id=%s main_appointment_id=%s order=%s",
                additional_appointment.id,
                main_appointment.id,
                order,
            )

            return additional_appointment

        except (
            Doctor.DoesNotExist,
            MedicalService.DoesNotExist,
            TimeSlot.DoesNotExist,
        ) as e:
            logger.warning(
                "AppointmentForm._create_additional_appointment: объект не найден order=%s error=%s",
                order,
                str(e),
            )
            raise forms.ValidationError(
                f"Ошибка создания дополнительной записи: {str(e)}"
            )


class AppointmentSimpleEditForm(forms.ModelForm):
    """Упрощенная форма редактирования записи с подробным логированием"""

    allow_time_change = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.HiddenInput(attrs={"id": "id_allow_time_change"}),
        label="Разрешить изменение времени",
    )
    new_time_slot_id = forms.IntegerField(
        required=False,
        widget=forms.HiddenInput(attrs={"id": "id_new_time_slot_id"}),
        label="ID нового временного слота",
    )
    new_appointment_date = forms.DateField(
        required=False,
        widget=forms.HiddenInput(attrs={"id": "id_new_appointment_date"}),
        label="Новая дата приема",
    )
    needs_procedural = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
        label="Занять окошко в процедурном кабинете",
        help_text="Автоматически займет такое же время в процедурном кабинете",
    )

    class Meta:
        model = Appointment
        fields = [
            "service",
            "insurance_type",
            "needs_reschedule",
            "comment",
        ]
        widgets = {
            "service": forms.Select(attrs={"class": "form-select"}),
            "insurance_type": forms.Select(attrs={"class": "form-select"}),
            "needs_reschedule": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
            "comment": forms.Textarea(attrs={"rows": 3, "class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        self.appointment = kwargs.get("instance")
        super().__init__(*args, **kwargs)

        logger.info(
            "Инициализация AppointmentSimpleEditForm: appointment_id=%s doctor_id=%s service_id=%s time_slot_id=%s",
            getattr(self.appointment, "id", None),
            getattr(getattr(self.appointment, "doctor", None), "id", None),
            getattr(getattr(self.appointment, "service", None), "id", None),
            getattr(getattr(self.appointment, "time_slot", None), "id", None),
        )

        if self.appointment:
            if self.appointment.doctor:
                self.fields["service"].queryset = get_cached_doctor_services(
                    self.appointment.doctor
                )
                self.fields["service"].widget.attrs["data-doctor-id"] = str(
                    self.appointment.doctor.id
                )

                visit_date = None
                if getattr(self.appointment, "time_slot", None):
                    visit_date = self.appointment.time_slot.date

                def _service_label(service_obj):
                    if visit_date:
                        price = get_service_price_on_date(service_obj, visit_date)
                    else:
                        price = service_obj.price
                    return f"{service_obj.name} - {price} руб."

                self.fields["service"].label_from_instance = _service_label

            if self.appointment.time_slot:
                self.fields["new_time_slot_id"].initial = self.appointment.time_slot.id
                self.fields["new_appointment_date"].initial = self.appointment.date

            procedural_exists = Appointment.objects.filter(
                previous_appointment=self.appointment,
                time_slot__cabinet__number=6,
            ).exists()

            logger.info(
                "Инициализация AppointmentSimpleEditForm: procedural_exists=%s appointment_id=%s текущая_услуга=%s",
                procedural_exists,
                getattr(self.appointment, "id", None),
                getattr(getattr(self.appointment, "service", None), "name", None),
            )

            if procedural_exists:
                self.fields["needs_procedural"].initial = True

                if self._is_medical_blockade_service(self.appointment.service):
                    self.fields["needs_procedural"].widget.attrs.update(
                        {
                            "disabled": "disabled",
                            "title": "Для этой услуги процедурная запись обязательна",
                        }
                    )
                    logger.info(
                        "Инициализация AppointmentSimpleEditForm: флаг needs_procedural заблокирован для обязательной процедурной услуги appointment_id=%s",
                        getattr(self.appointment, "id", None),
                    )

    def clean(self):
        cleaned_data = super().clean()

        service = cleaned_data.get("service") or (
            self.instance.service if self.instance else None
        )

        posted_needs_procedural = cleaned_data.get("needs_procedural", False)

        logger.info(
            "Проверка формы редактирования записи: appointment_id=%s original_service_id=%s original_service=%s new_service_id=%s new_service=%s posted_needs_procedural=%s allow_time_change=%s new_time_slot_id=%s",
            getattr(self.appointment, "id", None),
            getattr(getattr(self.instance, "service", None), "id", None),
            getattr(getattr(self.instance, "service", None), "name", None),
            getattr(service, "id", None),
            getattr(service, "name", None),
            posted_needs_procedural,
            cleaned_data.get("allow_time_change", False),
            cleaned_data.get("new_time_slot_id"),
        )

        if self.appointment and self.appointment.pk:
            procedural_exists = Appointment.objects.filter(
                previous_appointment=self.appointment,
                time_slot__cabinet__number=6,
            ).exists()

            if procedural_exists and self._is_medical_blockade_service(service):
                cleaned_data["needs_procedural"] = True

            logger.info(
                "Проверка формы редактирования записи: procedural_exists=%s forced_needs_procedural=%s is_medical_blockade=%s",
                procedural_exists,
                cleaned_data.get("needs_procedural", False),
                self._is_medical_blockade_service(service),
            )

        allow_time_change = cleaned_data.get("allow_time_change", False)
        new_time_slot_id = cleaned_data.get("new_time_slot_id")

        if allow_time_change and new_time_slot_id:
            try:
                new_time_slot = TimeSlot.objects.get(id=new_time_slot_id)

                if not new_time_slot.is_available():
                    current_appointment_in_slot = new_time_slot.appointments.filter(
                        id=self.appointment.id
                    ).exists()

                    if not current_appointment_in_slot:
                        logger.warning(
                            "Проверка формы редактирования записи: выбранный слот уже занят appointment_id=%s new_time_slot_id=%s",
                            getattr(self.appointment, "id", None),
                            new_time_slot_id,
                        )
                        raise forms.ValidationError(
                            "Выбранный временной слот уже занят другим пациентом. "
                            "Пожалуйста, выберите другой слот."
                        )

                if new_time_slot.doctor != self.appointment.doctor:
                    logger.warning(
                        "Проверка формы редактирования записи: слот принадлежит другому врачу appointment_id=%s new_time_slot_id=%s expected_doctor_id=%s actual_doctor_id=%s",
                        getattr(self.appointment, "id", None),
                        new_time_slot_id,
                        getattr(self.appointment.doctor, "id", None),
                        getattr(new_time_slot.doctor, "id", None),
                    )
                    raise forms.ValidationError(
                        "Выбранный слот не принадлежит текущему врачу."
                    )

                new_date = cleaned_data.get("new_appointment_date")
                if new_date and new_time_slot.date != new_date:
                    logger.warning(
                        "Проверка формы редактирования записи: дата слота не совпадает appointment_id=%s new_time_slot_id=%s form_date=%s slot_date=%s",
                        getattr(self.appointment, "id", None),
                        new_time_slot_id,
                        new_date,
                        new_time_slot.date,
                    )
                    raise forms.ValidationError(
                        "Дата нового слота не совпадает с выбранной датой."
                    )

                cleaned_data["new_time_slot"] = new_time_slot

                logger.info(
                    "Проверка формы редактирования записи: новый слот принят appointment_id=%s new_time_slot_id=%s date=%s start=%s end=%s",
                    getattr(self.appointment, "id", None),
                    new_time_slot.id,
                    new_time_slot.date,
                    new_time_slot.start_time,
                    new_time_slot.end_time,
                )

            except TimeSlot.DoesNotExist:
                logger.warning(
                    "Проверка формы редактирования записи: новый слот не существует appointment_id=%s new_time_slot_id=%s",
                    getattr(self.appointment, "id", None),
                    new_time_slot_id,
                )
                raise forms.ValidationError("Выбранный временной слот не существует")

        needs_procedural = cleaned_data.get("needs_procedural", False)

        logger.info(
            "Проверка формы редактирования записи: перед проверкой процедурного кабинета appointment_id=%s final_needs_procedural=%s is_medical_blockade=%s",
            getattr(self.appointment, "id", None),
            needs_procedural,
            self._is_medical_blockade_service(service),
        )

        if needs_procedural or self._is_medical_blockade_service(service):
            self._validate_procedural_availability(cleaned_data)

        logger.info(
            "Проверка формы редактирования записи завершена успешно: appointment_id=%s",
            getattr(self.appointment, "id", None),
        )
        return cleaned_data

    def _is_medical_blockade_service(self, service):
        """Проверяет, является ли услуга медицинской блокадой"""
        if not service:
            return False

        from timetable.models import MedicalServiceCategory

        if service.category == MedicalServiceCategory.MEDICAL_BLOCKADES:
            return True

        blockade_keywords = [
            "блокада",
            "блокады",
            "блокад",
            "укол",
            "уколы",
            "инъекция",
            "инъекции",
            "введение",
            "внутримышечно",
            "внутрисуставно",
        ]
        service_name_lower = service.name.lower()

        return any(keyword in service_name_lower for keyword in blockade_keywords)

    def _validate_procedural_availability(self, cleaned_data):
        """Проверяет доступность процедурного кабинета"""
        needs_procedural = cleaned_data.get("needs_procedural", False)
        service = cleaned_data.get("service") or (
            self.instance.service if self.instance else None
        )

        logger.info(
            "Проверка доступности процедурного кабинета: appointment_id=%s needs_procedural=%s is_medical_blockade=%s",
            getattr(self.appointment, "id", None),
            needs_procedural,
            self._is_medical_blockade_service(service),
        )

        if not needs_procedural and not self._is_medical_blockade_service(service):
            logger.info(
                "Проверка доступности процедурного кабинета: пропуск проверки appointment_id=%s",
                getattr(self.appointment, "id", None),
            )
            return

        if cleaned_data.get("allow_time_change") and cleaned_data.get("new_time_slot"):
            time_slot_to_check = cleaned_data.get("new_time_slot")
        else:
            time_slot_to_check = self.appointment.time_slot

        if not time_slot_to_check:
            logger.warning(
                "Проверка доступности процедурного кабинета: отсутствует слот для проверки appointment_id=%s",
                getattr(self.appointment, "id", None),
            )
            return

        procedural_cabinet = get_procedural_cabinet()

        conflicting_slots = TimeSlot.objects.filter(
            date=time_slot_to_check.date,
            cabinet=procedural_cabinet,
            start_time__lt=time_slot_to_check.end_time,
            end_time__gt=time_slot_to_check.start_time,
            appointments__isnull=False,
        )

        procedural_appointment = Appointment.objects.filter(
            previous_appointment=self.appointment,
            time_slot__cabinet__number=6,
        ).first()

        if procedural_appointment and procedural_appointment.time_slot:
            conflicting_slots = conflicting_slots.exclude(
                id=procedural_appointment.time_slot_id
            )

        conflict_count = conflicting_slots.count()

        logger.info(
            "Проверка доступности процедурного кабинета: appointment_id=%s time_slot_id=%s date=%s conflict_count=%s existing_procedural_id=%s",
            getattr(self.appointment, "id", None),
            getattr(time_slot_to_check, "id", None),
            getattr(time_slot_to_check, "date", None),
            conflict_count,
            getattr(procedural_appointment, "id", None),
        )

        if conflicting_slots.exists():
            occupied_slot = conflicting_slots.first()
            first_appointment = occupied_slot.appointments.first()

            patient_name = (
                first_appointment.patient.get_full_name()
                if first_appointment and first_appointment.patient
                else "Неизвестный пациент"
            )

            logger.warning(
                "Проверка доступности процедурного кабинета: найден конфликт appointment_id=%s occupied_slot_id=%s patient=%s",
                getattr(self.appointment, "id", None),
                getattr(occupied_slot, "id", None),
                patient_name,
            )

            raise forms.ValidationError(
                f"Невозможно создать процедурную запись: время {time_slot_to_check.start_time.strftime('%H:%M')}-"
                f"{time_slot_to_check.end_time.strftime('%H:%M')} "
                f"на дату {time_slot_to_check.date.strftime('%d.%m.%Y')} "
                f"в процедурном кабинете уже занято пациентом {patient_name}. "
                f"Пожалуйста, выберите другое время или снимите галочку 'Занять окошко в процедурном кабинете'."
            )

    @transaction.atomic
    def save(self, commit=True):
        """Сохраняет запись с логированием решений по процедурному кабинету"""
        appointment = super().save(commit=False)
        service_changed = False
        procedural_was_moved = False

        original_service = getattr(self.instance, "service", None)
        new_service = self.cleaned_data.get("service") or appointment.service

        if self.instance.pk and original_service != new_service:
            service_changed = True

        logger.info(
            "Сохранение отредактированной записи: старт appointment_id=%s original_service_id=%s original_service=%s new_service_id=%s new_service=%s service_changed=%s commit=%s",
            getattr(self.instance, "id", None),
            getattr(original_service, "id", None),
            getattr(original_service, "name", None),
            getattr(new_service, "id", None),
            getattr(new_service, "name", None),
            service_changed,
            commit,
        )

        if self.instance.pk:
            old_date = self.instance.date
            allow_time_change = self.cleaned_data.get("allow_time_change", False)
            new_time_slot = self.cleaned_data.get("new_time_slot")

            if allow_time_change and new_time_slot:
                new_date = new_time_slot.date
            else:
                new_date = old_date

            if old_date != new_date:
                appointment.status = Appointment.AppointmentStatus.SCHEDULED
                logger.info(
                    "Сохранение отредактированной записи: изменилась дата, статус сброшен appointment_id=%s old_date=%s new_date=%s",
                    getattr(self.instance, "id", None),
                    old_date,
                    new_date,
                )

        if commit:
            try:
                allow_time_change = self.cleaned_data.get("allow_time_change", False)
                new_time_slot = self.cleaned_data.get("new_time_slot")

                if allow_time_change and new_time_slot:
                    old_time_slot = appointment.time_slot
                    appointment.time_slot = new_time_slot

                    logger.info(
                        "Сохранение отредактированной записи: изменено время appointment_id=%s old_time_slot_id=%s new_time_slot_id=%s",
                        getattr(self.instance, "id", None),
                        getattr(old_time_slot, "id", None),
                        getattr(new_time_slot, "id", None),
                    )

                    if old_time_slot.id != new_time_slot.id:
                        procedural_was_moved = self._move_procedural_appointment(
                            appointment, old_time_slot, new_time_slot
                        )

                appointment.save()

                logger.info(
                    "Сохранение отредактированной записи: основная запись сохранена appointment_id=%s time_slot_id=%s service_id=%s",
                    appointment.id,
                    getattr(appointment.time_slot, "id", None),
                    getattr(appointment.service, "id", None),
                )

                needs_procedural = self.cleaned_data.get("needs_procedural", False)
                service = self.cleaned_data.get("service") or appointment.service
                requires_procedural = (
                    needs_procedural or self._is_medical_blockade_service(service)
                )

                logger.info(
                    "Сохранение отредактированной записи: перед обработкой процедурной записи appointment_id=%s cleaned_needs_procedural=%s is_medical_blockade=%s procedural_was_moved=%s",
                    appointment.id,
                    needs_procedural,
                    self._is_medical_blockade_service(service),
                    procedural_was_moved,
                )

                if procedural_was_moved and requires_procedural:
                    logger.info(
                        "Сохранение отредактированной записи: связанная процедурная запись уже перенесена, повторная обработка не требуется appointment_id=%s",
                        appointment.id,
                    )
                else:
                    self._handle_procedural_appointment(appointment, needs_procedural)

                if service_changed and hasattr(self, "_update_procedural_service"):
                    logger.info(
                        "Сохранение отредактированной записи: обновление услуги в процедурной записи appointment_id=%s",
                        appointment.id,
                    )
                    self._update_procedural_service(appointment)

            except forms.ValidationError as e:
                logger.warning(
                    "Сохранение отредактированной записи: ValidationError appointment_id=%s error=%s",
                    getattr(self.instance, "id", None),
                    str(e),
                    exc_info=True,
                )
                raise forms.ValidationError(str(e))

        logger.info(
            "Сохранение отредактированной записи завершено успешно: appointment_id=%s",
            getattr(appointment, "id", None),
        )
        return appointment

    def _handle_procedural_appointment(self, appointment, needs_procedural):
        """Обрабатывает создание/обновление процедурной записи"""
        from appointments.services import ProceduralAppointmentService

        existing_procedural = Appointment.objects.filter(
            previous_appointment=appointment,
            time_slot__cabinet__number=6,
        ).first()

        service = self.cleaned_data.get("service") or appointment.service
        requires_procedural = needs_procedural or self._is_medical_blockade_service(
            service
        )

        logger.info(
            "Обработка процедурной записи: appointment_id=%s needs_procedural=%s is_medical_blockade=%s requires_procedural=%s existing_procedural_id=%s service=%s",
            getattr(appointment, "id", None),
            needs_procedural,
            self._is_medical_blockade_service(service),
            requires_procedural,
            getattr(existing_procedural, "id", None),
            getattr(service, "name", None),
        )

        if requires_procedural:
            if not existing_procedural:
                can_create = (
                    ProceduralAppointmentService.can_create_procedural_appointment(
                        appointment
                    )
                )

                logger.info(
                    "Обработка процедурной записи: существующая процедурная запись не найдена, can_create=%s appointment_id=%s",
                    can_create,
                    getattr(appointment, "id", None),
                )

                if not can_create:
                    raise forms.ValidationError(
                        "Невозможно создать процедурную запись: выбранное время в процедурном кабинете уже занято. "
                        "Пожалуйста, выберите другое время или снимите галочку 'Занять окошко в процедурном кабинете'."
                    )

                procedural = ProceduralAppointmentService.create_procedural_appointment(
                    appointment
                )

                logger.info(
                    "Обработка процедурной записи: процедурная запись создана appointment_id=%s procedural_id=%s procedural_slot_id=%s",
                    getattr(appointment, "id", None),
                    getattr(procedural, "id", None),
                    getattr(getattr(procedural, "time_slot", None), "id", None),
                )
            else:
                ProceduralAppointmentService.update_procedural_appointment(
                    appointment, existing_procedural
                )

                logger.info(
                    "Обработка процедурной записи: процедурная запись обновлена appointment_id=%s procedural_id=%s",
                    getattr(appointment, "id", None),
                    getattr(existing_procedural, "id", None),
                )

        elif existing_procedural:
            old_slot = existing_procedural.time_slot
            procedural_id = existing_procedural.id
            existing_procedural.delete()

            logger.info(
                "Обработка процедурной записи: процедурная запись удалена appointment_id=%s procedural_id=%s old_slot_id=%s",
                getattr(appointment, "id", None),
                procedural_id,
                getattr(old_slot, "id", None),
            )

            if old_slot and not old_slot.appointments.exists():
                old_slot_id = old_slot.id
                old_slot.delete()

                logger.info(
                    "Обработка процедурной записи: пустой процедурный слот удалён slot_id=%s",
                    old_slot_id,
                )

    def _move_procedural_appointment(self, appointment, old_time_slot, new_time_slot):
        """Переносит связанную процедурную запись на новое время"""
        procedural_appointment = Appointment.objects.filter(
            previous_appointment=appointment,
            time_slot__cabinet__number=6,
        ).first()

        logger.info(
            "Перенос процедурной записи: appointment_id=%s procedural_id=%s old_time_slot_id=%s new_time_slot_id=%s",
            getattr(appointment, "id", None),
            getattr(procedural_appointment, "id", None),
            getattr(old_time_slot, "id", None),
            getattr(new_time_slot, "id", None),
        )

        if not procedural_appointment:
            logger.info(
                "Перенос процедурной записи: процедурная запись отсутствует, перенос не требуется appointment_id=%s",
                getattr(appointment, "id", None),
            )
            return False

        procedural_cabinet = get_procedural_cabinet()

        procedural_time_slot, created = TimeSlot.objects.get_or_create(
            doctor=procedural_appointment.doctor or appointment.doctor,
            cabinet=procedural_cabinet,
            date=new_time_slot.date,
            start_time=new_time_slot.start_time,
            end_time=new_time_slot.end_time,
            defaults={"slot_type": "working", "description": "Процедурный кабинет"},
        )

        logger.info(
            "Перенос процедурной записи: целевой процедурный слот найден appointment_id=%s procedural_slot_id=%s created=%s",
            getattr(appointment, "id", None),
            getattr(procedural_time_slot, "id", None),
            created,
        )

        if not created and procedural_time_slot.appointments.exists():
            other_appointment = procedural_time_slot.appointments.exclude(
                id=procedural_appointment.id
            ).first()

            if other_appointment:
                error_msg = (
                    f"Невозможно перенести запись: время в процедурном кабинете уже занято записью "
                    f"#{other_appointment.id} для пациента {other_appointment.patient.get_full_name()}."
                )

                logger.warning(
                    "Перенос процедурной записи: целевой слот уже занят appointment_id=%s procedural_slot_id=%s other_appointment_id=%s",
                    getattr(appointment, "id", None),
                    getattr(procedural_time_slot, "id", None),
                    getattr(other_appointment, "id", None),
                )
                raise forms.ValidationError(error_msg)

        old_procedural_slot = procedural_appointment.time_slot
        procedural_appointment.time_slot = procedural_time_slot

        if procedural_appointment.comment != appointment.doctor.surname:
            procedural_appointment.comment = appointment.doctor.surname

        procedural_appointment.save()

        logger.info(
            "Перенос процедурной записи: процедурная запись перенесена appointment_id=%s procedural_id=%s new_procedural_slot_id=%s",
            getattr(appointment, "id", None),
            getattr(procedural_appointment, "id", None),
            getattr(procedural_time_slot, "id", None),
        )

        if old_procedural_slot and not old_procedural_slot.appointments.exists():
            old_slot_id = old_procedural_slot.id
            old_procedural_slot.delete()

            logger.info(
                "Перенос процедурной записи: старый пустой процедурный слот удалён slot_id=%s",
                old_slot_id,
            )

        return True

    def _update_procedural_service(self, appointment):
        """Всегда обновляет услугу в процедурной записи на ту же что и в основной записи"""
        procedural_appointment = Appointment.objects.filter(
            previous_appointment=appointment,
            time_slot__cabinet__number=6,
        ).first()

        logger.info(
            "Обновление услуги процедурной записи: appointment_id=%s procedural_id=%s main_service_id=%s main_service=%s",
            getattr(appointment, "id", None),
            getattr(procedural_appointment, "id", None),
            getattr(getattr(appointment, "service", None), "id", None),
            getattr(getattr(appointment, "service", None), "name", None),
        )

        if not procedural_appointment:
            logger.info(
                "Обновление услуги процедурной записи: процедурная запись отсутствует, обновление не требуется appointment_id=%s",
                getattr(appointment, "id", None),
            )
            return

        if appointment.service:
            procedural_appointment.service = appointment.service
            procedural_appointment.price_at_appointment = get_service_price_on_date(
                procedural_appointment.service, procedural_appointment.time_slot.date
            )
            procedural_appointment.save()

            logger.info(
                "Обновление услуги процедурной записи: услуга обновлена appointment_id=%s procedural_id=%s service_id=%s",
                getattr(appointment, "id", None),
                getattr(procedural_appointment, "id", None),
                getattr(getattr(appointment, "service", None), "id", None),
            )
        else:
            logger.warning(
                "Обновление услуги процедурной записи: у основной записи отсутствует услуга appointment_id=%s",
                getattr(appointment, "id", None),
            )


class ProceduralAppointmentForm(ProceduralAppointmentBaseForm, forms.ModelForm):
    """Форма создания записи в процедурный кабинет с поддержкой цепочек"""

    class Meta:
        model = Appointment
        fields = ["service", "insurance_type", "needs_reschedule", "comment"]

    def __init__(self, *args, **kwargs):
        self.selected_date = kwargs.pop("selected_date", None)

        doctor = None
        time_slot = None

        forms.ModelForm.__init__(self, *args, **kwargs)
        ProceduralAppointmentBaseForm.__init__(
            self,
            *args,
            **kwargs,
            doctor=doctor,
            time_slot=time_slot,
            selected_date=self.selected_date,
        )

        if not self.selected_date:
            self.selected_date = timezone.now().date()

        self.fields["insurance_type"].initial = "paid"
        self._update_service_queryset()

        logger.info(
            "Инициализация ProceduralAppointmentForm: selected_date=%s instance_id=%s",
            self.selected_date,
            getattr(getattr(self, "instance", None), "id", None),
        )

    def _update_service_queryset(self):
        """Обновляет queryset услуг после инициализации формы"""
        from timetable.models import MedicalServiceCategory

        nurse_categories = [
            MedicalServiceCategory.MEDICAL_BLOCKADES,
            MedicalServiceCategory.ANALYZES,
        ]

        nurse_services = MedicalService.objects.filter(
            category__in=nurse_categories, is_active=True
        )

        self.fields["service"].queryset = nurse_services

        logger.info(
            "Обновлен queryset услуг процедурной формы: services_count=%s",
            nurse_services.count(),
        )

    @transaction.atomic
    def save(self, commit=True):
        """Сохраняет процедурную запись с проверкой времени"""
        date = (
            self.cleaned_data.get("procedural_appointment_date") or self.selected_date
        )
        start_time = self.cleaned_data.get("procedural_start_time")
        end_time = self.cleaned_data.get("procedural_end_time")

        logger.info(
            "Сохранение ProceduralAppointmentForm: старт date=%s start_time=%s end_time=%s service_id=%s insurance_type=%s commit=%s",
            date,
            start_time,
            end_time,
            getattr(self.cleaned_data.get("service"), "id", None),
            self.cleaned_data.get("insurance_type"),
            commit,
        )

        if not all([date, start_time, end_time]):
            logger.warning(
                "Сохранение ProceduralAppointmentForm: не заполнены обязательные поля date=%s start_time=%s end_time=%s",
                date,
                start_time,
                end_time,
            )
            raise forms.ValidationError(
                "Для создания процедурной записи необходимо указать дату, время начала и окончания"
            )

        if not self.cleaned_data.get("insurance_type"):
            self.cleaned_data["insurance_type"] = "paid"
            logger.info(
                "Сохранение ProceduralAppointmentForm: тип оплаты не был указан, установлен paid"
            )

        appointment = super().save(commit=False)

        try:
            patient_data = self.get_patient_data()

            logger.info(
                "Сохранение ProceduralAppointmentForm: обработка данных пациента surname=%s first_name=%s birth_date=%s",
                patient_data.get("surname") if isinstance(patient_data, dict) else None,
                (
                    patient_data.get("first_name")
                    if isinstance(patient_data, dict)
                    else None
                ),
                (
                    patient_data.get("date_of_birth")
                    if isinstance(patient_data, dict)
                    else None
                ),
            )

            if not patient_data.get("surname") or not patient_data.get("first_name"):
                logger.warning(
                    "Сохранение ProceduralAppointmentForm: не заполнены фамилия или имя пациента"
                )
                raise forms.ValidationError("Необходимо указать фамилию и имя пациента")

            from patients.services import PatientService

            patient, created = PatientService.get_or_create_patient(patient_data)

            if not patient:
                logger.warning(
                    "Сохранение ProceduralAppointmentForm: пациент не был найден или создан"
                )
                raise forms.ValidationError("Не удалось создать или найти пациента")

            appointment.patient = patient

            logger.info(
                "Сохранение ProceduralAppointmentForm: пациент обработан patient_id=%s created=%s",
                getattr(patient, "id", None),
                created,
            )

        except Exception as e:
            logger.warning(
                "Сохранение ProceduralAppointmentForm: ошибка обработки данных пациента error=%s",
                str(e),
                exc_info=True,
            )
            raise forms.ValidationError(f"Ошибка обработки данных пациента: {str(e)}")

        from appointments.services import ProceduralAppointmentService
        from appointments.utils_for_caches import get_procedural_cabinet

        procedural_cabinet = get_procedural_cabinet()

        nurse_doctor = Doctor.objects.filter(specialization="nurse").first()
        if not nurse_doctor:
            logger.warning(
                "Сохранение ProceduralAppointmentForm: врач-медсестра не найден"
            )
            raise forms.ValidationError("Врач-медсестра не найден")

        logger.info(
            "Сохранение ProceduralAppointmentForm: найден врач-медсестра doctor_id=%s cabinet_id=%s",
            getattr(nurse_doctor, "id", None),
            getattr(procedural_cabinet, "id", None),
        )

        time_slot = ProceduralAppointmentService.create_or_get_procedural_slot(
            date=date,
            start_time=start_time,
            end_time=end_time,
            doctor=nurse_doctor,
        )

        logger.info(
            "Сохранение ProceduralAppointmentForm: получен процедурный слот slot_id=%s date=%s start_time=%s end_time=%s",
            getattr(time_slot, "id", None),
            getattr(time_slot, "date", None),
            getattr(time_slot, "start_time", None),
            getattr(time_slot, "end_time", None),
        )

        if time_slot.appointments.exists():
            if not (
                self.instance
                and self.instance.pk
                and self.instance.time_slot_id == time_slot.id
            ):
                logger.warning(
                    "Сохранение ProceduralAppointmentForm: процедурный кабинет уже занят slot_id=%s date=%s start_time=%s end_time=%s",
                    getattr(time_slot, "id", None),
                    date,
                    start_time,
                    end_time,
                )
                raise forms.ValidationError(
                    f"Процедурный кабинет в это время уже занят. "
                    f"Время: {start_time.strftime('%H:%M')}-{end_time.strftime('%H:%M')} "
                    f"Дата: {date.strftime('%d.%m.%Y')}"
                )

        appointment.time_slot = time_slot

        if not appointment.insurance_type:
            appointment.insurance_type = "paid"

        appointment.status = Appointment.AppointmentStatus.SCHEDULED

        if appointment.service and not appointment.price_at_appointment:
            appointment.price_at_appointment = get_service_price_on_date(
                appointment.service, appointment.time_slot.date
            )

        logger.info(
            "Сохранение ProceduralAppointmentForm: подготовлена запись patient_id=%s service_id=%s time_slot_id=%s price_at_appointment=%s",
            getattr(getattr(appointment, "patient", None), "id", None),
            getattr(getattr(appointment, "service", None), "id", None),
            getattr(getattr(appointment, "time_slot", None), "id", None),
            getattr(appointment, "price_at_appointment", None),
        )

        selected_blood_tests_input = self.cleaned_data.get(
            "selected_blood_tests_input", ""
        )
        selected_test_ids = []

        if selected_blood_tests_input and selected_blood_tests_input.strip():
            try:
                test_ids = [
                    int(id.strip())
                    for id in selected_blood_tests_input.split(",")
                    if id.strip() and id.strip().isdigit()
                ]
                selected_test_ids = test_ids

                logger.info(
                    "Сохранение ProceduralAppointmentForm: разобраны анализы крови tests_count=%s test_ids=%s",
                    len(selected_test_ids),
                    selected_test_ids,
                )
            except (ValueError, TypeError):
                logger.warning(
                    "Сохранение ProceduralAppointmentForm: неверный формат выбранных анализов raw=%s",
                    selected_blood_tests_input,
                )
                raise forms.ValidationError("Неверный формат выбранных анализов")

        total_sum = self.cleaned_data.get("total_sum")
        if not total_sum:
            tests_price = 0
            if selected_test_ids:
                from timetable.models import BloodTest

                tests_price = sum(
                    BloodTest.objects.filter(id__in=selected_test_ids).values_list(
                        "price", flat=True
                    )
                )

            service_price = appointment.price_at_appointment or 0
            total_sum = tests_price + service_price

            logger.info(
                "Сохранение ProceduralAppointmentForm: total_sum пересчитана автоматически service_price=%s tests_price=%s total_sum=%s",
                service_price,
                tests_price,
                total_sum,
            )

        appointment.total_with_blood_tests = total_sum

        if commit:
            appointment.save()

            logger.info(
                "Сохранение ProceduralAppointmentForm: основная процедурная запись сохранена appointment_id=%s",
                appointment.id,
            )

            if selected_test_ids:
                from appointments.models import AppointmentBloodTest

                AppointmentBloodTest.objects.filter(appointment=appointment).delete()

                for test_id in selected_test_ids:
                    AppointmentBloodTest.objects.create(
                        appointment=appointment, blood_test_id=test_id
                    )

                logger.info(
                    "Сохранение ProceduralAppointmentForm: сохранены анализы крови appointment_id=%s tests_count=%s",
                    appointment.id,
                    len(selected_test_ids),
                )

            service_price = appointment.price_at_appointment or (
                appointment.service.price if appointment.service else 0
            )
            tests_price = appointment.get_tests_price
            appointment.total_with_blood_tests = tests_price + service_price
            appointment.save()

            logger.info(
                "Сохранение ProceduralAppointmentForm: итоговая сумма пересчитана appointment_id=%s service_price=%s tests_price=%s total=%s",
                appointment.id,
                service_price,
                tests_price,
                appointment.total_with_blood_tests,
            )

            if selected_test_ids and appointment.comment:
                from timetable.models import BloodTest

                tests = BloodTest.objects.filter(id__in=selected_test_ids)
                if tests.exists():
                    tests_list = ", ".join([test.name for test in tests])
                    if "Анализы:" not in appointment.comment:
                        appointment.comment = (
                            f"{appointment.comment}\nАнализы: {tests_list}"
                        )
                        appointment.save()

                        logger.info(
                            "Сохранение ProceduralAppointmentForm: комментарий дополнен анализами appointment_id=%s",
                            appointment.id,
                        )

        logger.info(
            "Сохранение ProceduralAppointmentForm завершено успешно: appointment_id=%s",
            getattr(appointment, "id", None),
        )
        return appointment

    def _check_procedural_time_availability(self, start_time, end_time):
        """Проверяет доступность времени в процедурном кабинете"""
        try:
            date = self.selected_date or timezone.now().date()
            procedural_cabinet = get_procedural_cabinet()

            from timetable.models import TimeSlot

            conflicting_slots = TimeSlot.get_conflicting_slots(
                date=date,
                start_time=start_time,
                end_time=end_time,
                cabinet=procedural_cabinet,
            ).filter(appointments__isnull=False)

            is_available = not conflicting_slots.exists()

            logger.info(
                "Проверка доступности времени в процедурном кабинете: date=%s start_time=%s end_time=%s is_available=%s conflicts=%s",
                date,
                start_time,
                end_time,
                is_available,
                conflicting_slots.count(),
            )

            return is_available

        except Exception:
            logger.exception(
                "Ошибка при проверке доступности времени в процедурном кабинете: start_time=%s end_time=%s",
                start_time,
                end_time,
            )
            return False

    def _create_procedural_slot(self, start_time, end_time):
        """Создает или находит существующий временной слот для процедурного кабинета"""
        date = self.selected_date or timezone.now().date()

        time_slot = ProceduralAppointmentService.create_or_get_procedural_slot(
            date=date,
            start_time=start_time,
            end_time=end_time,
            doctor=None,
        )

        logger.info(
            "Создан или найден процедурный слот: slot_id=%s date=%s start_time=%s end_time=%s",
            getattr(time_slot, "id", None),
            date,
            start_time,
            end_time,
        )

        return time_slot

    def _validate_additional_appointment_time(
        self, appointment_data, order, main_appointment
    ):
        """Проверяет доступность времени для дополнительной записи"""
        try:
            doctor_id = appointment_data.get("doctor_id")
            service_id = appointment_data.get("service_id")
            time_slot_id = appointment_data.get("time_slot_id")

            logger.info(
                "Проверка времени дополнительной записи для процедурной формы: order=%s doctor_id=%s service_id=%s time_slot_id=%s main_appointment_id=%s",
                order,
                doctor_id,
                service_id,
                time_slot_id,
                getattr(main_appointment, "id", None),
            )

            if not all([doctor_id, service_id, time_slot_id]):
                logger.warning(
                    "Проверка времени дополнительной записи для процедурной формы: не все поля заполнены order=%s",
                    order,
                )
                return

            time_slot = TimeSlot.objects.get(id=time_slot_id)

            if not time_slot.is_available():
                logger.warning(
                    "Проверка времени дополнительной записи для процедурной формы: слот занят order=%s time_slot_id=%s",
                    order,
                    time_slot_id,
                )
                raise forms.ValidationError(
                    f"Ошибка в дополнительной записи #{order}: "
                    f"Слот {time_slot.start_time} уже занят. "
                    "Пожалуйста, выберите другое время."
                )

            logger.info(
                "Проверка времени дополнительной записи для процедурной формы завершена успешно: order=%s time_slot_id=%s",
                order,
                time_slot_id,
            )

        except TimeSlot.DoesNotExist:
            logger.warning(
                "Проверка времени дополнительной записи для процедурной формы: слот не существует order=%s time_slot_id=%s",
                order,
                time_slot_id,
            )
            raise forms.ValidationError(
                f"Ошибка в дополнительной записи #{order}: выбранный временной слот не существует"
            )

    def _handle_blood_tests(self, appointment):
        """Обработка выбранных анализов крови"""
        selected_blood_tests_input = self.cleaned_data.get(
            "selected_blood_tests_input", ""
        )

        if selected_blood_tests_input:
            try:
                selected_blood_tests_input = selected_blood_tests_input.strip()
                test_ids = [
                    int(id.strip())
                    for id in selected_blood_tests_input.split(",")
                    if id.strip() and id.strip().isdigit()
                ]

                selected_blood_tests = BloodTest.objects.filter(id__in=test_ids)

                for test in selected_blood_tests:
                    AppointmentBloodTest.objects.create(
                        appointment=appointment, blood_test=test
                    )

                logger.info(
                    "Обработка анализов крови в ProceduralAppointmentForm: appointment_id=%s tests_count=%s",
                    getattr(appointment, "id", None),
                    selected_blood_tests.count(),
                )

                self._update_appointment_comment(appointment, selected_blood_tests)

            except (ValueError, TypeError):
                logger.warning(
                    "Обработка анализов крови в ProceduralAppointmentForm: неверный формат raw=%s",
                    selected_blood_tests_input,
                )
                raise forms.ValidationError("Неверный формат выбранных анализов")

    def _update_appointment_comment(self, appointment, selected_blood_tests):
        """Обновляет комментарий с информацией об анализах"""
        user_comment = self.cleaned_data.get("comment", "").strip()
        comment_lines = []

        if user_comment:
            comment_lines.append(user_comment)

        if selected_blood_tests:
            tests_price = sum(test.price for test in selected_blood_tests)
            service_price = (
                appointment.price_at_appointment or appointment.service.price
            )
            total_price = tests_price + service_price

            comment_lines.append(
                f"Анализы: {tests_price} руб. + Забор крови: {service_price} руб. = Итого: {total_price} руб."
            )

        if comment_lines:
            appointment.comment = "\n".join(comment_lines)
            appointment.save()

            logger.info(
                "Обновлен комментарий процедурной записи: appointment_id=%s",
                getattr(appointment, "id", None),
            )

    def _handle_additional_appointments(self, main_appointment):
        """Обработка дополнительных записей к другим врачам (общая логика)"""
        appointment_chain_type = self.cleaned_data.get("appointment_chain_type")

        logger.info(
            "Обработка дополнительных записей в ProceduralAppointmentForm: main_appointment_id=%s chain_type=%s",
            getattr(main_appointment, "id", None),
            appointment_chain_type,
        )

        if appointment_chain_type in ["another_doctor", "multiple"]:
            additional_data = self.cleaned_data.get("additional_appointments_data")
            procedural_data = self.cleaned_data.get("procedural_appointments_data")

            if additional_data:
                try:
                    appointments_list = json.loads(additional_data)
                    procedural_list = (
                        json.loads(procedural_data) if procedural_data else []
                    )

                    logger.info(
                        "Обработка дополнительных записей в ProceduralAppointmentForm: additional_count=%s procedural_count=%s",
                        len(appointments_list),
                        len(procedural_list),
                    )

                    for i, appointment_data in enumerate(appointments_list, start=1):
                        additional_appointment = self._create_additional_appointment(
                            main_appointment, appointment_data, i
                        )

                        logger.info(
                            "Обработка дополнительных записей в ProceduralAppointmentForm: создана дополнительная запись main_appointment_id=%s additional_appointment_id=%s order=%s",
                            getattr(main_appointment, "id", None),
                            getattr(additional_appointment, "id", None),
                            i,
                        )

                        procedural_info = None
                        if procedural_list:
                            for item in procedural_list:
                                if str(item.get("index")) == str(
                                    appointment_data.get("index")
                                ):
                                    procedural_info = item
                                    break

                        if procedural_info and procedural_info.get("needs_procedural"):
                            ProceduralAppointmentService.create_procedural_for_appointment(
                                additional_appointment,
                                main_appointment=additional_appointment,
                            )

                            logger.info(
                                "Обработка дополнительных записей в ProceduralAppointmentForm: создана процедурная запись для дополнительной записи additional_appointment_id=%s",
                                getattr(additional_appointment, "id", None),
                            )

                except (json.JSONDecodeError, KeyError) as e:
                    logger.warning(
                        "Обработка дополнительных записей в ProceduralAppointmentForm: ошибка обработки данных error=%s",
                        str(e),
                    )
                    raise forms.ValidationError(
                        f"Ошибка обработки данных дополнительных записей: {str(e)}"
                    )

    def _create_additional_appointment(self, main_appointment, appointment_data, order):
        """Создание одной дополнительной записи (общая логика)"""
        try:
            doctor_id = appointment_data.get("doctor_id")
            service_id = appointment_data.get("service_id")
            time_slot_id = appointment_data.get("time_slot_id")
            comment = appointment_data.get("comment", "")
            insurance_type = appointment_data.get("insurance_type", "paid")

            logger.info(
                "Создание дополнительной записи из ProceduralAppointmentForm: main_appointment_id=%s order=%s doctor_id=%s service_id=%s time_slot_id=%s",
                getattr(main_appointment, "id", None),
                order,
                doctor_id,
                service_id,
                time_slot_id,
            )

            if not all([doctor_id, service_id, time_slot_id]):
                logger.warning(
                    "Создание дополнительной записи из ProceduralAppointmentForm: не все обязательные поля заполнены order=%s",
                    order,
                )
                raise ValueError("Не все обязательные поля заполнены")

            doctor = Doctor.objects.get(id=doctor_id)
            service = MedicalService.objects.get(id=service_id)
            time_slot = TimeSlot.objects.get(id=time_slot_id)

            if not time_slot.is_available():
                logger.warning(
                    "Создание дополнительной записи из ProceduralAppointmentForm: слот занят order=%s time_slot_id=%s doctor_id=%s",
                    order,
                    time_slot_id,
                    doctor_id,
                )
                raise forms.ValidationError(
                    f"Слот {time_slot.start_time} у врача {doctor.surname} уже занят"
                )

            additional_appointment = Appointment.objects.create(
                time_slot=time_slot,
                patient=main_appointment.patient,
                service=service,
                insurance_type=insurance_type,
                status=Appointment.AppointmentStatus.SCHEDULED,
                comment=comment or f"Дополнительная запись!",
                chain_type=Appointment.ChainType.MULTIPLE_DOCTORS,
                is_chain_main=False,
            )

            additional_appointment.price_at_appointment = get_service_price_on_date(
                service, time_slot.date
            )
            additional_appointment.total_with_blood_tests = get_service_price_on_date(
                service, time_slot.date
            )
            additional_appointment.save()

            AppointmentChain.objects.create(
                main_appointment=main_appointment,
                related_appointment=additional_appointment,
                chain_type=AppointmentChain.ChainType.ANOTHER_DOCTOR,
                order=order,
            )

            logger.info(
                "Создание дополнительной записи из ProceduralAppointmentForm завершено успешно: additional_appointment_id=%s main_appointment_id=%s order=%s",
                getattr(additional_appointment, "id", None),
                getattr(main_appointment, "id", None),
                order,
            )

            return additional_appointment

        except (
            Doctor.DoesNotExist,
            MedicalService.DoesNotExist,
            TimeSlot.DoesNotExist,
        ) as e:
            logger.warning(
                "Создание дополнительной записи из ProceduralAppointmentForm: объект не найден order=%s error=%s",
                order,
                str(e),
            )
            raise forms.ValidationError(
                f"Ошибка создания дополнительной записи: {str(e)}"
            )

    def _set_appointment_price(appointment, service=None):
        """Устанавливает цену услуги для записи на дату визита (time_slot.date)."""
        visit_date = appointment.time_slot.date if appointment.time_slot else None
        svc = service or appointment.service

        if svc and visit_date:
            appointment.price_at_appointment = get_service_price_on_date(
                svc, visit_date
            )
        elif svc:
            appointment.price_at_appointment = svc.price

        if not appointment.total_with_blood_tests:
            appointment.total_with_blood_tests = appointment.price_at_appointment


class ProceduralAppointmentUpdateForm(forms.ModelForm):
    """Упрощенная форма для редактирования процедурной записи - только основные поля"""

    procedural_appointment_date = forms.DateField(
        required=True,
        label="Дата записи",
        widget=forms.DateInput(
            attrs={
                "type": "date",
                "class": "form-control",
                "id": "id_procedural_appointment_date",
            }
        ),
    )

    procedural_start_time = forms.TimeField(
        required=True,
        label="Время начала",
        widget=forms.TimeInput(attrs={"type": "time", "class": "form-control"}),
    )

    procedural_end_time = forms.TimeField(
        required=True,
        label="Время окончания",
        widget=forms.TimeInput(attrs={"type": "time", "class": "form-control"}),
    )

    selected_blood_tests_input = forms.CharField(
        required=False,
        widget=forms.HiddenInput(attrs={"id": "id_selected_blood_tests"}),
        label="Выбранные анализы крови",
    )

    total_sum = forms.DecimalField(
        required=False,
        max_digits=10,
        decimal_places=2,
        widget=forms.HiddenInput(attrs={"id": "id_total_sum"}),
        label="Итоговая сумма",
    )

    class Meta:
        model = Appointment
        fields = ["service", "insurance_type", "comment"]
        widgets = {
            "service": forms.Select(attrs={"class": "form-select"}),
            "insurance_type": forms.Select(attrs={"class": "form-select"}),
            "comment": forms.Textarea(attrs={"rows": 3, "class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        self.current_appointment = kwargs.pop("current_appointment", None)
        self.selected_date = kwargs.pop("selected_date", None)
        super().__init__(*args, **kwargs)

        from django.utils import timezone

        today = timezone.now().date()
        self.fields["procedural_appointment_date"].widget.attrs[
            "min"
        ] = today.isoformat()

        logger.info(
            "Инициализация ProceduralAppointmentUpdateForm: current_appointment_id=%s selected_date=%s instance_id=%s",
            getattr(self.current_appointment, "id", None),
            self.selected_date,
            getattr(getattr(self, "instance", None), "id", None),
        )

        if self.current_appointment and self.instance.pk:
            self._set_initial_values()
            self._update_service_queryset(self._get_target_service_date())

    def _get_target_service_date(self):
        raw_date = None

        if self.is_bound:
            raw_date = self.data.get(self.add_prefix("procedural_appointment_date"))

        if raw_date:
            try:
                return date_cls.fromisoformat(raw_date)
            except (TypeError, ValueError):
                logger.warning(
                    "Не удалось распознать дату формы редактирования процедурной записи: appointment_id=%s raw_date=%s",
                    getattr(self.current_appointment, "id", None),
                    raw_date,
                )

        return (
            self.selected_date
            or getattr(self.current_appointment, "date", None)
            or getattr(self.instance, "date", None)
        )

    def _update_service_queryset(self, target_date=None):
        """Обновляет queryset услуг после инициализации формы"""
        from timetable.models import MedicalServiceCategory

        nurse_categories = [
            MedicalServiceCategory.MEDICAL_BLOCKADES,
            MedicalServiceCategory.ANALYZES,
        ]

        nurse_services = MedicalService.objects.filter(
            category__in=nurse_categories, is_active=True
        )

        self.fields["service"].queryset = nurse_services
        self.fields["service"].choices = [
            (
                service.pk,
                f"{service.name} - {get_service_price_on_date(service, target_date):.2f} руб.",
            )
            for service in nurse_services
        ]

        logger.info(
            "Обновлен queryset услуг формы редактирования процедурной записи: services_count=%s target_date=%s",
            nurse_services.count(),
            target_date,
        )

    def _set_initial_values(self):
        """Устанавливает начальные значения для формы"""
        if self.current_appointment.date:
            self.fields["procedural_appointment_date"].initial = (
                self.current_appointment.date
            )

        selected_tests = self.current_appointment.selected_blood_tests.all()
        if selected_tests.exists():
            test_ids = [str(test.blood_test.id) for test in selected_tests]
            self.fields["selected_blood_tests_input"].initial = ",".join(test_ids)

        if self.current_appointment.total_with_blood_tests:
            self.fields["total_sum"].initial = (
                self.current_appointment.total_with_blood_tests
            )

        if self.current_appointment.start_time:
            self.fields["procedural_start_time"].initial = (
                self.current_appointment.start_time.strftime("%H:%M")
            )
        if self.current_appointment.end_time:
            self.fields["procedural_end_time"].initial = (
                self.current_appointment.end_time.strftime("%H:%M")
            )

        if self.current_appointment.service:
            self.fields["service"].initial = self.current_appointment.service

        logger.info(
            "Установлены начальные значения ProceduralAppointmentUpdateForm: appointment_id=%s date=%s start_time=%s end_time=%s service_id=%s total_sum=%s",
            getattr(self.current_appointment, "id", None),
            getattr(self.current_appointment, "date", None),
            getattr(self.current_appointment, "start_time", None),
            getattr(self.current_appointment, "end_time", None),
            getattr(getattr(self.current_appointment, "service", None), "id", None),
            getattr(self.current_appointment, "total_with_blood_tests", None),
        )

    def clean(self):
        """Проверка формы редактирования процедурной записи"""
        cleaned_data = super().clean()

        start_time = cleaned_data.get("procedural_start_time")
        end_time = cleaned_data.get("procedural_end_time")
        appointment_date = cleaned_data.get("procedural_appointment_date")

        logger.info(
            "Проверка ProceduralAppointmentUpdateForm: appointment_id=%s appointment_date=%s start_time=%s end_time=%s service_id=%s insurance_type=%s",
            getattr(self.current_appointment, "id", None),
            appointment_date,
            start_time,
            end_time,
            getattr(cleaned_data.get("service"), "id", None),
            cleaned_data.get("insurance_type"),
        )

        if start_time and end_time and start_time >= end_time:
            logger.warning(
                "Проверка ProceduralAppointmentUpdateForm: время окончания не позже времени начала appointment_id=%s start_time=%s end_time=%s",
                getattr(self.current_appointment, "id", None),
                start_time,
                end_time,
            )
            raise forms.ValidationError(
                "Время окончания должно быть позже времени начала"
            )

        if appointment_date and start_time and end_time:
            if not self._check_procedural_time_availability(
                appointment_date, start_time, end_time
            ):
                logger.warning(
                    "Проверка ProceduralAppointmentUpdateForm: выбранное время уже занято appointment_id=%s date=%s start_time=%s end_time=%s",
                    getattr(self.current_appointment, "id", None),
                    appointment_date,
                    start_time,
                    end_time,
                )
                raise forms.ValidationError(
                    "Выбранное время в процедурном кабинете уже занято. "
                    "Пожалуйста, выберите другое время."
                )

        if not cleaned_data.get("selected_blood_tests_input"):
            cleaned_data["selected_blood_tests_input"] = ""

        if not cleaned_data.get("total_sum"):
            try:
                service = (
                    cleaned_data.get("service") or self.current_appointment.service
                )
                target_date = appointment_date or self.current_appointment.date
                test_ids_input = cleaned_data.get("selected_blood_tests_input", "")

                test_ids = [
                    int(id.strip())
                    for id in test_ids_input.split(",")
                    if id.strip().isdigit()
                ]
                tests_price = sum(
                    BloodTest.objects.filter(id__in=test_ids).values_list(
                        "price", flat=True
                    )
                )
                service_price = (
                    get_service_price_on_date(service, target_date) if service else 0
                )
                total = tests_price + service_price

                cleaned_data["total_sum"] = total

                logger.info(
                    "Проверка ProceduralAppointmentUpdateForm: total_sum пересчитана автоматически appointment_id=%s tests_price=%s service_price=%s total=%s",
                    getattr(self.current_appointment, "id", None),
                    tests_price,
                    service_price,
                    total,
                )
            except Exception:
                cleaned_data["total_sum"] = 0
                logger.warning(
                    "Проверка ProceduralAppointmentUpdateForm: не удалось пересчитать total_sum appointment_id=%s",
                    getattr(self.current_appointment, "id", None),
                    exc_info=True,
                )

        logger.info(
            "Проверка ProceduralAppointmentUpdateForm завершена успешно: appointment_id=%s",
            getattr(self.current_appointment, "id", None),
        )
        return cleaned_data

    def _check_procedural_time_availability(self, date, start_time, end_time):
        """Проверяет доступность времени в процедурном кабинете на указанную дату"""
        try:
            procedural_cabinet = get_procedural_cabinet()

            conflicting_slots = TimeSlot.get_conflicting_slots(
                date=date,
                start_time=start_time,
                end_time=end_time,
                cabinet=procedural_cabinet,
            ).filter(appointments__isnull=False)

            if self.current_appointment and self.current_appointment.time_slot:
                conflicting_slots = conflicting_slots.exclude(
                    id=self.current_appointment.time_slot_id
                )

            is_available = not conflicting_slots.exists()

            logger.info(
                "Проверка доступности времени при редактировании процедурной записи: appointment_id=%s date=%s start_time=%s end_time=%s is_available=%s conflicts=%s",
                getattr(self.current_appointment, "id", None),
                date,
                start_time,
                end_time,
                is_available,
                conflicting_slots.count(),
            )

            return is_available

        except Exception:
            logger.exception(
                "Ошибка при проверке доступности времени в ProceduralAppointmentUpdateForm: appointment_id=%s date=%s start_time=%s end_time=%s",
                getattr(self.current_appointment, "id", None),
                date,
                start_time,
                end_time,
            )
            return False

    @transaction.atomic
    def save(self, commit=True):
        """Сохраняет изменения существующей процедурной записи"""
        appointment = self.instance

        new_date = self.cleaned_data.get("procedural_appointment_date")
        start_time = self.cleaned_data.get("procedural_start_time")
        end_time = self.cleaned_data.get("procedural_end_time")

        logger.info(
            "Сохранение ProceduralAppointmentUpdateForm: старт appointment_id=%s new_date=%s start_time=%s end_time=%s service_id=%s insurance_type=%s commit=%s",
            getattr(appointment, "id", None),
            new_date,
            start_time,
            end_time,
            getattr(self.cleaned_data.get("service"), "id", None),
            self.cleaned_data.get("insurance_type"),
            commit,
        )

        date_changed = new_date and new_date != appointment.date
        time_changed = False

        if start_time and end_time and appointment.time_slot:
            current_start = appointment.time_slot.start_time.strftime("%H:%M")
            current_end = appointment.time_slot.end_time.strftime("%H:%M")
            new_start = (
                start_time.strftime("%H:%M")
                if hasattr(start_time, "strftime")
                else str(start_time)
            )
            new_end = (
                end_time.strftime("%H:%M")
                if hasattr(end_time, "strftime")
                else str(end_time)
            )

            time_changed = current_start != new_start or current_end != new_end

        logger.info(
            "Сохранение ProceduralAppointmentUpdateForm: appointment_id=%s date_changed=%s time_changed=%s",
            getattr(appointment, "id", None),
            date_changed,
            time_changed,
        )

        if date_changed or time_changed:
            from appointments.services import ProceduralAppointmentService

            time_slot = ProceduralAppointmentService.create_or_get_procedural_slot(
                date=new_date,
                start_time=start_time,
                end_time=end_time,
                doctor=appointment.doctor,
            )

            logger.info(
                "Сохранение ProceduralAppointmentUpdateForm: получен новый/существующий слот appointment_id=%s slot_id=%s",
                getattr(appointment, "id", None),
                getattr(time_slot, "id", None),
            )

            if time_slot.id != appointment.time_slot_id:
                if time_slot.appointments.exclude(id=appointment.id).exists():
                    logger.warning(
                        "Сохранение ProceduralAppointmentUpdateForm: целевой слот уже занят appointment_id=%s slot_id=%s",
                        getattr(appointment, "id", None),
                        getattr(time_slot, "id", None),
                    )
                    raise forms.ValidationError(
                        "Выбранное время уже занято другой записью. Пожалуйста, выберите другое время."
                    )

            appointment.time_slot = time_slot

        appointment.service = self.cleaned_data.get("service") or appointment.service
        appointment.insurance_type = (
            self.cleaned_data.get("insurance_type") or appointment.insurance_type
        )

        user_comment = self.cleaned_data.get("comment", "")
        if user_comment != appointment.comment:
            appointment.comment = user_comment

        target_date = new_date or appointment.date
        if appointment.service:
            appointment.price_at_appointment = get_service_price_on_date(
                appointment.service, target_date
            )

        selected_blood_tests_input = self.cleaned_data.get(
            "selected_blood_tests_input", ""
        )
        tests_price = 0

        if selected_blood_tests_input and selected_blood_tests_input.strip():
            test_ids = [
                int(id.strip())
                for id in selected_blood_tests_input.split(",")
                if id.strip() and id.strip().isdigit()
            ]

            if test_ids:
                tests_price = sum(
                    BloodTest.objects.filter(id__in=test_ids).values_list(
                        "price", flat=True
                    )
                )

        service_price = appointment.price_at_appointment or 0
        appointment.total_with_blood_tests = tests_price + service_price

        logger.info(
            "Сохранение ProceduralAppointmentUpdateForm: рассчитаны суммы appointment_id=%s service_price=%s tests_price=%s total=%s",
            getattr(appointment, "id", None),
            service_price,
            tests_price,
            appointment.total_with_blood_tests,
        )

        if commit:
            appointment.save()

            logger.info(
                "Сохранение ProceduralAppointmentUpdateForm: запись сохранена appointment_id=%s",
                getattr(appointment, "id", None),
            )

            self._update_blood_tests(appointment)
            appointment.save()

            logger.info(
                "Сохранение ProceduralAppointmentUpdateForm завершено успешно: appointment_id=%s",
                getattr(appointment, "id", None),
            )

        return appointment

    def _update_blood_tests(self, appointment):
        """Обновляет выбранные анализы крови"""
        selected_blood_tests_input = self.cleaned_data.get(
            "selected_blood_tests_input", ""
        )

        appointment.selected_blood_tests.all().delete()

        logger.info(
            "Обновление анализов крови в ProceduralAppointmentUpdateForm: очищены старые связи appointment_id=%s",
            getattr(appointment, "id", None),
        )

        if selected_blood_tests_input and selected_blood_tests_input.strip():
            try:
                test_ids = [
                    int(id.strip())
                    for id in selected_blood_tests_input.split(",")
                    if id.strip() and id.strip().isdigit()
                ]

                for test_id in test_ids:
                    AppointmentBloodTest.objects.create(
                        appointment=appointment, blood_test_id=test_id
                    )

                logger.info(
                    "Обновление анализов крови в ProceduralAppointmentUpdateForm: добавлены новые анализы appointment_id=%s tests_count=%s",
                    getattr(appointment, "id", None),
                    len(test_ids),
                )

            except (ValueError, TypeError) as e:
                logger.warning(
                    "Обновление анализов крови в ProceduralAppointmentUpdateForm: ошибка разбора test_ids appointment_id=%s error=%s",
                    getattr(appointment, "id", None),
                    str(e),
                    exc_info=True,
                )


class AdditionalAppointmentForm(forms.Form):
    """Форма для одной дополнительной записи к другому врачу"""

    doctor = forms.ModelChoiceField(
        queryset=Doctor.objects.order_by("surname"),
        widget=forms.Select(
            attrs={
                "class": "form-select additional-doctor-select",
                "data-action": "change->appointment#onDoctorChange",
            }
        ),
        label="Врач",
        required=True,
    )

    service = forms.ModelChoiceField(
        queryset=MedicalService.objects.none(),
        widget=forms.Select(
            attrs={
                "class": "form-select additional-service-select",
                "disabled": "disabled",
                "data-action": "change->appointment#onServiceChange",
            }
        ),
        label="Услуга",
        required=True,
    )

    appointment_date = forms.DateField(
        widget=forms.DateInput(
            attrs={
                "type": "date",
                "class": "form-control additional-date-select",
                "data-action": "change->appointment#onDateChange",
            }
        ),
        label="Дата приема",
        required=True,
    )

    time_slot = forms.ModelChoiceField(
        queryset=TimeSlot.objects.none(),
        widget=forms.Select(
            attrs={
                "class": "form-select additional-slot-select",
                "disabled": "disabled",
                "data-action": "change->appointment#onSlotChange",
            }
        ),
        label="Временной слот",
        required=True,
    )

    comment = forms.CharField(
        widget=forms.Textarea(
            attrs={
                "rows": 2,
                "class": "form-control",
                "placeholder": "Комментарий к дополнительной записи",
            }
        ),
        label="Комментарий",
        required=False,
    )

    def __init__(self, *args, **kwargs):
        self.initial_doctor = kwargs.pop("initial_doctor", None)
        self.initial_date = kwargs.pop("initial_date", None)
        super().__init__(*args, **kwargs)

        today = timezone.now().date()
        self.fields["appointment_date"].widget.attrs["min"] = today.isoformat()

        logger.info(
            "Инициализация AdditionalAppointmentForm: initial_doctor_id=%s initial_date=%s bound=%s",
            getattr(self.initial_doctor, "id", None),
            self.initial_date,
            self.is_bound,
        )

        if self.initial_doctor:
            self.fields["doctor"].initial = self.initial_doctor
            self.set_service_queryset(self.initial_doctor)

        if self.initial_date:
            self.fields["appointment_date"].initial = self.initial_date

    def set_service_queryset(self, doctor):
        """Устанавливает queryset услуг для выбранного врача"""
        if doctor:
            logger.info(
                "Установка queryset услуг для дополнительной записи: doctor_id=%s doctor=%s",
                getattr(doctor, "id", None),
                getattr(doctor, "surname", None),
            )

            from appointments.services import AppointmentService

            class TempForm:
                def __init__(self, doctor):
                    self.doctor = doctor
                    self.fields = {
                        "service": type(
                            "Field", (), {"queryset": MedicalService.objects.none()}
                        ),
                        "additional_service": type(
                            "Field", (), {"queryset": MedicalService.objects.none()}
                        ),
                    }

            temp_form = TempForm(doctor)
            AppointmentService.initialize_service_queryset(temp_form, doctor)

            self.fields["service"].queryset = temp_form.fields["service"].queryset
            self.fields["service"].widget.attrs.pop("disabled", None)

            logger.info(
                "Установка queryset услуг для дополнительной записи завершена: doctor_id=%s services_count=%s",
                getattr(doctor, "id", None),
                (
                    self.fields["service"].queryset.count()
                    if hasattr(self.fields["service"].queryset, "count")
                    else "unknown"
                ),
            )
        else:
            logger.warning(
                "Установка queryset услуг для дополнительной записи: врач не передан"
            )

    def set_time_slot_queryset(self, doctor, date):
        """Устанавливает queryset слотов для выбранного врача и даты"""
        if doctor and date:
            logger.info(
                "Установка queryset слотов для дополнительной записи: doctor_id=%s date=%s",
                getattr(doctor, "id", None),
                date,
            )

            available_slots = TimeSlot.objects.filter(
                doctor=doctor,
                date=date,
                slot_type="working",
                appointments__isnull=True,
            ).order_by("start_time")

            self.fields["time_slot"].queryset = available_slots
            if available_slots.exists():
                self.fields["time_slot"].widget.attrs.pop("disabled", None)
                logger.info(
                    "Найдены доступные слоты для дополнительной записи: doctor_id=%s date=%s slots_count=%s",
                    getattr(doctor, "id", None),
                    date,
                    available_slots.count(),
                )
            else:
                self.fields["time_slot"].widget.attrs["disabled"] = "disabled"
                self.fields["time_slot"].queryset = TimeSlot.objects.none()
                logger.warning(
                    "Нет доступных слотов для дополнительной записи: doctor_id=%s date=%s",
                    getattr(doctor, "id", None),
                    date,
                )
        else:
            logger.warning(
                "Установка queryset слотов для дополнительной записи: недостаточно данных doctor_id=%s date=%s",
                getattr(doctor, "id", None) if doctor else None,
                date,
            )

    def clean(self):
        cleaned_data = super().clean()

        doctor = cleaned_data.get("doctor")
        appointment_date = cleaned_data.get("appointment_date")
        time_slot = cleaned_data.get("time_slot")
        service = cleaned_data.get("service")

        logger.info(
            "Проверка AdditionalAppointmentForm: doctor_id=%s service_id=%s appointment_date=%s time_slot_id=%s",
            getattr(doctor, "id", None),
            getattr(service, "id", None),
            appointment_date,
            getattr(time_slot, "id", None),
        )

        if not doctor or not appointment_date or not time_slot:
            logger.warning(
                "Проверка AdditionalAppointmentForm: не все обязательные поля заполнены doctor_id=%s appointment_date=%s time_slot_id=%s",
                getattr(doctor, "id", None),
                appointment_date,
                getattr(time_slot, "id", None),
            )
            return cleaned_data

        if time_slot.doctor != doctor:
            logger.warning(
                "Проверка AdditionalAppointmentForm: слот принадлежит другому врачу doctor_id=%s slot_doctor_id=%s time_slot_id=%s",
                getattr(doctor, "id", None),
                getattr(getattr(time_slot, "doctor", None), "id", None),
                getattr(time_slot, "id", None),
            )
            raise ValidationError("Выбранный слот не принадлежит выбранному врачу")

        if time_slot.date != appointment_date:
            logger.warning(
                "Проверка AdditionalAppointmentForm: дата слота не совпадает doctor_id=%s selected_date=%s slot_date=%s time_slot_id=%s",
                getattr(doctor, "id", None),
                appointment_date,
                getattr(time_slot, "date", None),
                getattr(time_slot, "id", None),
            )
            raise ValidationError("Выбранный слот не на выбранную дату")

        if not time_slot.is_available():
            logger.warning(
                "Проверка AdditionalAppointmentForm: выбранный слот уже занят doctor_id=%s time_slot_id=%s date=%s",
                getattr(doctor, "id", None),
                getattr(time_slot, "id", None),
                getattr(time_slot, "date", None),
            )
            raise ValidationError("Выбранный слот уже занят")

        logger.info(
            "Проверка AdditionalAppointmentForm завершена успешно: doctor_id=%s service_id=%s time_slot_id=%s",
            getattr(doctor, "id", None),
            getattr(service, "id", None),
            getattr(time_slot, "id", None),
        )
        return cleaned_data
