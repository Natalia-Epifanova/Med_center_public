import json
from datetime import datetime, timedelta

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.http import HttpResponseRedirect, JsonResponse
from django.urls import reverse_lazy, reverse
from django.utils import timezone
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.views.generic import (
    TemplateView,
    CreateView,
    UpdateView,
    DeleteView,
    DetailView,
    ListView,
    FormView,
)
from django.shortcuts import redirect
from django.contrib import messages

from timetable.forms import (
    TimeSlotForm,
    TimeSlotUpdateForm,
    AppointmentForm,
    AppointmentUpdateForm,
    ProceduralAppointmentForm,
    DayCommentForm,
    ProceduralAppointmentUpdateForm,
    CopyScheduleForm,
)
from timetable.models import TimeSlot, Appointment, Cabinet, Doctor, DayComment
from timetable.services import TimeSlotService, CopyScheduleService


class HomeView(TemplateView):
    template_name = "timetable/home.html"


class TimeSlotCreateView(LoginRequiredMixin, FormView):
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
        context["user_can_edit_comments"] = self.request.user.is_staff

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


class EmergencySlotCreateView(LoginRequiredMixin, View):
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
        kwargs["doctor"] = self.object.doctor
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["time_slot"] = self.object.time_slot
        context["doctor"] = self.object.doctor
        context["current_appointment"] = self.object

        # Получаем информацию о следующем слоте для отображения
        next_slot = self.object.time_slot.get_next_consecutive_slot()
        context["next_slot"] = next_slot

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
        # ИСПРАВЛЕНИЕ: получаем новый слот из time_slot_id
        new_time_slot = form.cleaned_data["time_slot_id"]  # Это объект TimeSlot

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


class ProceduralAppointmentCreateView(LoginRequiredMixin, CreateView):
    """Создание записи в процедурный кабинет без привязки к слоту"""

    model = Appointment
    form_class = ProceduralAppointmentForm
    template_name = "timetable/procedural_appointment_form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        # Получаем дату из GET параметров
        date_str = self.request.GET.get("date")
        if date_str:
            try:
                self.selected_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                self.selected_date = timezone.now().date()
        else:
            self.selected_date = timezone.now().date()

        # Находим процедурный кабинет и врача-медсестр

        self.procedural_cabinet = Cabinet.objects.get(number=6)
        self.nurse_doctor = Doctor.objects.filter(specialization="nurse").first()

        # Передаем selected_date в форму
        kwargs["selected_date"] = self.selected_date
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context.update(
            {
                "selected_date": self.selected_date,
                "procedural_cabinet": self.procedural_cabinet,
                "nurse_doctor": self.nurse_doctor,
            }
        )
        return context

    def form_valid(self, form):
        try:
            # Сохраняем запись
            self.object = form.save()

            messages.success(
                self.request, "Запись в процедурный кабинет создана успешно!"
            )
            return redirect(self.get_success_url())

        except Exception as e:
            messages.error(self.request, f"Ошибка при создании записи: {str(e)}")
            return self.form_invalid(form)

    def get_success_url(self):
        return reverse("timetable:schedule_day") + f"?date={self.selected_date}"


class ProceduralAppointmentUpdateView(LoginRequiredMixin, UpdateView):
    """Редактирование записи в процедурный кабинет"""

    model = Appointment
    form_class = ProceduralAppointmentUpdateForm
    template_name = "timetable/procedural_appointment_update_form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["current_appointment"] = self.object
        kwargs["selected_date"] = self.object.date

        print(f"DEBUG: In get_form_kwargs, request method: {self.request.method}")
        print(f"DEBUG: In get_form_kwargs, request POST data: {self.request.POST}")

        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Получаем выбранные анализы для передачи в JavaScript
        selected_tests = self.object.selected_blood_tests.all()

        # ВАЖНОЕ ИСПРАВЛЕНИЕ: получаем ID самих анализов крови
        initial_test_ids = [test.blood_test.id for test in selected_tests]

        # ДОБАВЬТЕ ДЛЯ ОТЛАДКИ
        print(f"DEBUG: Appointment ID: {self.object.id}")
        print(f"DEBUG: Selected AppointmentBloodTest objects: {list(selected_tests)}")
        print(f"DEBUG: BloodTest IDs: {initial_test_ids}")

        context.update(
            {
                "selected_date": self.object.date,
                "procedural_cabinet": self.object.cabinet,
                "nurse_doctor": self.object.doctor,
                "initial_test_ids": json.dumps(
                    initial_test_ids
                ),  # Используйте json.dumps!
                "current_appointment": self.object,
            }
        )
        return context

    def get_initial(self):
        initial = super().get_initial()

        # Заполняем поля пациента
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

        # Заполняем время из слота
        initial.update(
            {
                "procedural_start_time": self.object.start_time,
                "procedural_end_time": self.object.end_time,
            }
        )

        return initial

    def form_valid(self, form):
        try:
            response = super().form_valid(form)
            messages.success(
                self.request, "Запись в процедурный кабинет успешно обновлена!"
            )
            return response
        except Exception as e:
            messages.error(self.request, f"Ошибка при обновлении записи: {str(e)}")
            return self.form_invalid(form)

    def get_success_url(self):
        return reverse("timetable:schedule_day") + f"?date={self.object.date}"


