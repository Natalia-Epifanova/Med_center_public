import os
from datetime import datetime
from typing import List, Optional

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.db import models
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
    TemplateView,
)
from docxtpl import DocxTemplate

from appointments.models import Appointment
from patients.constants import DOCUMENT_TYPES
from patients.forms import (
    PatientForm,
    PatientFullForm,
    PatientSearchForm,
    ReservePatientCreateForm,
    ReservePatientUpdateForm,
    WaitlistPatientForm,
)
from patients.models import Patient, ReserveList, ReservePatient, WaitlistPatient
from patients.services import PatientService, CardNumberService
from patients.utils import (
    get_russian_month_name,
    number_to_words,
    get_russian_month_name_for_reserve,
)
from timetable.models import Doctor
from users.permissions.decorators import medical_admin_or_admin_required
from users.permissions.mixins import MedicalAdminOrAdminRequiredMixin


class PatientListView(LoginRequiredMixin, ListView):
    """Список пациентов с поиском и пагинацией"""

    model = Patient
    template_name = "patients/patient_list.html"
    login_url = "/users/login/"
    context_object_name = "patients"
    paginate_by = 100

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
    def get_patient_short_name(patient):
        """Получить Полное ФИО врача в формате 'Фамилия И.О.'"""
        if patient and patient.last_name:  # Если есть отчество
            return f"{patient.surname} {patient.first_name[0]}.{patient.last_name[0]}."
        elif patient:
            return f"{patient.surname} {patient.first_name[0]}."
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

        # Проверяем, существует ли appointment
        if appointment and appointment.doctor:
            service_price = appointment.service.price if appointment.service else 0
            doctor_short_name = DocumentGenerator.get_doctor_short_name(
                appointment.doctor
            )
            patient_short_name = DocumentGenerator.get_patient_short_name(
                appointment.patient
            )
            doctor_specialization = appointment.doctor.get_specialization_display()
            doc_surname = appointment.doctor.surname
            doc_f_name = appointment.doctor.first_name
            doc_l_name = appointment.doctor.last_name or ""
            service_name = appointment.service.name if appointment.service else ""
            appointment_date = (
                appointment.time_slot.date.strftime("%d.%m.%Y")
                if appointment.time_slot and appointment.time_slot.date
                else ""
            )
        else:
            # Устанавливаем значения по умолчанию если appointment или doctor отсутствуют
            service_price = 0
            doctor_short_name = ""
            patient_short_name = DocumentGenerator.get_patient_short_name(patient)
            doctor_specialization = ""
            doc_surname = ""
            doc_f_name = ""
            doc_l_name = ""
            service_name = ""
            appointment_date = ""

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

        # Формируем контекст с БЕЗОПАСНЫМИ значениями
        context = {
            # Данные пациента
            "patient_id": patient.pk,
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
            # Данные о записи - используем значения из проверки выше
            "appointment_date": appointment_date,
            "doctor_name": doctor_short_name,
            "patient_short_name": patient_short_name,
            "doctor_specialization": doctor_specialization,
            "doc_surname": doc_surname,
            "doc_f_name": doc_f_name,
            "doc_l_name": doc_l_name,
            "service_name": service_name,
            "service_price": service_price,
            "service_price_words": (
                number_to_words(int(service_price)) if service_price else "ноль"
            ),
            # Текущая дата
            "current_date": datetime.now().strftime("%d.%m.%Y"),
            "c_day": datetime.now().strftime("%d"),
            "current_month": datetime.now().strftime("%m"),
            "cur_month_ru": get_russian_month_name(datetime.now().month),
            "current_year": datetime.now().strftime("%Y"),
            "multiple_services": False,
            "services_count": 1,
            "services_text": service_name,
            "total_price": service_price,
            "total_price_words": (
                number_to_words(int(service_price)) if service_price else "ноль"
            ),
            "date_range": appointment_date + "г." if appointment_date else "",
            "single_date": appointment_date,
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


# ===== РЕЗЕРВНЫЕ СПИСКИ =====


class ReserveMainView(LoginRequiredMixin, TemplateView):
    """Главная страница резервных списков - показываем только врачей с записями"""

    template_name = "patients/reserve_main.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        current_year = timezone.now().year
        search = self.request.GET.get("search", "").strip()

        # Используем правильное имя обратной связи: 'reservelist' (строчными буквами)
        # Получаем ID врачей, у которых ЕСТЬ записи в резерве в текущем году
        doctors_with_reserve_ids = (
            ReserveList.objects.filter(year=current_year, entries__isnull=False)
            .values_list("doctor_id", flat=True)
            .distinct()
        )

        # Если есть поиск, фильтруем дополнительно по имени пациента
        if search:
            doctors_with_reserve_ids = (
                ReserveList.objects.filter(
                    year=current_year, entries__surname__icontains=search
                )
                .values_list("doctor_id", flat=True)
                .distinct()
            )

        # Получаем врачей
        doctors_to_show = Doctor.objects.filter(id__in=doctors_with_reserve_ids)

        # Структура для отображения
        reserve_data = []

        for doctor in doctors_to_show:
            doctor_data = {
                "doctor": doctor,
                "months": [],
                "total_patients": 0,
                "has_any_patients": False,
            }

            # Для каждого месяца (1-12)
            for month_num in range(1, 13):
                try:
                    # Получаем список резерва
                    reserve_list = ReserveList.objects.get(
                        doctor=doctor, month=month_num, year=current_year
                    )

                    # Получаем записи
                    entries = reserve_list.entries.all().order_by(
                        "surname", "first_name"
                    )

                    # Фильтруем по поиску если нужно
                    if search:
                        entries = entries.filter(
                            models.Q(surname__icontains=search)
                            | models.Q(first_name__icontains=search)
                            | models.Q(last_name__icontains=search)
                            | models.Q(phone_number__icontains=search)
                        )

                    patient_count = entries.count()

                    doctor_data["months"].append(
                        {
                            "month_num": month_num,
                            "month_name": get_russian_month_name_for_reserve(
                                month_num
                            ).capitalize(),
                            "reserve_list": reserve_list,
                            "entries": entries,
                            "patient_count": patient_count,
                        }
                    )

                    doctor_data["total_patients"] += patient_count

                    if patient_count > 0:
                        doctor_data["has_any_patients"] = True

                except ReserveList.DoesNotExist:
                    # Если списка нет - пустой месяц
                    doctor_data["months"].append(
                        {
                            "month_num": month_num,
                            "month_name": get_russian_month_name_for_reserve(
                                month_num
                            ).capitalize(),
                            "reserve_list": None,
                            "entries": [],
                            "patient_count": 0,
                        }
                    )

            # Добавляем врача в список только если у него есть пациенты
            if doctor_data["has_any_patients"]:
                reserve_data.append(doctor_data)

        context.update(
            {
                "reserve_data": reserve_data,
                "current_year": current_year,
                "search": search,
                "has_results": len(reserve_data) > 0,
                "doctors_count": doctors_to_show.count(),
            }
        )

        return context


class ReservePatientCreateView(LoginRequiredMixin, CreateView):
    """Создание новой записи в резерве"""

    model = ReservePatient
    form_class = ReservePatientCreateForm
    template_name = "patients/reserve_patient_form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Получаем параметры из GET запроса
        doctor_id = self.request.GET.get("doctor_id")
        month = self.request.GET.get("month", timezone.now().month)
        year = self.request.GET.get("year", timezone.now().year)

        # Добавляем врачей для выбора
        context["doctors"] = Doctor.objects.all()
        context["selected_doctor_id"] = doctor_id
        context["selected_month"] = month
        context["selected_year"] = year
        context["current_year"] = timezone.now().year

        return context

    def form_valid(self, form):
        # Получаем данные пациента из формы
        patient_data = {
            "surname": form.cleaned_data.get("surname"),
            "first_name": form.cleaned_data.get("first_name"),
            "last_name": form.cleaned_data.get("last_name", ""),
            "phone_number": form.cleaned_data.get("phone_number"),
            "date_of_birth": form.cleaned_data.get("date_of_birth"),
        }

        # Создаем или находим пациента в основной базе
        try:
            patient, created = PatientService.get_or_create_patient(patient_data)

            if created:
                messages.info(
                    self.request,
                    f"Новый пациент {patient.get_full_name()} добавлен в базу данных",
                )
            else:
                messages.info(
                    self.request,
                    f"Использован существующий пациент: {patient.get_full_name()}",
                )

        except ValidationError as e:
            messages.error(self.request, f"Ошибка при создании пациента: {e}")
            return self.form_invalid(form)
        except Exception as e:
            messages.error(self.request, f"Ошибка при обработке пациента: {e}")
            return self.form_invalid(form)

        # Получаем данные о враче и периоде
        doctor_id = self.request.POST.get("doctor")
        month = self.request.POST.get("month", timezone.now().month)
        year = self.request.POST.get("year", timezone.now().year)

        if not doctor_id:
            messages.error(self.request, "Необходимо выбрать врача")
            return self.form_invalid(form)

        try:
            doctor = Doctor.objects.get(id=doctor_id)
        except Doctor.DoesNotExist:
            messages.error(self.request, "Выбранный врач не найден")
            return self.form_invalid(form)

        # Получаем или создаем резервный список
        reserve_list, created = ReserveList.objects.get_or_create(
            doctor=doctor, month=int(month), year=int(year)
        )

        # Сохраняем запись в резерв с привязкой к пациенту
        reserve_patient = form.save(commit=False)
        reserve_patient.reserve_list = reserve_list
        reserve_patient.patient = (
            patient  # Привязываем к найденному/созданному пациенту
        )

        # Копируем данные из формы (на всякий случай)
        reserve_patient.surname = patient.surname
        reserve_patient.first_name = patient.first_name
        reserve_patient.last_name = patient.last_name or ""
        reserve_patient.phone_number = patient.phone_number or ""
        reserve_patient.date_of_birth = patient.date_of_birth

        reserve_patient.save()

        messages.success(
            self.request,
            f"Пациент {patient.get_full_name()} добавлен в резервный список "
            f"{doctor.surname} {doctor.first_name} {doctor.last_name}",
        )
        return redirect("patients:reserve_main")

    def get_success_url(self):
        return reverse_lazy("patients:reserve_main")


class ReservePatientUpdateView(LoginRequiredMixin, UpdateView):
    """Редактирование только КОММЕНТАРИЯ в резервной записи"""

    model = ReservePatient
    form_class = ReservePatientUpdateForm
    template_name = "patients/reserve_patient_form.html"

    def get_form_kwargs(self):
        """Добавляем instance в kwargs для формы"""
        kwargs = super().get_form_kwargs()
        kwargs["instance"] = self.object
        return kwargs

    def form_valid(self, form):
        """Сохраняем ТОЛЬКО комментарий"""
        reserve_patient = self.object
        reserve_patient.comment = form.cleaned_data.get("comment", "")
        reserve_patient.save(update_fields=["comment"])

        messages.success(self.request, "Комментарий обновлен")
        return redirect("patients:reserve_main")

    def get_context_data(self, **kwargs):
        """Добавляем данные пациента в контекст для отображения"""
        context = super().get_context_data(**kwargs)
        reserve_patient = self.object

        # Добавляем данные пациента для отображения
        context["reserve_patient"] = reserve_patient
        context["patient"] = reserve_patient.patient  # Если есть связь
        context["is_edit_mode"] = True
        context["readonly_mode"] = True  # Флаг для шаблона

        return context

    def get_success_url(self):
        return reverse_lazy("patients:reserve_main")


class ReservePatientDeleteView(MedicalAdminOrAdminRequiredMixin, DeleteView):
    """Удаление записи из резерва"""

    model = ReservePatient
    template_name = "patients/reserve_patient_confirm_delete.html"

    def delete(self, request, *args, **kwargs):
        messages.success(request, "Запись удалена из резерва")
        return super().delete(request, *args, **kwargs)

    def get_success_url(self):
        return reverse_lazy("patients:reserve_main")


class WaitlistPatientListView(LoginRequiredMixin, ListView):
    """Список пациентов в листе ожидания"""

    model = WaitlistPatient
    template_name = "patients/waitlist_list.html"
    context_object_name = "waitlist_patients"


class WaitlistPatientCreateView(LoginRequiredMixin, CreateView):
    """Добавление пациента в лист ожидания"""

    model = WaitlistPatient
    form_class = WaitlistPatientForm
    template_name = "patients/waitlist_form.html"

    def get_success_url(self):
        return reverse_lazy("timetable:reschedule_requests")


class WaitlistPatientUpdateView(LoginRequiredMixin, UpdateView):
    """Редактирование записи в листе ожидания"""

    model = WaitlistPatient
    form_class = WaitlistPatientForm
    template_name = "patients/waitlist_form.html"

    def get_success_url(self):
        return reverse_lazy("timetable:reschedule_requests")


class WaitlistPatientDeleteView(MedicalAdminOrAdminRequiredMixin, DeleteView):
    """Удаление записи из листа ожидания"""

    model = WaitlistPatient
    template_name = "patients/waitlist_confirm_delete.html"

    def get_success_url(self):
        return reverse_lazy("timetable:reschedule_requests")

    def delete(self, request, *args, **kwargs):
        messages.success(request, "Запись удалена из листа ожидания")
        return super().delete(request, *args, **kwargs)
