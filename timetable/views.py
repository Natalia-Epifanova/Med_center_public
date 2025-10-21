from datetime import datetime, timedelta

from django import forms
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import models, IntegrityError, transaction
from django.http import HttpResponseRedirect, JsonResponse
from django.urls import reverse_lazy, reverse
from django.utils import timezone
from django.views.generic import (
    TemplateView,
    CreateView,
    UpdateView,
    DeleteView,
    DetailView,
    ListView,
)
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.db.models import Q


from timetable.forms import (
    TimeSlotForm,
    TimeSlotUpdateForm,
    PatientForm,
    AppointmentForm,
    AppointmentUpdateForm,
)
from timetable.models import TimeSlot, Patient, Appointment
from timetable.utils import save_slots_with_conflict_check, create_time_slots


class HomeView(TemplateView):
    template_name = "timetable/home.html"


class TimeSlotCreateView(LoginRequiredMixin, CreateView):
    model = TimeSlot
    form_class = TimeSlotForm
    template_name = "timetable/schedule_create.html"

    def get_success_url(self):
        return reverse_lazy("timetable:schedule_create")

    def form_valid(self, form):
        date = form.cleaned_data["date"]
        cabinet = form.cleaned_data["cabinet"]
        doctor = form.cleaned_data["doctor"]
        add_type = form.cleaned_data["add_type"]

        try:
            if add_type == "single":
                slots = self._create_single_slot(form, date, cabinet, doctor)
            else:
                slots = self._create_multiple_slots(form, date, cabinet, doctor)

            saved_count = save_slots_with_conflict_check(slots)

            if saved_count > 0:
                messages.success(self.request, f"Успешно создано {saved_count} слотов")
            else:
                messages.warning(self.request, "Не было создано ни одного нового слота")

        except Exception as e:
            messages.error(self.request, f"Ошибка при создании слотов: {str(e)}")
            return self.form_invalid(form)

        return HttpResponseRedirect(self.get_success_url())

    def _create_single_slot(self, form, date, cabinet, doctor):
        """Создание одиночного слота"""
        start_time = form.cleaned_data.get("single_start_time")
        end_time = form.cleaned_data.get("single_end_time")
        slot_type = form.cleaned_data.get("single_slot_type")
        description = form.cleaned_data.get("single_description") or ""

        if start_time and end_time:
            return [
                TimeSlot(
                    date=date,
                    cabinet=cabinet,
                    doctor=doctor,
                    start_time=start_time,
                    end_time=end_time,
                    slot_type=slot_type,
                    description=description,
                )
            ]
        return []

    def _create_multiple_slots(self, form, date, cabinet, doctor):
        """Создание нескольких слотов"""
        start_time = form.cleaned_data.get("multiple_start_time")
        end_time = form.cleaned_data.get("multiple_end_time")
        interval = form.cleaned_data.get("interval")

        if start_time and end_time and interval:
            return create_time_slots(
                date, cabinet, doctor, start_time, end_time, interval
            )
        return []


class TimeSlotUpdateView(LoginRequiredMixin, UpdateView):
    model = TimeSlot
    form_class = TimeSlotUpdateForm
    template_name = "timetable/timeslot_form.html"

    def get_success_url(self):
        return reverse_lazy("timetable:timeslot_detail", kwargs={"pk": self.object.pk})

    def form_valid(self, form):
        messages.success(self.request, "Слот успешно обновлен.")
        return super().form_valid(form)


class TimeSlotDetailView(LoginRequiredMixin, DetailView):
    model = TimeSlot
    template_name = "timetable/timeslot_detail.html"
    context_object_name = "slot"


class TimeSlotDeleteView(LoginRequiredMixin, DeleteView):
    model = TimeSlot
    template_name = "timetable/timeslot_confirm_delete.html"
    success_url = reverse_lazy("timetable:schedule_day")

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, "Слот успешно удален.")
        return super().delete(request, *args, **kwargs)


