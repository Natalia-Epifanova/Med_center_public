from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.decorators.http import require_POST
from django.views.generic import (
    DeleteView,
    DetailView,
    FormView,
    ListView,
    TemplateView,
    UpdateView,
)

from appointments.models import Appointment
from timetable.forms import (
    CopyScheduleForm,
    CopyWeeklyScheduleForm,
    DayCommentForm,
    TimeSlotForm,
    TimeSlotUpdateForm,
)
from timetable.models import Cabinet, DayComment, Doctor, TimeSlot
from timetable.services import CopyScheduleService, TimeSlotService
from users.permissions.decorators import admin_required
from users.permissions.mixins import (
    AdminRequiredMixin,
    MedicalAdminOrAdminRequiredMixin,
)


class HomeView(TemplateView):
    template_name = "timetable/home.html"


class TimeSlotCreateView(AdminRequiredMixin, FormView):
    form_class = TimeSlotForm
    template_name = "timetable/schedule_create.html"
    success_url = reverse_lazy("timetable:schedule_create")

    def get_initial(self):
        """Предзаполняем дату из GET параметров"""
        initial = super().get_initial()
        date_param = self.request.GET.get("date")
        if date_param:
            try:
                # Проверяем корректность даты
                datetime.strptime(date_param, "%Y-%m-%d").date()
                initial["date"] = date_param
            except ValueError:
                pass
        return initial

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

    @staticmethod
    def _create_single_slot(form, date, cabinet, doctor):
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

    @staticmethod
    def _create_multiple_slots(form, date, cabinet, doctor):
        """Создание нескольких слотов"""
        start_time = form.cleaned_data.get("multiple_start_time")
        end_time = form.cleaned_data.get("multiple_end_time")
        interval = form.cleaned_data.get("interval")

        if start_time and end_time and interval:
            return TimeSlotService.create_time_slots(
                date, cabinet, doctor, start_time, end_time, interval
            )
        return []


class TimeSlotUpdateView(MedicalAdminOrAdminRequiredMixin, UpdateView):
    model = TimeSlot
    form_class = TimeSlotUpdateForm
    template_name = "timetable/timeslot_form.html"

    def get_success_url(self):
        return reverse_lazy("timetable:timeslot_detail", kwargs={"pk": self.object.pk})

    def form_valid(self, form):
        messages.success(self.request, "Слот успешно обновлен.")
        return super().form_valid(form)


class TimeSlotDetailView(MedicalAdminOrAdminRequiredMixin, DetailView):
    model = TimeSlot
    template_name = "timetable/timeslot_detail.html"
    context_object_name = "slot"


class TimeSlotDeleteView(MedicalAdminOrAdminRequiredMixin, DeleteView):
    model = TimeSlot
    template_name = "timetable/timeslot_confirm_delete.html"

    def get_success_url(self):
        # Получаем дату из удаляемого слота
        slot_date = self.object.date
        return reverse_lazy("timetable:schedule_day") + f"?date={slot_date}"

    def delete(self, request, *args, **kwargs):
        # Сохраняем дату перед удалением
        self.object = self.get_object()
        slot_date = self.object.date

        messages.success(self.request, "Слот успешно удален.")

        # Выполняем удаление
        response = super().delete(request, *args, **kwargs)
        return response


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

        try:
            day_comment = DayComment.objects.get(date=selected_date)
            context["day_comment"] = day_comment
            context["day_comment_form"] = DayCommentForm(instance=day_comment)
        except DayComment.DoesNotExist:
            context["day_comment"] = None
            context["day_comment_form"] = DayCommentForm(
                initial={"date": selected_date}
            )

            # Проверяем права пользователя
        context["user_can_edit_comments"] = (
            self.request.user.groups.filter(name="Admin").exists()
            if self.request.user.is_authenticated
            else False
        )

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
        context["cabinets"] = Cabinet.objects.all().order_by("number")
        context["doctors"] = Doctor.objects.all().order_by("surname", "first_name")
        return context