@login_required
@require_POST
def save_day_comment(request):
    """Сохранение комментария дня (только для администраторов)"""
    if not request.user.is_staff:
        return JsonResponse({"error": "Недостаточно прав"}, status=403)

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


@require_POST
@csrf_exempt
def update_appointment_status(request, pk):
    """AJAX view для обновления статуса записи"""
    try:
        # Проверяем аутентификацию
        if not request.user.is_authenticated:
            return JsonResponse(
                {"success": False, "error": "Требуется авторизация"}, status=403
            )

        appointment = Appointment.objects.get(pk=pk)

        # Получаем статус из POST данных (не из JSON)
        new_status = request.POST.get("status")

        if new_status in dict(Appointment.AppointmentStatus.choices):
            appointment.status = new_status
            appointment.save()

            # Логируем изменение для отладки
            print(f"Статус записи {appointment.id} изменен на: {new_status}")

            return JsonResponse(
                {
                    "success": True,
                    "new_status": appointment.status,
                    "new_status_display": appointment.get_status_display(),
                    "status_class": get_status_badge_class(appointment.status),
                }
            )
        else:
            return JsonResponse(
                {"success": False, "error": "Неверный статус"}, status=400
            )

    except Appointment.DoesNotExist:
        return JsonResponse(
            {"success": False, "error": "Запись не найдена"}, status=404
        )
    except Exception as e:
        print(f"Ошибка при обновлении статуса: {str(e)}")
        return JsonResponse({"success": False, "error": str(e)}, status=500)


def get_status_badge_class(status):
    """Получить CSS класс для бейджа статуса"""
    status_classes = {
        "scheduled": "bg-primary",
        "confirmed": "bg-info",
        "completed": "bg-success",
        "cancelled": "bg-warning",
        "no_show": "bg-danger",
    }
    return status_classes.get(status, "bg-secondary")


class DoctorReportView(TemplateView):
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


class CopyScheduleView(LoginRequiredMixin, FormView):
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


class CopyWeeklyScheduleView(LoginRequiredMixin, TemplateView):
    """Копирование расписания по недельному шаблону"""

    template_name = "timetable/copy_weekly_schedule.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Предзаполняем даты
        today = timezone.now().date()
        monday = today - timedelta(days=today.weekday())
        next_monday = monday + timedelta(days=7)
        end_of_month = today.replace(day=28) + timedelta(days=4)
        end_of_month = end_of_month.replace(day=1) - timedelta(days=1)

        context.update(
            {
                "today": today,
                "start_date": next_monday,
                "end_date": end_of_month,
                "weekdays": [
                    (0, "Понедельник"),
                    (1, "Вторник"),
                    (2, "Среда"),
                    (3, "Четверг"),
                    (4, "Пятница"),
                    (5, "Суббота"),
                    (6, "Воскресенье"),
                ],
            }
        )

        return context

    def post(self, request):
        try:
            start_date_str = request.POST.get("start_date")
            end_date_str = request.POST.get("end_date")
            pattern_days = [int(day) for day in request.POST.getlist("pattern_days")]

            if not pattern_days:
                messages.error(
                    request, "Выберите хотя бы один день недели для копирования"
                )
                return self.get(request)

            start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()

            if start_date >= end_date:
                messages.error(request, "Дата начала должна быть раньше даты окончания")
                return self.get(request)

            # Копируем по шаблону
            result = CopyScheduleService.copy_weekly_pattern(
                start_date=start_date,
                end_date=end_date,
                pattern_days=pattern_days,
                user=request.user,
                request=request,
            )

            if result["success"]:
                success_count = sum(
                    1 for r in result["results"] if r["result"]["success"]
                )
                messages.success(
                    request,
                    f"Успешно создано расписание на {success_count} дней из {result['total_days_processed']}",
                )
            else:
                messages.error(request, f"Ошибка при копировании: {result['error']}")

        except Exception as e:
            messages.error(request, f"Ошибка при копировании расписания: {str(e)}")

        return redirect("timetable:schedule_day")