class ScheduleDayView(LoginRequiredMixin, TemplateView):
    template_name = "timetable/schedule_day.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        date_param = self.request.GET.get("date")

        # Получаем текущую дату
        current_date = timezone.now().date()
        context["current_date"] = current_date

        # Определяем выбранную дату
        if date_param:
            try:
                selected_date = datetime.strptime(date_param, "%Y-%m-%d").date()
            except ValueError:
                messages.error(self.request, "Неверный формат даты")
                selected_date = current_date
        else:
            # Если дата не указана, показываем сегодня
            selected_date = current_date

        context["selected_date"] = selected_date

        # Вычисляем предыдущий и следующий день
        prev_date = selected_date - timedelta(days=1)
        next_date = selected_date + timedelta(days=1)
        context["prev_date"] = prev_date
        context["next_date"] = next_date

        # Получаем слоты на выбранную дату
        slots = TimeSlot.objects.filter(date=selected_date).select_related(
            "cabinet", "doctor"
        )
        cabinets = set(slot.cabinet for slot in slots)

        schedule_data = {}
        for cabinet in cabinets:
            cabinet_slots = slots.filter(cabinet=cabinet).order_by("start_time")
            schedule_data[cabinet] = cabinet_slots

        context["schedule_data"] = schedule_data
        slots = TimeSlot.objects.filter(date=selected_date).select_related(
            "cabinet", "doctor"
        )
        cabinets = set(slot.cabinet for slot in slots)

        schedule_data = {}
        for cabinet in cabinets:
            cabinet_slots = slots.filter(cabinet=cabinet).order_by("start_time")

            # Группируем слоты по врачам с комментариями
            doctor_slots = {}
            for slot in cabinet_slots:
                doctor_id = slot.doctor.id
                if doctor_id not in doctor_slots:
                    doctor_slots[doctor_id] = {
                        "doctor": slot.doctor,
                        "comment": slot.doctor.schedule_comment,
                        "slots": [],
                    }
                doctor_slots[doctor_id]["slots"].append(slot)

            schedule_data[cabinet] = doctor_slots

        context["schedule_data"] = schedule_data
        return context


class PatientListView(LoginRequiredMixin, ListView):
    model = Patient
    template_name = "timetable/patient_list.html"
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
    form_class = PatientForm
    template_name = "timetable/patient_form.html"
    success_url = reverse_lazy("timetable:patient_list")


class PatientUpdateView(LoginRequiredMixin, UpdateView):
    model = Patient
    form_class = PatientForm
    template_name = "timetable/patient_form.html"
    success_url = reverse_lazy("timetable:patient_list")


class PatientDetailView(LoginRequiredMixin, DetailView):
    model = Patient
    template_name = "timetable/patient_detail.html"


class PatientDeleteView(LoginRequiredMixin, DeleteView):
    model = Patient
    template_name = "timetable/patient_confirm_delete.html"
    success_url = reverse_lazy("timetable:patient_list")