class EmergencySlotCreateView(MedicalAdminOrAdminRequiredMixin, View):
    """Создание экстренного слота"""

    def post(self, request):
        date_str = request.POST.get("date", "")

        try:
            cabinet_id = request.POST.get("cabinet")
            doctor_id = request.POST.get("doctor")
            start_time = request.POST.get("start_time")
            end_time = request.POST.get("end_time")
            slot_type = request.POST.get("slot_type", "working")
            description = request.POST.get("description", "")

            # Валидация данных
            if not all([date_str, cabinet_id, doctor_id, start_time, end_time]):
                messages.error(request, "Все обязательные поля должны быть заполнены")
                return HttpResponseRedirect(
                    f"{reverse('timetable:schedule_day')}?date={date_str}"
                )

            # Проверка форматов времени
            try:
                date = datetime.strptime(date_str, "%Y-%m-%d").date()
                start_time_obj = datetime.strptime(start_time, "%H:%M").time()
                end_time_obj = datetime.strptime(end_time, "%H:%M").time()

                if start_time_obj >= end_time_obj:
                    messages.error(
                        request, "Время окончания должно быть позже времени начала"
                    )
                    return HttpResponseRedirect(
                        f"{reverse('timetable:schedule_day')}?date={date_str}"
                    )
            except ValueError as e:
                messages.error(request, f"Неверный формат времени или даты: {str(e)}")
                return HttpResponseRedirect(
                    f"{reverse('timetable:schedule_day')}?date={date_str}"
                )

            # Проверка конфликтов перед созданием слота
            conflicting_slots = TimeSlot.objects.filter(
                date=date,
                cabinet_id=cabinet_id,
                doctor_id=doctor_id,
                start_time__lt=end_time_obj,
                end_time__gt=start_time_obj,
            ).exists()

            if conflicting_slots:
                messages.error(
                    request, "Выбранное время конфликтует с существующими слотами"
                )
                return HttpResponseRedirect(
                    f"{reverse('timetable:schedule_day')}?date={date_str}"
                )

            # Создание и сохранение слота
            slot = TimeSlot(
                date=date,
                cabinet_id=cabinet_id,
                doctor_id=doctor_id,
                start_time=start_time_obj,
                end_time=end_time_obj,
                slot_type=slot_type,
                description=description,
            )

            slot.save()
            messages.success(request, "Экстренный слот успешно создан")

        except Exception as e:
            messages.error(request, f"Ошибка при создании слота: {str(e)}")

        return HttpResponseRedirect(
            f"{reverse('timetable:schedule_day')}?date={date_str}"
        )


class RescheduleRequestsView(MedicalAdminOrAdminRequiredMixin, ListView):
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


@login_required
@require_POST
@admin_required
def save_day_comment(request):
    """Сохранение комментария дня (только для администраторов)"""
    date_str = request.POST.get("date")
    comment_text = request.POST.get("comment", "").strip()

    try:
        date = datetime.strptime(date_str, "%Y-%m-%d").date()

        # Создаем или обновляем комментарий
        comment_obj, created = DayComment.objects.update_or_create(
            date=date,
            defaults={
                "comment": comment_text,
            },
        )

        return JsonResponse(
            {"success": True, "message": "Комментарий сохранен", "created": created}
        )

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)


class DoctorReportView(AdminRequiredMixin, TemplateView):
    template_name = "timetable/doctor_report.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        date_str = self.kwargs.get("date")

        try:
            report_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            report_date = datetime.now().date()

        # Получаем все записи на указанную дату с правильными связями
        appointments = Appointment.objects.filter(
            time_slot__date=report_date,
            status__in=[
                "scheduled",
                "confirmed",
                "completed",
            ],
        ).select_related("time_slot__doctor", "service", "patient")

        # Группируем по врачам и услугам
        report_data = {}
        for appointment in appointments:
            # Получаем врача через time_slot
            doctor = appointment.time_slot.doctor
            service_name = appointment.service.name

            if doctor not in report_data:
                report_data[doctor] = {}

            if service_name not in report_data[doctor]:
                report_data[doctor][service_name] = 0

            report_data[doctor][service_name] += 1

        context.update(
            {
                "report_date": report_date,
                "report_data": report_data,
                "selected_date": report_date,
            }
        )
        return context


