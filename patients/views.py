import os
from datetime import datetime
from typing import List, Optional

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import models
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse_lazy
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
)
from docxtpl import DocxTemplate

from appointments.models import Appointment
from patients.constants import DOCUMENT_TYPES
from patients.forms import PatientForm, PatientFullForm, PatientSearchForm
from patients.models import Patient
from patients.utils import get_russian_month_name, number_to_words
from users.permissions.decorators import medical_admin_or_admin_required
from users.permissions.mixins import MedicalAdminOrAdminRequiredMixin


class PatientListView(LoginRequiredMixin, ListView):
    """Список пациентов с поиском и пагинацией"""

    model = Patient
    template_name = "patients/patient_list.html"
    context_object_name = "patients"
    paginate_by = 20

    def get_queryset(self):
        """Получение и фильтрация queryset"""
        queryset = super().get_queryset()
        search = self.request.GET.get("search", "").strip()

        if search:
            # Поиск по нескольким полям
            queryset = queryset.filter(
                models.Q(surname__icontains=search)
                | models.Q(first_name__icontains=search)
                | models.Q(last_name__icontains=search)
                | models.Q(phone_number__icontains=search)
                | models.Q(card_number__icontains=search)
                | models.Q(card_number_IP__icontains=search)
                | models.Q(card_number_OMS__icontains=search)
            )

        # Используем ordering из Meta
        return queryset

    def get_context_data(self, **kwargs):
        """Добавляем форму поиска в контекст"""
        context = super().get_context_data(**kwargs)
        context["search_form"] = PatientSearchForm(
            initial={"search": self.request.GET.get("search", "")}
        )
        return context


class PatientCreateView(MedicalAdminOrAdminRequiredMixin, CreateView):
    """Создание нового пациента"""

    model = Patient
    form_class = PatientForm
    template_name = "patients/patient_form.html"
    success_url = reverse_lazy("patients:patient_list")

    def form_valid(self, form):
        """Дополнительная обработка при успешном создании"""
        response = super().form_valid(form)
        # Можно добавить сообщение об успехе
        return response


class PatientUpdateView(MedicalAdminOrAdminRequiredMixin, UpdateView):
    model = Patient
    form_class = PatientFullForm
    template_name = "patients/patient_form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Определяем группы полей
        context["address_fields"] = [
            "area",
            "locality",
            "city",
            "district",
            "street",
            "home",
            "building",
            "apartment",
        ]
        context["insurance_fields"] = ["polis_oms", "snils", "insurance_company"]

        return context

    def get_success_url(self):
        return reverse_lazy("patients:patient_detail", kwargs={"pk": self.object.pk})


class PatientDetailView(LoginRequiredMixin, DetailView):
    """Детальная информация о пациенте"""

    model = Patient
    template_name = "patients/patient_detail.html"

    def get_context_data(self, **kwargs):
        """Добавление истории записей в контекст"""
        context = super().get_context_data(**kwargs)
        patient = self.object

        # Получаем историю записей с оптимизацией запросов
        appointment_history = (
            Appointment.objects.filter(patient=patient)
            .select_related("time_slot__doctor", "time_slot__cabinet", "service")
            .prefetch_related("selected_blood_tests")
            .order_by("-time_slot__date", "-time_slot__start_time")
        )

        context["appointment_history"] = appointment_history
        return context


class PatientDeleteView(MedicalAdminOrAdminRequiredMixin, DeleteView):
    """Удаление пациента"""

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

        # ПРАВИЛЬНО ФОРМИРУЕМ АДРЕС
        address_parts = []

        # Добавляем субъект РФ (область, край и т.д.)
        if patient.area:
            address_parts.append(patient.area)

        # Добавляем район если есть
        if patient.district:
            address_parts.append(f"{patient.district} р-н")

        # Населенный пункт
        if patient.locality:
            address_parts.append(patient.locality)

        # Город
        if patient.city:
            address_parts.append(f"г. {patient.city}")

        # Улица
        if patient.street:
            address_parts.append(f"ул. {patient.street}")

        # Дом
        if patient.home:
            house_part = f"д. {patient.home}"
            if patient.building:
                house_part += f" корп. {patient.building}"
            address_parts.append(house_part)

        # Квартира
        if patient.apartment:
            address_parts.append(f"кв. {patient.apartment}")

        # Формируем итоговый адрес
        formatted_address = ", ".join(filter(None, address_parts))

        context = {
            # Данные пациента
            "surname": patient.surname,
            "first_name": patient.first_name,
            "last_name": patient.last_name or "",
            "date_of_birth": (
                patient.date_of_birth.strftime("%d.%m.%Y")
                if patient.date_of_birth
                else ""
            ),
            "b_day": (
                patient.date_of_birth.strftime("%d") if patient.date_of_birth else ""
            ),
            "birth_month": (
                patient.date_of_birth.strftime("%m") if patient.date_of_birth else ""
            ),
            "b_month_name": (
                get_russian_month_name(patient.date_of_birth.month)
                if patient.date_of_birth
                else ""
            ),
            "b_year": (
                patient.date_of_birth.strftime("%Y") if patient.date_of_birth else ""
            ),
            "phone_number": patient.phone_number or "",
            "card_number": patient.card_number or "",
            "card_number_IP": patient.card_number_IP or "",
            "card_number_OMS": patient.card_number_OMS or "",
            "gender": patient.get_gender_display() if patient.gender else "",
            "area": patient.area or "",
            "locality": patient.locality or "",
            "city": patient.city or "",
            "district": patient.district or "",
            "street": patient.street or "",
            "home": patient.home or "",
            "building": patient.building or "",
            "apartment": patient.apartment or "",
            # АДРЕС - ИСПРАВЛЕННЫЙ ВАРИАНТ
            "address": formatted_address,
            # ПАСПОРТ - ИСПРАВЛЕННЫЙ ВАРИАНТ
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
            # Данные о записи
            "appointment_date": (
                appointment.time_slot.date.strftime("%d.%m.%Y")
                if appointment and appointment.time_slot
                else ""
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


@medical_admin_or_admin_required
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