class AppointmentCreateView(CreateView):
    model = Appointment
    form_class = AppointmentForm
    template_name = "timetable/appointment_form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        time_slot = TimeSlot.objects.get(pk=self.kwargs["time_slot_id"])
        kwargs["time_slot"] = time_slot
        kwargs["doctor"] = time_slot.doctor
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        time_slot = TimeSlot.objects.get(pk=self.kwargs["time_slot_id"])
        context["time_slot"] = time_slot
        context["doctor"] = time_slot.doctor

        # Получаем информацию о следующем слоте для отображения
        next_slot = time_slot.get_next_consecutive_slot()
        context["next_slot"] = next_slot

        return context

    @transaction.atomic
    def form_valid(self, form):
        print("🔔 НАЧАЛО FORM_VALID (atomic transaction)")
        sid = None

        try:
            # Создаем точку сохранения для возможного отката
            sid = transaction.savepoint()

            # Получаем данные пациента из формы
            patient_data = {
                "surname": form.cleaned_data.get("surname"),
                "first_name": form.cleaned_data.get("first_name"),
                "last_name": form.cleaned_data.get("last_name"),
                "phone_number": form.cleaned_data.get("phone_number"),
                "card_number": form.cleaned_data.get("card_number"),
                "date_of_birth": form.cleaned_data.get("date_of_birth"),
            }
            print(f"🔔 Данные пациента в form_valid: {patient_data}")

            # Ищем существующего пациента (используем миксин)
            patient, created = form.get_or_create_patient(patient_data)
            print(f"🔔 Пациент в form_valid: {patient}, created: {created}")

            # ВАЖНО: Проверяем, что пациент создан/найден
            if not patient:
                messages.error(
                    self.request,
                    "Не удалось создать или найти пациента. Проверьте данные.",
                )
                return self.form_invalid(form)

            # Проверяем, что основной слот все еще свободен
            time_slot = form.time_slot
            if not time_slot.is_available():
                messages.error(
                    self.request,
                    "К сожалению, выбранное время уже занято. Пожалуйста, выберите другое время.",
                )
                return self.form_invalid(form)

            # ВАЖНО: Проверяем возможность создания процедурной записи ДО сохранения основной
            needs_procedural = form.cleaned_data.get("needs_procedural")
            print(f"🔔 Значение needs_procedural: {needs_procedural}")
            print(f"🔔 Время слота: {time_slot.start_time}-{time_slot.end_time}")

            if needs_procedural:
                print("🔄 ПРЕДВАРИТЕЛЬНАЯ ПРОВЕРКА ПРОЦЕДУРНОЙ ЗАПИСИ")
                # Создаем временный объект appointment для проверки
                temp_appointment = Appointment(
                    time_slot=time_slot,
                    patient=patient,
                    service=form.cleaned_data.get("service"),
                    insurance_type=form.cleaned_data.get("insurance_type"),
                )

                can_create_procedural = form.can_create_procedural_appointment(
                    temp_appointment
                )
                if not can_create_procedural:
                    messages.error(
                        self.request,
                        "Невозможно создать запись: выбранное время в процедурном кабинете уже занято. "
                        "Пожалуйста, выберите другое время или снимите галочку 'Занять окошко в процедурном кабинете'.",
                    )
                    return self.form_invalid(form)
                else:
                    print("✅ Предварительная проверка процедурной записи пройдена")

            # ВАЖНО: Сначала сохраняем основную запись
            print("💾 СОХРАНЕНИЕ ОСНОВНОЙ ЗАПИСИ В БД")
            self.object = form.save(commit=True)
            print(f"✅ Основная запись сохранена в БД: ID={self.object.id}")

            # Обрабатываем процедурную запись если нужно
            procedural_result = None
            if needs_procedural:
                print("🔄 СОЗДАНИЕ ПРОЦЕДУРНОЙ ЗАПИСИ")
                try:
                    procedural_result = form.create_procedural_appointment(self.object)
                    if not procedural_result:
                        # Откатываем транзакцию если не удалось создать процедурную запись
                        transaction.savepoint_rollback(sid)
                        messages.error(
                            self.request,
                            "Не удалось создать запись в процедурном кабинете. Пожалуйста, попробуйте другое время.",
                        )
                        return self.form_invalid(form)
                    print(f"✅ Процедурная запись создана: ID={procedural_result.id}")
                except forms.ValidationError as e:
                    # Откатываем транзакцию при ошибке валидации
                    transaction.savepoint_rollback(sid)
                    messages.error(self.request, str(e))
                    return self.form_invalid(form)
                except Exception as e:
                    # Откатываем транзакцию при любой другой ошибке
                    transaction.savepoint_rollback(sid)
                    print(f"❌ Ошибка при создании процедурной записи: {str(e)}")
                    messages.error(
                        self.request,
                        f"Ошибка при создании записи в процедурном кабинете: {str(e)}",
                    )
                    return self.form_invalid(form)

            # Обрабатываем последовательные записи если нужно
            self._create_consecutive_appointments(self.object, form)

            # Если все успешно - коммитим транзакцию
            transaction.savepoint_commit(sid)

            if created:
                messages.success(self.request, "Запись успешно создана!")
            else:
                messages.success(
                    self.request,
                    f"Запись успешно создана для существующего пациента: {patient.get_full_name()}",
                )

            print("🔔 КОНЕЦ FORM_VALID - УСПЕХ")
            return HttpResponseRedirect(self.get_success_url())

        except forms.ValidationError as e:
            print(f"❌ Ошибка валидации в form_valid: {str(e)}")
            if sid:
                transaction.savepoint_rollback(sid)
            messages.error(self.request, str(e))
            return self.form_invalid(form)

        except IntegrityError as e:
            print(f"❌ Ошибка IntegrityError в form_valid: {str(e)}")
            if sid:
                transaction.savepoint_rollback(sid)
            messages.error(self.request, f"Ошибка при создании записи: {str(e)}")
            return self.form_invalid(form)

        except Exception as e:
            print(f"❌ Неожиданная ошибка в form_valid: {str(e)}")
            if sid:
                transaction.savepoint_rollback(sid)
            import traceback

            print(f"❌ Traceback: {traceback.format_exc()}")
            messages.error(self.request, f"Неожиданная ошибка: {str(e)}")
            return self.form_invalid(form)

    def _create_consecutive_appointments(self, main_appointment, form):
        """Создание последовательных записей (второй услуги или двух слотов)"""
        appointment_type = form.cleaned_data.get("appointment_type")

        if appointment_type in ["additional", "two_slots"]:
            next_slot = main_appointment.time_slot.get_next_consecutive_slot()

            if next_slot:
                if appointment_type == "additional":
                    consecutive_appointment = Appointment(
                        time_slot=next_slot,
                        patient=main_appointment.patient,
                        service=form.cleaned_data["additional_service"],
                        insurance_type=main_appointment.insurance_type,
                        status=main_appointment.status,
                        is_consecutive=True,
                        previous_appointment=main_appointment,
                        comment=f"Последовательная запись к {main_appointment.service.name}",
                    )
                else:
                    consecutive_appointment = Appointment(
                        time_slot=next_slot,
                        patient=main_appointment.patient,
                        service=main_appointment.service,
                        insurance_type=main_appointment.insurance_type,
                        status=main_appointment.status,
                        is_consecutive=True,
                        previous_appointment=main_appointment,
                        occupies_two_slots=True,
                        comment=f"Продолжение услуги {main_appointment.service.name}",
                    )
                consecutive_appointment.save()

    def _check_patient_exists(self, patient_data):
        """Проверяет существование пациента и возвращает объект пациента если найден"""
        surname = patient_data.get("surname")
        first_name = patient_data.get("first_name")
        date_of_birth = patient_data.get("date_of_birth")

        if not surname or not first_name:
            return None

        # Базовый поиск по ФИО
        query = Patient.objects.filter(
            surname__iexact=surname, first_name__iexact=first_name
        )

        # Если указана дата рождения, добавляем в фильтр
        if date_of_birth:
            query = query.filter(date_of_birth=date_of_birth)

        return query.first()

    def get_success_url(self):
        # Используем self.object.time_slot.date вместо self.object.time_slot.date
        return reverse("timetable:schedule_day") + f"?date={self.object.time_slot.date}"


