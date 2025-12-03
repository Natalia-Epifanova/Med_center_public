import os
from datetime import datetime

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import models
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import (
    ListView,
    CreateView,
    UpdateView,
    DetailView,
    DeleteView,
)
from docxtpl import DocxTemplate
from patients.models import Patient
from patients.forms import PatientForm, PatientFullForm
from patients.utils import number_to_words, get_russian_month_name

DOCUMENT_TYPES = {
    "consent_hyaluronic": (
        "informed_consent_hyaluronic_template",
        "Согласие_на_блокаду_(Гиалуроновая_кислота)",
    ),
    "consent_GKSP": (
        "informed_consent_GKSP_template",
        "Согласие_на_блокаду_(ГКСП)",
    ),
    "consent_plasma": (
        "informed_consent_plasma_template",
        "Согласие_на_блокаду_(Плазма)",
    ),
    "consent_xray": (
        "informed_consent_xray_template",
        "Согласие_на_рентген",
    ),
    "consent_physio": (
        "informed_consent_physio_template",
        "Согласие_на_физио",
    ),
    "contract_revmamed": ("contract_revmamed_template", "Договор_Ревмамед"),
    "contract_IP": ("contract_IP_template", "Договор_ИП"),
    "contract_for_psych_support": (
        "contract_for_psych_support_template",
        "Договор_по_псих_сопровождению",
    ),
    "card_OMS": ("card_OMS_template", "Карта_ОМС"),
    "card_IP": ("card_IP_template", "Карта_ИП"),
    "card_paid": ("card_paid_template", "Карта_платно"),
    "card_xray": ("card_xray_template", "Карта_рентген"),
}


class PatientListView(LoginRequiredMixin, ListView):
    model = Patient
    template_name = "patients/patient_list.html"
    context_object_name = "patients"
    paginate_by = 20

    def get_queryset(self):
        queryset = super().get_queryset()
        search = self.request.GET.get("search", "")
        if search:
            queryset = queryset.filter(
                models.Q(surname__icontains=search)
                | models.Q(first_name__icontains=search)
                | models.Q(phone_number__icontains=search)
                | models.Q(card_number__icontains=search)
            )
        return queryset.order_by("card_number", "surname", "first_name")


class PatientCreateView(LoginRequiredMixin, CreateView):
    model = Patient
    form_class = PatientForm  # Минимальная форма для создания
    template_name = "patients/patient_form.html"
    success_url = reverse_lazy("patients:patient_list")


class PatientUpdateView(LoginRequiredMixin, UpdateView):
    model = Patient
    form_class = PatientFullForm
    template_name = "patients/patient_form.html"

    def get_success_url(self):
        return reverse_lazy("patients:patient_detail", kwargs={"pk": self.object.pk})


class PatientDetailView(LoginRequiredMixin, DetailView):
    model = Patient
    template_name = "patients/patient_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        patient = self.object
        context["appointment_history"] = patient.get_appointment_history()
        return context


class PatientDeleteView(LoginRequiredMixin, DeleteView):
    model = Patient
    template_name = "patients/patient_confirm_delete.html"
    success_url = reverse_lazy("patients:patient_list")


