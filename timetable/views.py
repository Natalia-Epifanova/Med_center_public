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
    FormView,
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
from timetable.services import TimeSlotService
from timetable.utils import save_slots_with_conflict_check, create_time_slots


class HomeView(TemplateView):
    template_name = "timetable/home.html"


class TimeSlotCreateView(LoginRequiredMixin, FormView):  # Изменяем наследование
    form_class = TimeSlotForm
    template_name = "timetable/schedule_create.html"
    success_url = reverse_lazy("timetable:schedule_create")

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

            saved_count = TimeSlotService.save_slots_with_conflict_check(slots)

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
            return TimeSlotService.create_time_slots(
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
        # Желаемый порядок кабинетов
        desired_order = [4, 6, 1, 2, 3, 25, 26]

        # Получаем уникальные кабинеты
        all_cabinets = list(set(slot.cabinet for slot in slots))

        # Сортируем кабинеты: сначала в желаемом порядке, потом остальные
        cabinets_in_order = []
        other_cabinets = []

        for cabinet in all_cabinets:
            if cabinet.number in desired_order:
                cabinets_in_order.append(cabinet)
            else:
                other_cabinets.append(cabinet)

        # Сортируем кабинеты в желаемом порядке
        cabinets_in_order.sort(key=lambda x: desired_order.index(x.number))
        # Сортируем остальные кабинеты по номеру
        other_cabinets.sort(key=lambda x: x.number)

        # Объединяем списки
        cabinets_sorted = cabinets_in_order + other_cabinets

        schedule_data = {}
        for cabinet in cabinets_sorted:
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
        context.update(
            {
                "time_slot": time_slot,
                "doctor": time_slot.doctor,
                "next_slot": time_slot.get_next_consecutive_slot(),
            }
        )
        return context

    @transaction.atomic
    def form_valid(self, form):
        try:
            # Сохраняем результат form.save() в self.object
            self.object = form.save()
            messages.success(self.request, "Запись успешно создана!")
            return HttpResponseRedirect(self.get_success_url())

        except Exception as e:
            messages.error(self.request, f"Ошибка при создании записи: {str(e)}")
            return self.form_invalid(form)

    def get_success_url(self):
        # Теперь self.object будет доступен
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
