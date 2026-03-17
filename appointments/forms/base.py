import json
import logging
from timetable.services import get_service_price_on_date
from django import forms
from django.core.exceptions import ValidationError

from appointments.mixins import AppointmentFormMixin, PatientFieldsMixin
from appointments.models import Appointment
from appointments.utils_for_caches import get_cached_doctor_services
from appointments.validators import AppointmentValidator
from timetable.mixins import StyleFormMixin  # ServiceBasedFormMixin,
from timetable.models import MedicalService

logger = logging.getLogger(__name__)


class AppointmentChainBaseForm(
    StyleFormMixin,
    PatientFieldsMixin,
    AppointmentFormMixin,
    forms.ModelForm,
):
    """Базовая форма для записей с поддержкой цепочек"""

    class Meta:
        model = Appointment
        fields = []  # Будем определять в дочерних формах

    # Основные поля (будут переопределены в дочерних формах)
    service = forms.ModelChoiceField(
        queryset=MedicalService.objects.none(),
        widget=forms.Select(attrs={"class": "form-select"}),
        label="Услуга",
    )

    insurance_type = forms.ChoiceField(
        choices=Appointment.InsuranceType.choices,
        widget=forms.Select(attrs={"class": "form-select"}),
        label="Тип оплаты",
    )

    # Поля для цепочек записей
    appointment_chain_type = forms.ChoiceField(
        choices=AppointmentFormMixin.APPOINTMENT_CHOICES,
        initial="none",
        widget=forms.RadioSelect(),
        label="Тип записи",
    )

    additional_service = forms.ModelChoiceField(
        queryset=MedicalService.objects.none(),
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
        label="Вторая услуга",
    )

    # Поля для записей к другим врачам
    additional_appointments_data = forms.CharField(
        required=False,
        widget=forms.HiddenInput(attrs={"id": "id_additional_appointments_data"}),
        label="Данные дополнительных записей",
    )

    # Поля для процедурных записей в цепочке
    procedural_appointments_data = forms.CharField(
        required=False,
        widget=forms.HiddenInput(attrs={"id": "id_procedural_appointments_data"}),
        label="Данные процедурных записей",
    )

    needs_procedural = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
        label="Занять окошко в процедурном кабинете",
        help_text="Автоматически займет такое же время в процедурном кабинете",
    )

    # Общие поля
    needs_reschedule = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
        label="Требуется перезапись на более ранний срок",
    )

    comment = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3, "class": "form-control"}),
        label="Комментарий",
    )

    total_sum = forms.DecimalField(
        required=False,
        widget=forms.HiddenInput(attrs={"id": "id_total_sum"}),
        decimal_places=2,
        max_digits=10,
        label="Итоговая сумма",
    )

    def __init__(self, *args, **kwargs):
        self.time_slot = kwargs.pop("time_slot", None)
        self.doctor = kwargs.pop("doctor", None)
        super().__init__(*args, **kwargs)

        logger.info(
            "Инициализация AppointmentChainBaseForm: form=%s instance_id=%s doctor_id=%s time_slot_id=%s",
            self.__class__.__name__,
            getattr(getattr(self, "instance", None), "id", None),
            getattr(self.doctor, "id", None),
            getattr(self.time_slot, "id", None),
        )

        self._set_initial_appointment_chain_type()
        self._initialize_service_queryset()

    def _set_initial_appointment_chain_type(self):
        """Устанавливает начальное значение для типа цепочки записей"""
        if hasattr(self, "instance") and self.instance and self.instance.pk:
            if self.instance.chain_type == Appointment.ChainType.MULTIPLE_DOCTORS:
                self.fields["appointment_chain_type"].initial = "multiple"
            elif self.instance.chain_type == Appointment.ChainType.SAME_DOCTOR:
                if self.instance.occupies_two_slots:
                    self.fields["appointment_chain_type"].initial = "two_slots"
            else:
                self.fields["appointment_chain_type"].initial = "none"

            logger.info(
                "Установлен initial appointment_chain_type: form=%s instance_id=%s chain_type=%s initial=%s",
                self.__class__.__name__,
                self.instance.id,
                self.instance.chain_type,
                self.fields["appointment_chain_type"].initial,
            )

    def _initialize_service_queryset(self):
        """Инициализирует queryset услуг"""
        doctor_to_use = self.doctor or (
            self.time_slot.doctor if self.time_slot else None
        )

        visit_date = None
        if self.time_slot:
            visit_date = self.time_slot.date
        elif getattr(self.instance, "time_slot", None):
            visit_date = self.instance.time_slot.date

        if doctor_to_use:
            services = doctor_to_use.get_available_services()
            self.fields["service"].queryset = services
            self.fields["additional_service"].queryset = services

            def _label(service_obj):
                if visit_date:
                    price = get_service_price_on_date(service_obj, visit_date)
                else:
                    price = service_obj.price
                return f"{service_obj.name} ({price} руб.)"

            self.fields["service"].label_from_instance = _label
            self.fields["additional_service"].label_from_instance = _label

            logger.info(
                "Инициализирован queryset услуг: form=%s doctor_id=%s visit_date=%s services_count=%s",
                self.__class__.__name__,
                doctor_to_use.id,
                visit_date,
                services.count() if hasattr(services, "count") else "unknown",
            )
        else:
            logger.warning(
                "Не удалось инициализировать queryset услуг: form=%s reason=no_doctor",
                self.__class__.__name__,
            )

    def clean(self):
        """Общая валидация для всех форм с цепочками"""
        cleaned_data = super().clean()

        appointment_chain_type = cleaned_data.get("appointment_chain_type")
        additional_data = cleaned_data.get("additional_appointments_data")

        logger.info(
            "Вход в clean AppointmentChainBaseForm: form=%s instance_id=%s appointment_chain_type=%s has_additional_data=%s needs_procedural=%s",
            self.__class__.__name__,
            getattr(getattr(self, "instance", None), "id", None),
            appointment_chain_type,
            bool(additional_data),
            cleaned_data.get("needs_procedural"),
        )

        if appointment_chain_type in ["another_doctor", "multiple"]:
            if additional_data:
                try:
                    appointments_list = json.loads(additional_data)

                    logger.info(
                        "Разобраны additional_appointments_data: form=%s instance_id=%s appointments_count=%s",
                        self.__class__.__name__,
                        getattr(getattr(self, "instance", None), "id", None),
                        len(appointments_list),
                    )

                    if not appointments_list:
                        logger.warning(
                            "Пустой список дополнительных записей: form=%s instance_id=%s appointment_chain_type=%s",
                            self.__class__.__name__,
                            getattr(getattr(self, "instance", None), "id", None),
                            appointment_chain_type,
                        )
                        raise ValidationError(
                            f'При выборе опции "{self.get_appointment_type_display(appointment_chain_type)}" '
                            f"необходимо добавить хотя бы одну дополнительную запись"
                        )

                    self._validate_additional_appointments(appointments_list)

                except json.JSONDecodeError:
                    logger.warning(
                        "Некорректный JSON в additional_appointments_data: form=%s instance_id=%s raw=%s",
                        self.__class__.__name__,
                        getattr(getattr(self, "instance", None), "id", None),
                        str(additional_data)[:500],
                    )
                    raise ValidationError(
                        "Неверный формат данных дополнительных записей"
                    )
            else:
                logger.warning(
                    "Для цепочки не переданы дополнительные записи: form=%s instance_id=%s appointment_chain_type=%s",
                    self.__class__.__name__,
                    getattr(getattr(self, "instance", None), "id", None),
                    appointment_chain_type,
                )

        if appointment_chain_type == "two_slots" and self.time_slot:
            logger.info(
                "Проверка последовательного слота: form=%s time_slot_id=%s",
                self.__class__.__name__,
                self.time_slot.id,
            )
            AppointmentValidator.validate_consecutive_slot(self.time_slot)

        logger.info(
            "clean AppointmentChainBaseForm завершен успешно: form=%s instance_id=%s",
            self.__class__.__name__,
            getattr(getattr(self, "instance", None), "id", None),
        )
        return cleaned_data

    def _validate_additional_appointments(self, appointments_list):
        """Валидация дополнительных записей"""
        for i, appointment_data in enumerate(appointments_list, start=1):
            doctor_id = appointment_data.get("doctor_id")
            service_id = appointment_data.get("service_id")
            time_slot_id = appointment_data.get("time_slot_id")

            logger.info(
                "Валидация дополнительной записи: form=%s index=%s doctor_id=%s service_id=%s time_slot_id=%s",
                self.__class__.__name__,
                i,
                doctor_id,
                service_id,
                time_slot_id,
            )

            if not all([doctor_id, service_id, time_slot_id]):
                logger.warning(
                    "Пропуск дополнительной записи из-за неполных данных: form=%s index=%s doctor_id=%s service_id=%s time_slot_id=%s",
                    self.__class__.__name__,
                    i,
                    doctor_id,
                    service_id,
                    time_slot_id,
                )
                continue

            try:
                from timetable.models import Doctor, MedicalService, TimeSlot

                doctor = Doctor.objects.get(id=doctor_id)
                service = MedicalService.objects.get(id=service_id)
                time_slot = TimeSlot.objects.get(id=time_slot_id)

                if not time_slot.is_available():
                    logger.warning(
                        "Слот недоступен для дополнительной записи: form=%s index=%s doctor_id=%s time_slot_id=%s",
                        self.__class__.__name__,
                        i,
                        doctor_id,
                        time_slot_id,
                    )
                    raise ValidationError(
                        f"Ошибка в дополнительной записи #{i}: "
                        f"Слот {time_slot.start_time} у врача {doctor.surname} уже занят"
                    )

                available_services = get_cached_doctor_services(doctor)
                if not available_services.filter(id=service.id).exists():
                    logger.warning(
                        "Услуга недоступна врачу в дополнительной записи: form=%s index=%s doctor_id=%s service_id=%s",
                        self.__class__.__name__,
                        i,
                        doctor_id,
                        service_id,
                    )
                    raise ValidationError(
                        f"Ошибка в дополнительной записи #{i}: "
                        f"Услуга '{service.name}' недоступна врачу {doctor.surname}"
                    )

                logger.info(
                    "Дополнительная запись прошла валидацию: form=%s index=%s doctor_id=%s service_id=%s time_slot_id=%s",
                    self.__class__.__name__,
                    i,
                    doctor_id,
                    service_id,
                    time_slot_id,
                )

            except (
                Doctor.DoesNotExist,
                MedicalService.DoesNotExist,
                TimeSlot.DoesNotExist,
            ) as e:
                logger.warning(
                    "Объект не найден при валидации дополнительной записи: form=%s index=%s error=%s",
                    self.__class__.__name__,
                    i,
                    str(e),
                )
                raise ValidationError(f"Ошибка в дополнительной записи #{i}: {str(e)}")
            except ValidationError:
                raise
            except Exception:
                logger.exception(
                    "Неожиданная ошибка при валидации дополнительной записи: form=%s index=%s",
                    self.__class__.__name__,
                    i,
                )
                raise

    def save(self, commit=True):
        """Базовый метод сохранения"""
        logger.info(
            "Сохранение AppointmentChainBaseForm: form=%s instance_id=%s commit=%s",
            self.__class__.__name__,
            getattr(getattr(self, "instance", None), "id", None),
            commit,
        )
        return super(forms.ModelForm, self).save(commit)