class DocumentGenerator:
    """Класс для генерации документов"""

    @staticmethod
    def get_doctor_short_name(doctor):
        """Получить краткое ФИО врача в формате 'Фамилия И.О.'"""
        if doctor and doctor.last_name:  # Если есть отчество
            return f"{doctor.surname} {doctor.first_name[0]}.{doctor.last_name[0]}."
        elif doctor:
            return f"{doctor.surname} {doctor.first_name[0]}."
        return ""

    @staticmethod
    def get_multiple_appointments_context(patient, appointment_ids):
        """Формирует контекст для нескольких записей"""
        from appointments.models import Appointment

        appointments = (
            Appointment.objects.filter(id__in=appointment_ids, patient=patient)
            .select_related("time_slot__doctor", "service")
            .order_by("time_slot__date", "time_slot__start_time")
        )

        if not appointments:
            return None

        # Формируем список услуг
        services_list = []
        total_price = 0
        dates = []

        for i, appointment in enumerate(appointments, 1):
            service_price = appointment.service.price
            if isinstance(service_price, str):
                try:
                    service_price = float(service_price)
                except ValueError:
                    service_price = 0

            # Добавляем услугу с номером
            services_list.append(f"{i}. {appointment.service.name}")
            total_price += service_price

            # Собираем даты
            if appointment.time_slot and appointment.time_slot.date:
                dates.append(appointment.time_slot.date)

        # Объединяем услуги в одну строку через запятую и пробел
        services_text = ", ".join(services_list)

        # Обрабатываем даты
        if dates:
            min_date = min(dates)
            max_date = max(dates)
            if len(dates) == 1:
                # Одна услуга - одна дата
                date_text = f"{min_date.strftime('%d.%m.%Y')}г."
                date_range_text = f"{min_date.strftime('%d.%m.%Y')}г."
            else:
                # Несколько услуг - диапазон дат
                date_text = f"{min_date.strftime('%d.%m.%Y')}г. по {max_date.strftime('%d.%m.%Y')}г."
                date_range_text = f"{min_date.strftime('%d.%m.%Y')}г. по {max_date.strftime('%d.%m.%Y')}г."
        else:
            date_text = ""
            date_range_text = ""

        return {
            "multiple_services": len(appointments) > 1,
            "appointments": appointments,
            "services_list": services_list,
            "services_text": services_text,
            "total_price": total_price,
            "total_price_words": number_to_words(int(total_price)),
            "services_count": len(appointments),
            "first_appointment": appointments.first(),
            "last_appointment": appointments.last(),
            # Даты
            "min_date": min_date.strftime("%d.%m.%Y") if dates else "",
            "max_date": max_date.strftime("%d.%m.%Y") if dates else "",
            "date_range": date_range_text,
            "single_date": min_date.strftime("%d.%m.%Y") if dates else "",
            # Для обратной совместимости
            "appointment_date": min_date.strftime("%d.%m.%Y") if dates else "",
        }

    @staticmethod
    def generate_document(
        patient,
        appointment,
        template_name,
        doc_type_name,
        multiple_appointments_context=None,
    ):
        """Универсальный метод генерации документа"""
        # Базовый контекст (как раньше)
        if not appointment and not multiple_appointments_context:
            appointment = patient.get_last_appointment()

        service_price = appointment.service.price if appointment else 0
        if isinstance(service_price, str):
            try:
                service_price = float(service_price)
            except ValueError:
                service_price = 0

        context = {
            # Данные пациента
            "surname": patient.surname,
            "first_name": patient.first_name,
            "last_name": patient.last_name or "",
            "date_of_birth": patient.date_of_birth.strftime("%d.%m.%Y"),
            "b_day": patient.date_of_birth.strftime("%d"),
            "birth_month": patient.date_of_birth.strftime("%m"),
            "b_month_name": get_russian_month_name(patient.date_of_birth.month),
            "b_year": patient.date_of_birth.strftime("%Y"),
            "phone_number": patient.phone_number or "",
            "card_number": patient.card_number or "",
            "card_number_IP": patient.card_number_IP or "",
            "gender": patient.get_gender_display() if patient.gender else "",
            "area": patient.area or "",
            "locality": patient.locality or "",
            "city": patient.city or "",
            "district": patient.district or "",
            "street": patient.street or "",
            "home": patient.home or "",
            "building": patient.building or "",
            "apartment": patient.apartment or "",
            "address": (
                f"{patient.area or ''} "
                f"{patient.district + ' р-н' if patient.district else ''} "
                f"{patient.locality or ''} "
                f"{patient.city or ''} "
                f"{patient.street or ''} "
                f"д. {patient.home or ''} "
                f"{'к.' + patient.building if patient.building else ''} "
                f"{'кв. ' + patient.apartment if patient.apartment else ''}"
            )
            .strip()
            .replace("  ", " "),
            "passport": "паспорт" if patient.passport_series else "",
            "p_series": patient.passport_series or "",
            "p_number": patient.passport_number or "",
            "p_date": (
                patient.passport_issue_date.strftime("%d.%m.%Y")
                if patient.passport_issue_date
                else ""
            ),
            "p_who_issued": patient.who_issued_the_passport or "",
            "polis_oms": patient.polis_oms or "",
            "snils": patient.snils or "",
            "insurance_company": patient.insurance_company or "",
            # Данные о записи (для обратной совместимости)
            "appointment_date": (
                appointment.time_slot.date.strftime("%d.%m.%Y") if appointment else None
            ),
            "doctor_name": (
                DocumentGenerator.get_doctor_short_name(appointment.doctor)
                if appointment
                else ""
            ),
            "doctor_specialization": (
                appointment.doctor.get_specialization_display() if appointment else ""
            ),
            "service_name": appointment.service.name if appointment else "",
            "service_price": service_price,
            "service_price_words": number_to_words(int(service_price)),
            # Текущая дата
            "current_date": datetime.now().strftime("%d.%m.%Y"),
            "c_day": datetime.now().strftime("%d"),
            "current_month": datetime.now().strftime("%m"),
            "cur_month_ru": get_russian_month_name(datetime.now().month),
            "current_year": datetime.now().strftime("%Y"),
            "multiple_services": False,
            "services_count": 1,
            "services_text": appointment.service.name if appointment else "",
            "total_price": service_price,
            "total_price_words": number_to_words(int(service_price)),
            "date_range": (
                appointment.time_slot.date.strftime("%d.%m.%Y") + "г."
                if appointment and appointment.time_slot and appointment.time_slot.date
                else ""
            ),
            "single_date": (
                appointment.time_slot.date.strftime("%d.%m.%Y")
                if appointment and appointment.time_slot and appointment.time_slot.date
                else ""
            ),
        }

        # Добавляем контекст для нескольких записей, если есть
        if multiple_appointments_context:
            context.update(multiple_appointments_context)

        # ИСПРАВЛЕННЫЙ ПУТЬ К ШАБЛОНАМ
        template_path = os.path.join(
            settings.BASE_DIR,
            "patients",
            "templates",
            "patients",
            "docs",
            f"{template_name}.docx",
        )

        print(f"Ищем шаблон по пути: {template_path}")  # Для отладки

        # Проверяем существование файла
        if not os.path.exists(template_path):
            raise FileNotFoundError(f"Файл шаблона не найден: {template_path}")

        doc = DocxTemplate(template_path)
        doc.render(context)

        # Сохраняем временный файл
        filename = f"{doc_type_name}_{patient.surname}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx"
        filepath = os.path.join("media", "temp_docs", filename)

        # Создаем папку если не существует
        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        doc.save(filepath)
        return filepath, filename