class CopyScheduleView(AdminRequiredMixin, FormView):
    """Копирование расписания с одного дня на другой"""

    form_class = CopyScheduleForm
    template_name = "timetable/copy_schedule.html"
    success_url = reverse_lazy("timetable:schedule_day")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["request"] = self.request
        return kwargs

    def get_initial(self):
        """Предзаполняем даты из GET параметров"""
        initial = super().get_initial()

        date_param = self.request.GET.get("date")
        if date_param:
            try:
                source_date = datetime.strptime(date_param, "%Y-%m-%d").date()
                initial["source_date"] = source_date
                # По умолчанию копируем на следующую неделю
                initial["target_date"] = source_date + timedelta(days=7)
            except ValueError:
                pass

        return initial

    def form_valid(self, form):
        try:
            source_date = form.cleaned_data["source_date"]
            target_date = form.cleaned_data["target_date"]
            copy_type = form.cleaned_data["copy_type"]
            cabinets = form.cleaned_data.get("cabinets")
            doctors = form.cleaned_data.get("doctors")
            conflict_resolution = form.cleaned_data["conflict_resolution"]

            # Копируем расписание
            result = CopyScheduleService.copy_schedule(
                source_date=source_date,
                target_date=target_date,
                copy_type=copy_type,
                cabinets=cabinets,
                doctors=doctors,
                conflict_resolution=conflict_resolution,
                user=self.request.user,
                request=self.request,
            )

            if result["success"]:
                messages.success(
                    self.request,
                    f"Успешно скопировано {result['created_count']} слотов с {source_date} на {target_date}. "
                    f"Пропущено {result['skipped_count']} слотов из-за конфликтов.",
                )
            else:
                messages.error(
                    self.request, f"Ошибка при копировании: {result['error']}"
                )

        except Exception as e:
            messages.error(self.request, f"Ошибка при копировании расписания: {str(e)}")

        return super().form_valid(form)

    def get_success_url(self):
        # Возвращаемся на целевую дату
        target_date = self.request.POST.get("target_date")
        if target_date:
            return reverse_lazy("timetable:schedule_day") + f"?date={target_date}"
        return self.success_url


class CopyWeeklyScheduleView(AdminRequiredMixin, FormView):
    """Копирование расписания по недельному шаблону с выбором недель"""

    form_class = CopyWeeklyScheduleForm
    template_name = "timetable/copy_weekly_schedule.html"
    success_url = reverse_lazy("timetable:schedule_day")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Добавляем информацию о выбранных неделях для предпросмотра
        source_week = self.request.GET.get("source_week")
        target_week = self.request.GET.get("target_week")

        if source_week:
            try:
                source_date = datetime.strptime(source_week, "%Y-%m-%d").date()
                context["source_week_dates"] = self.get_week_dates(source_date)
            except ValueError:
                pass

        if target_week:
            try:
                target_date = datetime.strptime(target_week, "%Y-%m-%d").date()
                context["target_week_dates"] = self.get_week_dates(target_date)
            except ValueError:
                pass

        return context

    def get_week_dates(self, start_date):
        """Возвращает список дат недели начиная с понедельника"""
        if start_date.weekday() != 0:
            start_date = start_date - timedelta(days=start_date.weekday())

        week_dates = []
        for i in range(7):
            date = start_date + timedelta(days=i)
            week_dates.append(
                {
                    "date": date,
                    "weekday": date.weekday(),
                    "weekday_name": self.get_weekday_name(date.weekday()),
                    "has_schedule": TimeSlot.objects.filter(date=date).exists(),
                }
            )

        return week_dates

    def get_weekday_name(self, weekday):
        """Возвращает название дня недели"""
        weekdays = {
            0: "Понедельник",
            1: "Вторник",
            2: "Среда",
            3: "Четверг",
            4: "Пятница",
            5: "Суббота",
            6: "Воскресенье",
        }
        return weekdays.get(weekday, "")

    def form_valid(self, form):
        try:
            source_week_start = form.cleaned_data["source_week_start"]
            target_week_start = form.cleaned_data["target_week_start"]
            days_to_copy = [int(day) for day in form.cleaned_data["days_to_copy"]]
            copy_type = form.cleaned_data.get("copy_type", "all")
            cabinets = form.cleaned_data.get("cabinets")
            doctors = form.cleaned_data.get("doctors")
            conflict_resolution = form.cleaned_data.get("conflict_resolution", "skip")

            # Копируем расписание
            result = CopyScheduleService.copy_weekly_schedule(
                source_week_start=source_week_start,
                target_week_start=target_week_start,
                days_to_copy=days_to_copy,
                copy_type=copy_type,
                cabinets=cabinets,
                doctors=doctors,
                conflict_resolution=conflict_resolution,
                user=self.request.user,
                request=self.request,
            )

            if result["success"]:
                messages.success(
                    self.request,
                    f"Успешно скопировано {result['created_count']} слотов "
                    f"({result['days_copied']} дней). "
                    f"Пропущено {result['skipped_count']} слотов.",
                )
            else:
                messages.error(
                    self.request, f"Ошибка при копировании: {result['error']}"
                )

        except Exception as e:
            messages.error(self.request, f"Ошибка при копировании расписания: {str(e)}")
            return self.form_invalid(form)

        return super().form_valid(form)