class AppointmentUpdateView(LoginRequiredMixin, UpdateView):
    """Полное редактирование записи на прием"""

    model = Appointment
    form_class = AppointmentUpdateForm
    template_name = "timetable/appointment_update_form.html"

    def get_success_url(self):
        return reverse_lazy("timetable:schedule_day") + f"?date={self.object.date}"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["current_appointment"] = self.object
        # ДОБАВЬТЕ ЭТУ СТРОКУ: передаем врача в форму
        kwargs["doctor"] = self.object.doctor
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["time_slot"] = self.object.time_slot
        context["doctor"] = self.object.time_slot.doctor

        # Получаем информацию о следующем слоте для отображения
        next_slot = self.object.time_slot.get_next_consecutive_slot()
        context["next_slot"] = next_slot

        # Информация о текущей записи
        context["current_appointment"] = self.object

        return context

    def get_initial(self):
        initial = super().get_initial()
        # Заполняем поля пациента из существующей записи
        patient = self.object.patient
        initial.update(
            {
                "surname": patient.surname,
                "first_name": patient.first_name,
                "last_name": patient.last_name,
                "phone_number": patient.phone_number,
                "card_number": patient.card_number,
                "date_of_birth": patient.date_of_birth,
            }
        )

        return initial

    def form_valid(self, form):
        # Сохраняем информацию о старом слоте для сообщения
        old_time_slot = self.object.time_slot
        new_time_slot = form.cleaned_data["time_slot"]

        # Сохраняем запись
        response = super().form_valid(form)

        # Добавляем сообщение об изменении
        if old_time_slot != new_time_slot:
            messages.success(
                self.request,
                f"Запись успешно обновлена. Время изменено с {old_time_slot.date} {old_time_slot.start_time} на {new_time_slot.date} {new_time_slot.start_time}",
            )
        else:
            messages.success(self.request, "Запись успешно обновлена.")

        return response


class AppointmentDeleteView(LoginRequiredMixin, DeleteView):
    """Удаление записи на прием"""

    model = Appointment
    template_name = "timetable/appointment_confirm_delete.html"

    def get_success_url(self):
        date = self.object.date
        return reverse_lazy("timetable:schedule_day") + f"?date={date}"

    def delete(self, request, *args, **kwargs):
        appointment = self.get_object()

        # Удаляем ВСЕ записи, которые ссылаются на эту запись как на предыдущую
        # Это включает процедурные записи и любые другие связанные записи
        related_appointments = Appointment.objects.filter(
            previous_appointment=appointment
        )
        related_count = related_appointments.count()

        # Удаляем связанные записи
        related_appointments.delete()

        # Удаляем основную запись
        result = super().delete(request, *args, **kwargs)

        # Сообщение пользователю
        if related_count > 0:
            messages.success(
                self.request,
                f"Запись и {related_count} связанных записей успешно удалены.",
            )
        else:
            messages.success(self.request, "Запись успешно удалена.")

        return result


class RescheduleRequestsView(LoginRequiredMixin, ListView):
    """Список запросов на перезапись"""

    model = Appointment
    template_name = "timetable/reschedule_requests.html"
    context_object_name = "appointments"

    def get_queryset(self):
        return Appointment.objects.filter(
            needs_reschedule=True,
            status__in=[
                Appointment.AppointmentStatus.SCHEDULED,
                Appointment.AppointmentStatus.CONFIRMED,
            ],
        ).select_related(
            "patient", "time_slot__doctor", "time_slot__cabinet", "service"
        )