def generate_document(request, pk, doc_type):
    """View для генерации документов"""
    patient = get_object_or_404(Patient, pk=pk)

    # Получаем ID записей из GET параметров
    appointment_ids = request.GET.getlist("appointment_id")
    appointment = None
    multiple_appointments_context = None

    # Договоры поддерживают несколько записей
    is_contract = doc_type in ["contract_revmamed", "contract_IP"]

    if appointment_ids:
        from appointments.models import Appointment

        if is_contract and len(appointment_ids) > 1:
            # Для договоров с несколькими записями
            multiple_appointments_context = (
                DocumentGenerator.get_multiple_appointments_context(
                    patient, appointment_ids
                )
            )
            if not multiple_appointments_context:
                appointment = patient.get_last_appointment()
        else:
            # Для одиночных записей
            try:
                appointment = Appointment.objects.get(
                    id=appointment_ids[0], patient=patient
                )
            except Appointment.DoesNotExist:
                appointment = patient.get_last_appointment()
    else:
        appointment = patient.get_last_appointment()

    if doc_type not in DOCUMENT_TYPES:
        return HttpResponse("Неизвестный тип документа")

    template_name, doc_type_name = DOCUMENT_TYPES[doc_type]

    try:
        filepath, filename = DocumentGenerator.generate_document(
            patient,
            appointment,
            template_name,
            doc_type_name,
            multiple_appointments_context,
        )
    except FileNotFoundError:
        return HttpResponse(f"Шаблон документа '{template_name}.docx' не найден")

    # Возвращаем DOCX
    with open(filepath, "rb") as f:
        response = HttpResponse(
            f.read(),
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        response["Content-Disposition"] = f'attachment; filename="{filename}"'

    # Удаляем временный файл
    os.remove(filepath)
    return response
