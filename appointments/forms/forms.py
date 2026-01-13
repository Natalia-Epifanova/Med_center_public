import json

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


class AppointmentForm(AppointmentChainBaseForm, forms.ModelForm):
    """Форма создания записи с возможностью изменения времени"""

    class Meta:
        model = Appointment
        fields = [
            "service",
            "insurance_type",
            "needs_reschedule",
            "comment",
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

    def __init__(self, *args, **kwargs):

        self.time_slot = kwargs.pop("time_slot", None)
        self.doctor = kwargs.pop("doctor", None)

        # Теперь передаем в родительский класс
        super().__init__(*args, **kwargs, time_slot=self.time_slot, doctor=self.doctor)
        self.fields["insurance_type"].initial = "paid"

        # Инициализируем поля с текущими значениями
        if self.time_slot:
            self.fields["new_time_slot_id"].initial = self.time_slot.id
            self.fields["new_appointment_date"].initial = self.time_slot.date

        # Определяем врача для использования
        doctor_to_use = self.doctor or (
            self.time_slot.doctor if self.time_slot else None
        )
        # Используем сервис для инициализации queryset
        AppointmentService.initialize_service_queryset(self, doctor_to_use)

    def clean(self):
        cleaned_data = super().clean()

        # Проверяем, разрешено ли изменение времени
        allow_time_change = cleaned_data.get("allow_time_change")
        new_time_slot_id = cleaned_data.get("new_time_slot_id")

        if allow_time_change and new_time_slot_id:
            try:
                # Получаем новый слот
                new_time_slot = TimeSlot.objects.get(id=new_time_slot_id)

                # Проверяем доступность
                if not new_time_slot.is_available():
                    raise forms.ValidationError(
                        "Выбранный временной слот уже занят. Пожалуйста, выберите другой слот."
                    )

                # Проверяем, что слот принадлежит тому же врачу
                if self.doctor and new_time_slot.doctor != self.doctor:
                    raise forms.ValidationError(
                        "Выбранный слот не принадлежит текущему врачу."
                    )

                # Сохраняем объект слота для использования в save()
                cleaned_data["new_time_slot"] = new_time_slot

            except TimeSlot.DoesNotExist:
                raise forms.ValidationError("Выбранный временной слот не существует")

        return cleaned_data

    def _validate_consecutive_for_pishchelev(
        self, main_appointment, appointment_chain_type
    ):
        """Дополнительная валидация для последовательных записей Пищелева"""
        if not hasattr(main_appointment, "doctor") or not main_appointment.doctor:
            return

        is_pishchelev = "пищелев" in main_appointment.doctor.surname.lower()
        if not is_pishchelev:
            return

        if appointment_chain_type == "two_slots":
            # Для записи на 2 слота
            next_slot = main_appointment.time_slot.get_next_consecutive_slot()
            if not next_slot:
                return

    @transaction.atomic
    def save(self, commit=True):
        """Сохраняет запись с транзакционной безопасность."""
        if not commit:
            return super(AppointmentChainBaseForm, self).save(commit=False)

        try:
            with transaction.atomic():
                # Создание/поиск пациента
                patient_data = self.get_patient_data()
                patient, created = PatientService.get_or_create_patient(patient_data)

                # Получаем объект записи из родительского класса
                appointment = super(AppointmentChainBaseForm, self).save(commit=False)
                appointment.patient = patient

                # Определяем, какой слот использовать
                allow_time_change = self.cleaned_data.get("allow_time_change", False)
                new_time_slot = self.cleaned_data.get("new_time_slot")

                if allow_time_change and new_time_slot:
                    appointment.time_slot = new_time_slot
                else:
                    appointment.time_slot = self.time_slot

                # Устанавливаем, что это основная запись в цепочке
                appointment.is_chain_main = True

                # Определяем тип цепочки
                appointment_chain_type = self.cleaned_data.get("appointment_chain_type")
                if appointment_chain_type == "two_slots":
                    appointment.chain_type = Appointment.ChainType.SAME_DOCTOR
                    appointment.occupies_two_slots = True
                elif appointment_chain_type in ["another_doctor", "multiple"]:
                    appointment.chain_type = Appointment.ChainType.MULTIPLE_DOCTORS
                else:
                    appointment.chain_type = Appointment.ChainType.SINGLE

                self._set_appointment_price(appointment)

                # Сохраняем общую сумму из формы (если есть)
                total_sum = self.cleaned_data.get("total_sum")
                if total_sum:
                    appointment.total_with_blood_tests = total_sum

                # ВАЖНО: Сохраняем основную запись сразу для получения ID
                appointment.save()

                if appointment_chain_type in ["another_doctor", "multiple"]:
                    if not appointment.comment:
                        appointment.comment = ""
                    # Добавляем пометку, что это основная запись в цепочке
                    chain_comment = f"Основная запись в цепочке"
                    if appointment.comment and chain_comment not in appointment.comment:
                        appointment.comment = f"{appointment.comment}\n{chain_comment}"
                    appointment.save()

                # ДОПОЛНИТЕЛЬНАЯ ПРОВЕРКА ПИЩЕЛЕВА для последовательных записей
                if appointment_chain_type == "two_slots":
                    self._validate_consecutive_for_pishchelev(
                        appointment, appointment_chain_type
                    )

                # ПРОВЕРКА: Процедурная запись для ОСНОВНОЙ записи (проверяем ДО создания)
                if self.cleaned_data.get("needs_procedural"):
                    if not ProceduralAppointmentService.can_create_procedural_appointment(
                        appointment
                    ):
                        raise forms.ValidationError(
                            "Невозможно создать запись: выбранное время в процедурном кабинете уже занято. "
                            "Пожалуйста, выберите другое время."
                        )

                # Только после всех проверок создаем остальные записи
                if self.cleaned_data.get("needs_procedural"):
                    procedural_appointment = (
                        ProceduralAppointmentService.create_procedural_appointment(
                            appointment
                        )
                    )
                    if procedural_appointment:
                        if not procedural_appointment.price_at_appointment:
                            procedural_appointment.price_at_appointment = (
                                procedural_appointment.service.price
                            )
                        procedural_appointment.total_with_blood_tests = (
                            procedural_appointment.price_at_appointment
                        )
                        procedural_appointment.save()

                # Обработка последовательных записей к тому же врачу (только для two_slots)
                if appointment_chain_type == "two_slots":  # УДАЛЕНО: additional
                    self._handle_consecutive_appointments(
                        appointment, appointment_chain_type
                    )

                # Обработка дополнительных записей к другим врачам
                if appointment_chain_type in ["another_doctor", "multiple"]:
                    self._handle_additional_appointments(appointment)

                return appointment

        except forms.ValidationError:
            raise
        except IntegrityError as e:
            if "unique_doctor_time_slot" in str(e):
                raise forms.ValidationError(
                    "Невозможно создать запись: выбранное время уже занято другим пациентом. "
                    "Пожалуйста, обновите страницу и выберите другое время."
                )
            raise

    @staticmethod
    def _set_appointment_price(appointment, service=None):
        """Устанавливает цену услуги для записи"""
        if not appointment.price_at_appointment:
            if service:
                appointment.price_at_appointment = service.price
            elif appointment.service:
                appointment.price_at_appointment = appointment.service.price

        # Устанавливает итоговую сумму
        if not appointment.total_with_blood_tests:
            appointment.total_with_blood_tests = appointment.price_at_appointment

    @staticmethod
    def _handle_consecutive_appointments(main_appointment, appointment_chain_type):
        """Обработка последовательных записей к тому же врачу (только для two_slots)"""
        if appointment_chain_type == "two_slots":  # УДАЛЕНО: additional
            try:
                # Используем сервис для создания последовательной записи
                ConsecutiveAppointmentService.create_consecutive_appointment(
                    main_appointment=main_appointment,
                    appointment_chain_type=appointment_chain_type,
                    additional_service=None,  # Для two_slots нет второй услуги
                )
            except ValidationError as e:
                # Перехватываем ValidationError и преобразуем в forms.ValidationError
                raise forms.ValidationError(str(e))

    def _handle_additional_appointments(self, main_appointment):
        """Обработка дополнительных записей к другим врачам"""
        appointment_chain_type = self.cleaned_data.get("appointment_chain_type")

        if appointment_chain_type in ["another_doctor", "multiple"]:
            additional_data = self.cleaned_data.get("additional_appointments_data")
            procedural_data = self.cleaned_data.get("procedural_appointments_data")

            if additional_data:
                try:
                    appointments_list = json.loads(additional_data)
                    procedural_list = (
                        json.loads(procedural_data) if procedural_data else []
                    )
                    additional_doctors = []
                    for i, appointment_data in enumerate(appointments_list, start=1):
                        if "insurance_type" not in appointment_data:
                            # Установить значение по умолчанию
                            appointment_data["insurance_type"] = "paid"

                        # Создаем запись
                        additional_appointment = self._create_additional_appointment(
                            main_appointment, appointment_data, i
                        )
                        # Добавляем врача в список для комментария основной записи
                        if additional_appointment.doctor:
                            additional_doctors.append(
                                additional_appointment.doctor.surname
                            )

                        # ПРОВЕРЯЕМ, ЕСТЬ ЛИ ПРОЦЕДУРНЫЕ ДАННЫЕ ДЛЯ ЭТОЙ ЗАПИСИ
                        procedural_info = None
                        if procedural_list:
                            # Ищем по индексу
                            for item in procedural_list:
                                if str(item.get("index")) == str(
                                    appointment_data.get("index")
                                ):
                                    procedural_info = item
                                    break

                        # Создаем процедурную запись если нужно (используем сервис)
                        if procedural_info and procedural_info.get("needs_procedural"):
                            ProceduralAppointmentService.create_procedural_for_appointment(
                                additional_appointment,
                                main_appointment=additional_appointment,
                            )

                    # ВАЖНО: Добавляем комментарий к ОСНОВНОЙ записи
                    if additional_doctors:
                        # Формируем комментарий с уникальными именами врачей
                        unique_doctors = []
                        for doctor in additional_doctors:
                            if doctor not in unique_doctors:
                                unique_doctors.append(doctor)

                        if len(unique_doctors) == 1:
                            chain_comment = f"Доп. запись к врачу {unique_doctors[0]}"
                        else:
                            doctors_str = ", ".join(unique_doctors)
                            chain_comment = f"Доп. записи к врачам: {doctors_str}"

                        # Добавляем только если еще нет такого комментария
                        current_comment = main_appointment.comment or ""

                        # Удаляем старые комментарии о цепочке (если они есть)
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

                        # Добавляем новый комментарий
                        if cleaned_comment:
                            main_appointment.comment = (
                                f"{cleaned_comment}\n{chain_comment}"
                            )
                        else:
                            main_appointment.comment = chain_comment

                        main_appointment.save()
                        print(
                            f"Добавлен комментарий к основной записи: {main_appointment.comment}"
                        )

                except (json.JSONDecodeError, KeyError) as e:
                    raise forms.ValidationError(
                        f"Ошибка обработки данных дополнительных записей: {str(e)}"
                    )

    def _create_additional_appointment(self, main_appointment, appointment_data, order):
        """Создание одной дополнительной записи с проверкой времени"""
        try:
            # Получаем объекты из данных
            doctor_id = appointment_data.get("doctor_id")
            service_id = appointment_data.get("service_id")
            time_slot_id = appointment_data.get("time_slot_id")
            comment = appointment_data.get("comment", "")
            insurance_type = appointment_data.get("insurance_type", "paid")

            if not all([doctor_id, service_id, time_slot_id]):
                raise ValueError("Не все обязательные поля заполнены")

            doctor = Doctor.objects.get(id=doctor_id)
            service = MedicalService.objects.get(id=service_id)
            time_slot = TimeSlot.objects.get(id=time_slot_id)

            # ВАЖНОЕ ДОБАВЛЕНИЕ: Проверка ограничений Пищелева
            if "пищелев" in doctor.surname.lower():
                from django.core.exceptions import ValidationError

                from appointments.utils import validate_pishchelev_restrictions

                try:
                    validate_pishchelev_restrictions(doctor, service, time_slot)
                except ValidationError as e:
                    raise forms.ValidationError(
                        f"Ошибка в дополнительной записи #{order} (к врачу {doctor.surname}): {str(e)}"
                    )

            # Проверяем, что дата дополнительной записи НЕ пересекается по времени с основной
            if time_slot.date == main_appointment.date:
                # Получаем время начала и окончания слотов
                main_start = main_appointment.start_time
                main_end = main_appointment.end_time
                add_start = time_slot.start_time
                add_end = time_slot.end_time

                # Функция для конвертации времени в минуты
                def time_to_minutes(t):
                    return t.hour * 60 + t.minute + t.second / 60

                main_start_minutes = time_to_minutes(main_start)
                main_end_minutes = time_to_minutes(main_end)
                add_start_minutes = time_to_minutes(add_start)
                add_end_minutes = time_to_minutes(add_end)

                # Проверяем пересечение времени
                # Два интервала пересекаются, если:
                # add_start < main_end И add_end > main_start
                is_overlapping = (
                    add_start_minutes < main_end_minutes
                    and add_end_minutes > main_start_minutes
                )

                if is_overlapping:
                    raise forms.ValidationError(
                        f"Ошибка: Время дополнительной записи пересекается с основной записью.\n"
                        f"Основная запись: {main_appointment.date.strftime('%d.%m.%Y')} "
                        f"{main_start.strftime('%H:%M')}-{main_end.strftime('%H:%M')}\n"
                        f"Дополнительная запись: {time_slot.date.strftime('%d.%m.%Y')} "
                        f"{add_start.strftime('%H:%M')}-{add_end.strftime('%H:%M')}\n\n"
                        f"Выберите другое время для дополнительной записи."
                    )

            # Проверяем доступность слота
            if not time_slot.is_available():
                raise forms.ValidationError(
                    f"Слот {time_slot.start_time} у врача {doctor.surname} уже занят"
                )

            # ВАЖНО: Создаем комментарий для дополнительной записи
            main_doctor_surname = main_appointment.doctor.surname
            additional_comment = comment or f"Доп. запись к врачу {main_doctor_surname}"

            # Создаем дополнительную запись
            additional_appointment = Appointment.objects.create(
                time_slot=time_slot,
                patient=main_appointment.patient,
                service=service,
                insurance_type=insurance_type,
                status=main_appointment.status,
                comment=additional_comment,  # Используем сформированный комментарий
                chain_type=Appointment.ChainType.MULTIPLE_DOCTORS,
                is_chain_main=False,
            )

            # Сохраняем цену
            self._set_appointment_price(additional_appointment, service)

            # Создаем связь
            chain = AppointmentChain.objects.create(
                main_appointment=main_appointment,
                related_appointment=additional_appointment,
                chain_type=AppointmentChain.ChainType.ANOTHER_DOCTOR,
                order=order,
            )

            return additional_appointment

        except (
            Doctor.DoesNotExist,
            MedicalService.DoesNotExist,
            TimeSlot.DoesNotExist,
        ) as e:
            raise forms.ValidationError(
                f"Ошибка создания дополнительной записи: {str(e)}"
            )


class AppointmentSimpleEditForm(forms.ModelForm):
    """Упрощенная форма редактирования записи с исправленной валидацией"""

    # УДАЛЯЕМ старые поля выбора даты и времени
    # new_appointment_date = forms.DateField(...) - УДАЛЯЕМ

    # ЗАМЕНА на поля для изменения времени (как при создании записи)
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

        if self.appointment:
            # Ограничиваем услуги только для этого врача
            self.fields["service"].queryset = get_cached_doctor_services(
                self.appointment.doctor
            )

            # Инициализируем поля изменения времени
            if self.appointment.time_slot:
                self.fields["new_time_slot_id"].initial = self.appointment.time_slot.id
                self.fields["new_appointment_date"].initial = self.appointment.date
                # Проверяем, есть ли уже процедурная запись
            procedural_exists = Appointment.objects.filter(
                previous_appointment=self.appointment,
                time_slot__cabinet__number=6,
            ).exists()

            # Если процедурная запись уже есть, делаем чекбокс отмеченным и неактивным
            if procedural_exists:
                self.fields["needs_procedural"].initial = True
                self.fields["needs_procedural"].widget.attrs.update(
                    {"disabled": "disabled", "title": "Процедурная запись уже создана"}
                )

    def clean(self):
        cleaned_data = super().clean()

        # Проверяем, разрешено ли изменение времени
        allow_time_change = cleaned_data.get("allow_time_change", False)
        new_time_slot_id = cleaned_data.get("new_time_slot_id")

        if allow_time_change and new_time_slot_id:
            try:
                # Получаем новый слот
                new_time_slot = TimeSlot.objects.get(id=new_time_slot_id)

                # Проверяем доступность
                if not new_time_slot.is_available():
                    # Проверяем, не занят ли он текущей записью
                    current_appointment_in_slot = new_time_slot.appointments.filter(
                        id=self.appointment.id
                    ).exists()

                    if not current_appointment_in_slot:
                        raise forms.ValidationError(
                            "Выбранный временной слот уже занят другим пациентом. "
                            "Пожалуйста, выберите другой слот."
                        )

                # Проверяем, что слот принадлежит тому же врачу
                if new_time_slot.doctor != self.appointment.doctor:
                    raise forms.ValidationError(
                        "Выбранный слот не принадлежит текущему врачу."
                    )

                # Проверяем дату слота
                new_date = cleaned_data.get("new_appointment_date")
                if new_date and new_time_slot.date != new_date:
                    raise forms.ValidationError(
                        "Дата нового слота не совпадает с выбранной датой."
                    )

                # Сохраняем объект слота для использования в save()
                cleaned_data["new_time_slot"] = new_time_slot

            except TimeSlot.DoesNotExist:
                raise forms.ValidationError("Выбранный временной слот не существует")

                # Проверяем процедурную запись если меняется время или выбрана услуга медблокады
        if cleaned_data.get("needs_procedural") or self._is_medical_blockade_service(
            cleaned_data.get("service")
        ):
            self._validate_procedural_availability(cleaned_data)
        # Проверяем процедурную запись если меняется время
        if allow_time_change and new_time_slot_id:
            self._validate_procedural_availability(cleaned_data)

        return cleaned_data

    def _is_medical_blockade_service(self, service):
        """Проверяет, является ли услуга медицинской блокадой"""
        if not service:
            return False

        # Проверяем по категории
        from timetable.models import MedicalServiceCategory

        if service.category == MedicalServiceCategory.MEDICAL_BLOCKADES:
            return True

        # Проверяем по названию
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
        # Определяем, какой слот проверять
        time_slot_to_check = None
        if cleaned_data.get("allow_time_change") and cleaned_data.get("new_time_slot"):
            time_slot_to_check = cleaned_data.get("new_time_slot")
        else:
            time_slot_to_check = self.appointment.time_slot

        if not time_slot_to_check:
            return

        # Находим процедурный кабинет
        procedural_cabinet = get_procedural_cabinet()

        # Проверяем доступность времени в процедурном кабинете
        conflicting_slots = TimeSlot.objects.filter(
            date=time_slot_to_check.date,
            cabinet=procedural_cabinet,
            start_time__lt=time_slot_to_check.end_time,
            end_time__gt=time_slot_to_check.start_time,
            appointments__isnull=False,
        )

        # Исключаем нашу процедурную запись из проверки
        procedural_appointment = Appointment.objects.filter(
            previous_appointment=self.appointment,
            time_slot__cabinet__number=6,
        ).first()

        if procedural_appointment and procedural_appointment.time_slot:
            conflicting_slots = conflicting_slots.exclude(
                id=procedural_appointment.time_slot_id
            )

        if conflicting_slots.exists():
            occupied_slot = conflicting_slots.first()
            patient_name = occupied_slot.appointments.first().patient.get_full_name()

            raise forms.ValidationError(
                f"Невозможно создать процедурную запись: время {time_slot_to_check.start_time.strftime('%H:%M')}-"
                f"{time_slot_to_check.end_time.strftime('%H:%M')} {time_slot_to_check.date.strftime('%d.%m.%Y')} "
                f"в процедурном кабинете уже занято пациентом {patient_name}. "
                f"Пожалуйста, выберите другое время или снимите галочку 'Занять окошко в процедурном кабинете'."
            )

    @transaction.atomic
    def save(self, commit=True):
        """Сохраняет запись с проверкой процедурного кабинета"""
        appointment = super().save(commit=False)
        service_changed = False
        if self.instance.pk:
            original_service = self.instance.service
            new_service = self.cleaned_data.get("service") or appointment.service
            if original_service != new_service:
                service_changed = True

        # Проверяем, нужно ли создать процедурную запись
        needs_procedural = self.cleaned_data.get("needs_procedural", False)
        service = self.cleaned_data.get("service") or appointment.service

        # Автоматически ставим галочку, если выбрана услуга медблокады
        if self._is_medical_blockade_service(service) and not needs_procedural:
            needs_procedural = True

        if commit:
            try:
                # Сохраняем запись с новым временным слотом если он изменился
                allow_time_change = self.cleaned_data.get("allow_time_change", False)
                new_time_slot = self.cleaned_data.get("new_time_slot")

                if allow_time_change and new_time_slot:
                    old_time_slot = appointment.time_slot
                    appointment.time_slot = new_time_slot

                    # Переносим процедурную запись если она есть
                    if old_time_slot.id != new_time_slot.id:
                        self._move_procedural_appointment(
                            appointment, old_time_slot, new_time_slot
                        )

                # Сохраняем основную запись
                appointment.save()

                # Обрабатываем процедурную запись
                self._handle_procedural_appointment(appointment, needs_procedural)
                if service_changed and hasattr(self, "_update_procedural_service"):
                    self._update_procedural_service(appointment)

            except forms.ValidationError as e:
                raise forms.ValidationError(str(e))

        return appointment

    def _handle_procedural_appointment(self, appointment, needs_procedural):
        """Обрабатывает создание/обновление процедурной записи"""
        from appointments.services import ProceduralAppointmentService

        # Проверяем, есть ли уже процедурная запись
        existing_procedural = Appointment.objects.filter(
            previous_appointment=appointment,
            time_slot__cabinet__number=6,
        ).first()

        if needs_procedural:
            # Нужно создать или обновить процедурную запись
            if not existing_procedural:
                # Проверяем, можно ли создать
                if not ProceduralAppointmentService.can_create_procedural_appointment(
                    appointment
                ):
                    raise forms.ValidationError(
                        "Невозможно создать процедурную запись: выбранное время в процедурном кабинете уже занято. "
                        "Пожалуйста, выберите другое время или снимите галочку 'Занять окошко в процедурном кабинете'."
                    )

                # Создаем новую процедурную запись
                ProceduralAppointmentService.create_procedural_appointment(appointment)
            else:
                # Обновляем существующую процедурную запись
                ProceduralAppointmentService.update_procedural_appointment(
                    appointment, existing_procedural
                )
        elif existing_procedural:
            # Если процедурная запись существует, но галочка снята - удаляем ее
            old_slot = existing_procedural.time_slot
            existing_procedural.delete()

            # Удаляем пустой слот процедурного кабинета
            if old_slot and not old_slot.appointments.exists():
                old_slot.delete()

    def _move_procedural_appointment(self, appointment, old_time_slot, new_time_slot):
        """Переносит связанную процедурную запись на новое время"""

        # Ищем процедурную запись
        procedural_appointment = Appointment.objects.filter(
            previous_appointment=appointment,
            time_slot__cabinet__number=6,
        ).first()

        if not procedural_appointment:
            return

        # Находим процедурный кабинет
        procedural_cabinet = get_procedural_cabinet()

        # Находим или создаем слот в процедурном кабинете на НОВОЕ время
        procedural_time_slot, created = TimeSlot.objects.get_or_create(
            doctor=procedural_appointment.doctor or appointment.doctor,
            cabinet=procedural_cabinet,
            date=new_time_slot.date,
            start_time=new_time_slot.start_time,
            end_time=new_time_slot.end_time,
            defaults={"slot_type": "working", "description": "Процедурный кабинет"},
        )

        # Проверяем, не занят ли этот слот другой записью
        if not created and procedural_time_slot.appointments.exists():
            other_appointment = procedural_time_slot.appointments.exclude(
                id=procedural_appointment.id
            ).first()

            if other_appointment:
                error_msg = (
                    f"Невозможно перенести запись: время в процедурном кабинете уже занято записью "
                    f"#{other_appointment.id} для пациента {other_appointment.patient.get_full_name()}."
                )
                raise forms.ValidationError(error_msg)

        # Сохраняем старый слот для удаления
        old_procedural_slot = procedural_appointment.time_slot

        # Обновляем слот процедурной записи
        procedural_appointment.time_slot = procedural_time_slot
        # НЕ пытаемся установить procedural_appointment.date - это тоже property

        # Обновляем комментарий с именем врача
        if procedural_appointment.comment != appointment.doctor.surname:
            procedural_appointment.comment = appointment.doctor.surname

        procedural_appointment.save()

        # Удаляем старый пустой слот
        if old_procedural_slot and not old_procedural_slot.appointments.exists():
            old_procedural_slot.delete()

    def _update_procedural_service(self, appointment):
        """Всегда обновляет услугу в процедурной записи на ту же что и в основной записи"""

        # Находим процедурную запись
        procedural_appointment = Appointment.objects.filter(
            previous_appointment=appointment,
            time_slot__cabinet__number=6,
        ).first()

        if not procedural_appointment:
            return

        # Всегда обновляем на ту же услугу что и в основной записи
        if appointment.service:
            procedural_appointment.service = appointment.service
            procedural_appointment.price_at_appointment = appointment.service.price
            procedural_appointment.save()
        else:
            print("DEBUG: Appointment has no service, cannot update procedural")


class ProceduralAppointmentForm(ProceduralAppointmentBaseForm, forms.ModelForm):
    """Форма создания записи в процедурный кабинет с поддержкой цепочек"""

    class Meta:
        model = Appointment
        fields = ["service", "insurance_type", "needs_reschedule", "comment"]

    def __init__(self, *args, **kwargs):
        self.selected_date = kwargs.pop("selected_date", None)

        # Убираем doctor и time_slot из kwargs, так как они не нужны для процедурной формы
        doctor = None  # Для процедурного кабинета - это медсестра
        time_slot = None

        # Вызываем инициализацию родительских классов отдельно
        forms.ModelForm.__init__(self, *args, **kwargs)
        ProceduralAppointmentBaseForm.__init__(
            self,
            *args,
            **kwargs,
            doctor=doctor,
            time_slot=time_slot,
            selected_date=self.selected_date,
        )

        # Устанавливаем сегодняшнюю дату как дефолтную
        if not self.selected_date:
            self.selected_date = timezone.now().date()

        # Устанавливаем тип оплаты по умолчанию как "платный"
        self.fields["insurance_type"].initial = "paid"
        # Обновляем queryset для услуги
        self._update_service_queryset()

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

    @transaction.atomic
    def save(self, commit=True):
        """Сохраняет процедурную запись с проверкой времени"""

        # Получаем данные для процедурной записи
        date = (
            self.cleaned_data.get("procedural_appointment_date") or self.selected_date
        )
        start_time = self.cleaned_data.get("procedural_start_time")
        end_time = self.cleaned_data.get("procedural_end_time")

        # Проверяем обязательные поля для процедурной записи
        if not all([date, start_time, end_time]):
            raise forms.ValidationError(
                "Для создания процедурной записи необходимо указать дату, время начала и окончания"
            )

        # Устанавливаем значение по умолчанию для типа оплаты
        if not self.cleaned_data.get("insurance_type"):
            self.cleaned_data["insurance_type"] = "paid"

        # Создаем объект записи, но еще не сохраняем в БД
        appointment = super().save(commit=False)

        # СОЗДАЕМ ИЛИ НАХОДИМ ПАЦИЕНТА
        try:
            patient_data = self.get_patient_data()

            # Проверяем, что есть основные данные пациента
            if not patient_data.get("surname") or not patient_data.get("first_name"):
                raise forms.ValidationError("Необходимо указать фамилию и имя пациента")

            # Используем сервис для создания/поиска пациента
            from patients.services import PatientService

            patient, created = PatientService.get_or_create_patient(patient_data)

            if not patient:
                raise forms.ValidationError("Не удалось создать или найти пациента")

            appointment.patient = patient

        except Exception as e:
            raise forms.ValidationError(f"Ошибка обработки данных пациента: {str(e)}")

        # Находим или создаем временной слот для процедурного кабинета
        from appointments.services import ProceduralAppointmentService
        from appointments.utils_for_caches import get_procedural_cabinet

        procedural_cabinet = get_procedural_cabinet()

        # Получаем врача-медсестру
        nurse_doctor = Doctor.objects.filter(specialization="nurse").first()
        if not nurse_doctor:
            raise forms.ValidationError("Врач-медсестра не найден")

        # Создаем или находим слот С УКАЗАННЫМ ВРАЧОМ
        time_slot = ProceduralAppointmentService.create_or_get_procedural_slot(
            date=date,
            start_time=start_time,
            end_time=end_time,
            doctor=nurse_doctor,  # Указываем врача-медсестру
        )

        # Проверяем доступность слота
        if time_slot.appointments.exists():
            # Проверяем, не пытаемся ли мы обновить существующую запись
            if not (
                self.instance
                and self.instance.pk
                and self.instance.time_slot_id == time_slot.id
            ):
                raise forms.ValidationError(
                    f"Процедурный кабинет в это время уже занят. "
                    f"Время: {start_time.strftime('%H:%M')}-{end_time.strftime('%H:%M')} "
                    f"Дата: {date.strftime('%d.%m.%Y')}"
                )

        # Назначаем слот записи
        appointment.time_slot = time_slot
        # НЕ устанавливаем appointment.doctor - это property, которое берется из time_slot.doctor

        # Устанавливаем тип оплаты (по умолчанию платный)
        if not appointment.insurance_type:
            appointment.insurance_type = "paid"

        # Устанавливаем статус
        appointment.status = Appointment.AppointmentStatus.SCHEDULED

        # Устанавливаем цену услуги
        if appointment.service and not appointment.price_at_appointment:
            appointment.price_at_appointment = appointment.service.price

        # Обрабатываем анализы крови
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
            except (ValueError, TypeError):
                raise forms.ValidationError("Неверный формат выбранных анализов")

        # Рассчитываем общую сумму
        total_sum = self.cleaned_data.get("total_sum")
        if not total_sum:
            # Рассчитываем сумму анализов
            tests_price = 0
            if selected_test_ids:
                from timetable.models import BloodTest

                tests_price = sum(
                    BloodTest.objects.filter(id__in=selected_test_ids).values_list(
                        "price", flat=True
                    )
                )

            # Сумма услуги
            service_price = appointment.price_at_appointment or 0
            total_sum = tests_price + service_price

        appointment.total_with_blood_tests = total_sum

        # Сохраняем запись
        if commit:
            appointment.save()

            # Добавляем анализы крови
            if selected_test_ids:
                from appointments.models import AppointmentBloodTest

                # Удаляем старые связи
                AppointmentBloodTest.objects.filter(appointment=appointment).delete()

                # Добавляем новые
                for test_id in selected_test_ids:
                    AppointmentBloodTest.objects.create(
                        appointment=appointment, blood_test_id=test_id
                    )

            # Обновляем комментарий если есть анализы
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

        return appointment

    def _check_procedural_time_availability(self, start_time, end_time):
        """Проверяет доступность времени в процедурном кабинете"""
        try:

            date = self.selected_date or timezone.now().date()
            procedural_cabinet = get_procedural_cabinet()

            # Проверяем конфликтующие слоты в процедурном кабинете
            from timetable.models import TimeSlot

            conflicting_slots = TimeSlot.get_conflicting_slots(
                date=date,
                start_time=start_time,
                end_time=end_time,
                cabinet=procedural_cabinet,
            ).filter(appointments__isnull=False)

            return not conflicting_slots.exists()

        except Exception:
            return False

    def _create_procedural_slot(self, start_time, end_time):
        """Создает или находит существующий временной слот для процедурного кабинета"""

        date = self.selected_date or timezone.now().date()

        time_slot = ProceduralAppointmentService.create_or_get_procedural_slot(
            date=date,
            start_time=start_time,
            end_time=end_time,
            doctor=None,  # Для процедурного кабинета врач - медсестра
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

            if not all([doctor_id, service_id, time_slot_id]):
                return

            time_slot = TimeSlot.objects.get(id=time_slot_id)

            # Проверяем доступность слота
            if not time_slot.is_available():
                raise forms.ValidationError(
                    f"Ошибка в дополнительной записи #{order}: "
                    f"Слот {time_slot.start_time} уже занят. "
                    "Пожалуйста, выберите другое время."
                )

        except TimeSlot.DoesNotExist:
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

                # Сохраняем выбранные анализы
                for test in selected_blood_tests:
                    AppointmentBloodTest.objects.create(
                        appointment=appointment, blood_test=test
                    )

                # Обновляем комментарий с информацией об анализах
                self._update_appointment_comment(appointment, selected_blood_tests)

            except (ValueError, TypeError):
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

    def _handle_additional_appointments(self, main_appointment):
        """Обработка дополнительных записей к другим врачам (общая логика)"""
        appointment_chain_type = self.cleaned_data.get("appointment_chain_type")

        if appointment_chain_type in ["another_doctor", "multiple"]:
            additional_data = self.cleaned_data.get("additional_appointments_data")
            procedural_data = self.cleaned_data.get("procedural_appointments_data")

            if additional_data:
                try:
                    appointments_list = json.loads(additional_data)
                    procedural_list = (
                        json.loads(procedural_data) if procedural_data else []
                    )

                    for i, appointment_data in enumerate(appointments_list, start=1):
                        # Создаем запись
                        additional_appointment = self._create_additional_appointment(
                            main_appointment, appointment_data, i
                        )

                        # Проверяем, есть ли процедурные данные для этой записи
                        procedural_info = None
                        if procedural_list:
                            for item in procedural_list:
                                if str(item.get("index")) == str(
                                    appointment_data.get("index")
                                ):
                                    procedural_info = item
                                    break

                        # Создаем процедурную запись если нужно
                        if procedural_info and procedural_info.get("needs_procedural"):
                            ProceduralAppointmentService.create_procedural_for_appointment(
                                additional_appointment,
                                main_appointment=additional_appointment,
                            )

                except (json.JSONDecodeError, KeyError) as e:
                    raise forms.ValidationError(
                        f"Ошибка обработки данных дополнительных записей: {str(e)}"
                    )

    def _create_additional_appointment(self, main_appointment, appointment_data, order):
        """Создание одной дополнительной записи (общая логика)"""
        try:
            # Получаем объекты из данных
            doctor_id = appointment_data.get("doctor_id")
            service_id = appointment_data.get("service_id")
            time_slot_id = appointment_data.get("time_slot_id")
            comment = appointment_data.get("comment", "")
            insurance_type = appointment_data.get("insurance_type", "paid")

            if not all([doctor_id, service_id, time_slot_id]):
                raise ValueError("Не все обязательные поля заполнены")

            doctor = Doctor.objects.get(id=doctor_id)
            service = MedicalService.objects.get(id=service_id)
            time_slot = TimeSlot.objects.get(id=time_slot_id)

            # Проверяем доступность слота (повторная проверка для надежности)
            if not time_slot.is_available():
                raise forms.ValidationError(
                    f"Слот {time_slot.start_time} у врача {doctor.surname} уже занят"
                )

            # Создаем дополнительную запись
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

            # Сохраняем цену
            additional_appointment.price_at_appointment = service.price
            additional_appointment.total_with_blood_tests = service.price
            additional_appointment.save()

            # Создаем связь
            AppointmentChain.objects.create(
                main_appointment=main_appointment,
                related_appointment=additional_appointment,
                chain_type=AppointmentChain.ChainType.ANOTHER_DOCTOR,
                order=order,
            )

            return additional_appointment

        except (
            Doctor.DoesNotExist,
            MedicalService.DoesNotExist,
            TimeSlot.DoesNotExist,
        ) as e:
            raise forms.ValidationError(
                f"Ошибка создания дополнительной записи: {str(e)}"
            )

    def _set_appointment_price(self, appointment):
        """Устанавливает цену услуги для записи"""
        if not appointment.price_at_appointment and appointment.service:
            appointment.price_at_appointment = appointment.service.price

        # Устанавливаем итоговую сумму
        if not appointment.total_with_blood_tests:
            appointment.total_with_blood_tests = appointment.price_at_appointment


class ProceduralAppointmentUpdateForm(forms.ModelForm):
    """Упрощенная форма для редактирования процедурной записи - только основные поля"""

    # ДОБАВЛЯЕМ поле для даты
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
        # Устанавливаем минимальную дату - сегодня
        from django.utils import timezone

        today = timezone.now().date()
        self.fields["procedural_appointment_date"].widget.attrs[
            "min"
        ] = today.isoformat()

        # Устанавливаем начальные значения
        if self.current_appointment and self.instance.pk:
            self._set_initial_values()

            # Обновляем queryset для услуги
            self._update_service_queryset()

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

    def _set_initial_values(self):
        """Устанавливает начальные значения для формы"""

        # 1. Устанавливаем дату
        if self.current_appointment.date:
            self.fields["procedural_appointment_date"].initial = (
                self.current_appointment.date
            )

        # 2. Устанавливаем анализы крови
        selected_tests = self.current_appointment.selected_blood_tests.all()
        if selected_tests.exists():
            test_ids = [str(test.blood_test.id) for test in selected_tests]
            self.fields["selected_blood_tests_input"].initial = ",".join(test_ids)

        # 3. Устанавливаем сумму
        if self.current_appointment.total_with_blood_tests:
            self.fields["total_sum"].initial = (
                self.current_appointment.total_with_blood_tests
            )

        # 4. Устанавливаем время
        if self.current_appointment.start_time:
            self.fields["procedural_start_time"].initial = (
                self.current_appointment.start_time.strftime("%H:%M")
            )
        if self.current_appointment.end_time:
            self.fields["procedural_end_time"].initial = (
                self.current_appointment.end_time.strftime("%H:%M")
            )

        # 5. Устанавливаем услугу
        if self.current_appointment.service:
            self.fields["service"].initial = self.current_appointment.service

    def clean(self):
        """Переопределяем clean для отладки"""
        cleaned_data = super().clean()

        # Валидация времени
        start_time = cleaned_data.get("procedural_start_time")
        end_time = cleaned_data.get("procedural_end_time")
        appointment_date = cleaned_data.get("procedural_appointment_date")

        if start_time and end_time and start_time >= end_time:
            raise forms.ValidationError(
                "Время окончания должно быть позже времени начала"
            )

        # Проверка доступности времени в процедурном кабинете
        if appointment_date and start_time and end_time:
            if not self._check_procedural_time_availability(
                appointment_date, start_time, end_time
            ):
                raise forms.ValidationError(
                    "Выбранное время в процедурном кабинете уже занято. "
                    "Пожалуйста, выберите другое время."
                )

        # ВАЖНО: Если нет анализов, устанавливаем пустую строку
        if not cleaned_data.get("selected_blood_tests_input"):
            cleaned_data["selected_blood_tests_input"] = ""

        # ВАЖНО: Если нет суммы, пытаемся ее рассчитать
        if not cleaned_data.get("total_sum"):
            # Пытаемся рассчитать сумму на основе выбранных тестов и услуги
            try:
                service = (
                    cleaned_data.get("service") or self.current_appointment.service
                )
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
                service_price = service.price if service else 0
                total = tests_price + service_price

                cleaned_data["total_sum"] = total
            except Exception:
                cleaned_data["total_sum"] = 0

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

            # Исключаем текущую запись из проверки
            if self.current_appointment and self.current_appointment.time_slot:
                conflicting_slots = conflicting_slots.exclude(
                    id=self.current_appointment.time_slot_id
                )

            return not conflicting_slots.exists()

        except Exception as e:
            print(f"ERROR in time availability check: {str(e)}")
            return False

    @transaction.atomic
    def save(self, commit=True):
        """Переопределяем save для ОБНОВЛЕНИЯ существующей записи"""
        # ОБНОВЛЕНИЕ существующей записи
        appointment = self.instance

        # 1. Получаем новые дату и время
        new_date = self.cleaned_data.get("procedural_appointment_date")
        start_time = self.cleaned_data.get("procedural_start_time")
        end_time = self.cleaned_data.get("procedural_end_time")

        # 2. Проверяем, изменились ли дата или время
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

        # 3. Если дата или время изменились, создаем/ищем новый слот
        if date_changed or time_changed:

            # Создаем новый слот или используем существующий
            from appointments.services import ProceduralAppointmentService

            time_slot = ProceduralAppointmentService.create_or_get_procedural_slot(
                date=new_date,  # Используем новую дату
                start_time=start_time,
                end_time=end_time,
                doctor=appointment.doctor,
            )

            # Проверяем доступность (кроме текущей записи)
            if time_slot.id != appointment.time_slot_id:
                if time_slot.appointments.exclude(id=appointment.id).exists():
                    raise forms.ValidationError(
                        "Выбранное время уже занято другой записью. Пожалуйста, выберите другое время."
                    )

            appointment.time_slot = time_slot

        # 4. Обновляем остальные поля
        appointment.service = self.cleaned_data.get("service") or appointment.service
        appointment.insurance_type = (
            self.cleaned_data.get("insurance_type") or appointment.insurance_type
        )

        # 5. Сохраняем комментарий
        user_comment = self.cleaned_data.get("comment", "")
        if user_comment != appointment.comment:
            appointment.comment = user_comment

        # 6. Устанавливаем цену услуги
        if appointment.service and not appointment.price_at_appointment:
            appointment.price_at_appointment = appointment.service.price

        # 7. УДАЛИТЕ весь блок с form_total_sum и замените на:
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

        service_price = appointment.price_at_appointment or (
            appointment.service.price if appointment.service else 0
        )
        appointment.total_with_blood_tests = tests_price + service_price

        # 8. Сохраняем запись
        if commit:
            appointment.save()

            # 9. Обновляем анализы крови
            self._update_blood_tests(appointment)
            appointment.save()

        return appointment

    def _update_blood_tests(self, appointment):
        """Обновляет выбранные анализы крови"""
        selected_blood_tests_input = self.cleaned_data.get(
            "selected_blood_tests_input", ""
        )

        # Удаляем все текущие связи
        appointment.selected_blood_tests.all().delete()

        if selected_blood_tests_input and selected_blood_tests_input.strip():
            try:
                # Парсим ID анализов
                test_ids = [
                    int(id.strip())
                    for id in selected_blood_tests_input.split(",")
                    if id.strip() and id.strip().isdigit()
                ]

                # Добавляем новые
                for test_id in test_ids:
                    AppointmentBloodTest.objects.create(
                        appointment=appointment, blood_test_id=test_id
                    )

            except (ValueError, TypeError) as e:
                print(f"ERROR parsing test IDs: {str(e)}")


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

        # Устанавливаем минимальную дату - сегодня
        today = timezone.now().date()
        self.fields["appointment_date"].widget.attrs["min"] = today.isoformat()

        # Устанавливаем начальные значения если есть
        if self.initial_doctor:
            self.fields["doctor"].initial = self.initial_doctor
            self.set_service_queryset(self.initial_doctor)

        if self.initial_date:
            self.fields["appointment_date"].initial = self.initial_date

    def set_service_queryset(self, doctor):
        """Устанавливает queryset услуг для выбранного врача"""
        if doctor:
            # Используем сервис для инициализации queryset
            from appointments.services import AppointmentService

            # Создаем временный объект формы для использования сервиса
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

    def set_time_slot_queryset(self, doctor, date):
        """Устанавливает queryset слотов для выбранного врача и даты"""

        if doctor and date:
            # Получаем доступные слоты
            available_slots = TimeSlot.objects.filter(
                doctor=doctor,
                date=date,
                slot_type="working",
                appointments__isnull=True,  # Только свободные слоты
            ).order_by("start_time")

            self.fields["time_slot"].queryset = available_slots
            if available_slots.exists():
                self.fields["time_slot"].widget.attrs.pop("disabled", None)
            else:
                self.fields["time_slot"].widget.attrs["disabled"] = "disabled"
                self.fields["time_slot"].queryset = TimeSlot.objects.none()

    def clean(self):
        cleaned_data = super().clean()

        doctor = cleaned_data.get("doctor")
        appointment_date = cleaned_data.get("appointment_date")
        time_slot = cleaned_data.get("time_slot")

        # Проверяем, что все обязательные поля есть
        if not doctor or not appointment_date or not time_slot:
            return cleaned_data

        # Проверяем, что слот принадлежит выбранному врачу
        if time_slot.doctor != doctor:
            raise ValidationError("Выбранный слот не принадлежит выбранному врачу")

        # Проверяем, что слот на выбранную дату
        if time_slot.date != appointment_date:
            raise ValidationError("Выбранный слот не на выбранную дату")

        # Проверяем, что слот свободен
        if not time_slot.is_available():
            raise ValidationError("Выбранный слот уже занят")

        return cleaned_data
