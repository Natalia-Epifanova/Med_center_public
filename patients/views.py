import os
from datetime import datetime

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import models
from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404
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

DOCUMENT_TYPES = {
    "consent_paid": (
        "informed_consent_paid_template",
        "Информированное_согласие_платно",
    ),
    "consent_oms": ("informed_consent_oms_template", "Информированное_согласие_ОМС"),
    "consent_IP": (
        "informed_consent_IP_template",
        "Информированное_согласие_ИП_Епифанова_ОЕ",
    ),
    "contract_xray": ("contract_xray_template", "Рентген_договор"),
    "contract_IP": ("contract_IP_template", "Договор_ИП"),
    "contract_densitometry": (
        "contract_densitometry_template",
        "Договор_на_денситометрию",
    ),
    "contract_ultrasound_IP": ("contract_ultrasound_IP_template", "Договор_на_УЗИ_ИП"),
    "contract_for_psych_support": (
        "contract_for_psych_support_template",
        "Договор_по_псих_сопровождению",
    ),
    "card_OMS": ("card_OMS_template", "Карта_ОМС"),
    "card_IP": ("card_IP_template", "Карта_ИП"),
    "card_paid": ("card_paid_template", "Карта_платно"),
    "card_xray": ("card_xray_template", "Карта_рентген"),
    "tax certificate": ("tax certificate_template", "Налоговая справка"),
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
    success_url = reverse_lazy("patients:patient_list")


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
    def generate_document(patient, appointment, template_name, doc_type_name):
        """Универсальный метод генерации документа"""
        if not appointment:
            appointment = patient.get_last_appointment()

        context = {
            # Данные пациента
            "surname": patient.surname,
            "first_name": patient.first_name,
            "last_name": patient.last_name or "",
            "date_of_birth": patient.date_of_birth,
            "b_day": patient.date_of_birth.strftime("%d"),
            "birth_month": patient.date_of_birth.strftime("%m"),
            "b_month_name": get_russian_month_name(patient.date_of_birth.month),
            "b_year": patient.date_of_birth.strftime("%Y"),
            "phone_number": patient.phone_number or "",
            "card_number": patient.card_number or "",
            "gender": patient.get_gender_display() if patient.gender else "",
            "area": patient.area or "",
            "locality": patient.locality or "",
            "city": patient.city or "",
            "district": patient.district or "",
            "street": patient.street or "Не указан",
            "home": patient.home or "Не указан",
            "building": patient.building or "Не указан",
            "apartment": patient.apartment or "Не указан",
            "passport": "паспорт" if patient.passport_series else "",
            "p_series": patient.passport_series or "",
            "p_number": patient.passport_number or "",
            "polis_oms": patient.polis_oms or "Не указан",
            "snils": patient.snils or "Не указан",
            "insurance_company": patient.insurance_company or "",
            # Данные о записи
            "appointment_date": appointment.time_slot.date if appointment else None,
            "doctor_name": (
                DocumentGenerator.get_doctor_short_name(appointment.doctor)
                if appointment
                else ""
            ),
            "doctor_specialization": (
                appointment.doctor.get_specialization_display() if appointment else ""
            ),
            "service_name": appointment.service.name if appointment else "",
            "service_price": appointment.service.price if appointment else "0",
            # Текущая дата
            "current_date": datetime.now().strftime("%d.%m.%Y"),
            "c_day": datetime.now().strftime("%d"),  # День (01-31)
            "current_month": datetime.now().strftime("%m"),  # Месяц (01-12)
            "current_month_name_ru": get_russian_month_name(
                datetime.now().month
            ),  # Русское название месяца
            "current_year": datetime.now().strftime("%Y"),  # Год (2025)
        }

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

    # Получаем ID записи из GET параметров
    appointment_id = request.GET.get("appointment_id")
    appointment = None

    if appointment_id:
        from timetable.models import Appointment

        try:
            appointment = Appointment.objects.get(id=appointment_id, patient=patient)
        except Appointment.DoesNotExist:
            appointment = patient.get_last_appointment()
    else:
        appointment = patient.get_last_appointment()

    if doc_type not in DOCUMENT_TYPES:
        return HttpResponse("Неизвестный тип документа")

    template_name, doc_type_name = DOCUMENT_TYPES[doc_type]

    try:
        filepath, filename = DocumentGenerator.generate_document(
            patient, appointment, template_name, doc_type_name
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


def get_russian_month_name(month_number):
    """Возвращает русское название месяца по номеру"""
    months = {
        1: "января",
        2: "февраля",
        3: "марта",
        4: "апреля",
        5: "мая",
        6: "июня",
        7: "июля",
        8: "августа",
        9: "сентября",
        10: "октября",
        11: "ноября",
        12: "декабря",
    }
    return months.get(month_number, "")
