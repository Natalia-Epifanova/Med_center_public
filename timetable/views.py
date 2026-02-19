from collections import defaultdict
from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.cache import cache
from django.db.models import Sum
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
from patients.models import WaitlistPatient
from timetable.forms import (
    CopyScheduleForm,
    CopyWeeklyScheduleForm,
    DayCommentForm,
    TimeSlotForm,
    TimeSlotUpdateForm,
    CabinetDayCommentForm,
)
from timetable.models import Cabinet, DayComment, Doctor, TimeSlot, CabinetDayComment
from timetable.services import CopyScheduleService, TimeSlotService
from users.permissions.decorators import admin_required, medical_admin_or_admin_required
from users.permissions.mixins import (
    AdminRequiredMixin,
    MedicalAdminOrAdminRequiredMixin,
)


class HomeView(LoginRequiredMixin, TemplateView):
    template_name = "timetable/home.html"
    login_url = "/users/login/"


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
        slot_date = self.object.date
        return reverse_lazy("timetable:schedule_day") + f"?date={slot_date}"

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
    login_url = "/users/login/"

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

        # Получаем комментарий дня (всегда показываем форму если админ)
        try:
            day_comment = DayComment.objects.get(date=selected_date)
            context["day_comment"] = day_comment
            context["day_comment_form"] = DayCommentForm(instance=day_comment)
        except DayComment.DoesNotExist:
            # Создаем пустой комментарий для формы
            context["day_comment"] = None
            context["day_comment_form"] = DayCommentForm(
                initial={"date": selected_date}
            )

        # ВСЕГДА показываем комментарий дня если пользователь админ
        context["show_day_comment"] = (
            self.request.user.groups.filter(name="Admin").exists()
            or context["day_comment"] is not None
        )

        # Получаем даты приема врачей для текущего месяца
        context["doctor_schedule_dates"] = self.get_doctor_schedule_dates(selected_date)

        # Получаем слоты на выбранную дату
        slots = TimeSlot.objects.filter(date=selected_date).select_related(
            "cabinet", "doctor"
        )
        # Желаемый порядок кабинетов
        desired_order = [4, 6, 5, 1, 2, 3, 25, 26]

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
        cabinet_comments = {}
        for cabinet in cabinets_sorted:
            try:
                comment = CabinetDayComment.objects.get(
                    date=selected_date, cabinet=cabinet
                )
                cabinet_comments[cabinet.id] = {
                    "comment": comment,
                    "form": CabinetDayCommentForm(instance=comment),
                }
            except CabinetDayComment.DoesNotExist:
                cabinet_comments[cabinet.id] = {
                    "comment": None,
                    "form": CabinetDayCommentForm(
                        initial={"date": selected_date, "cabinet": cabinet.id}
                    ),
                }

        context["cabinet_comments"] = cabinet_comments

        # Проверка прав для отображения формы
        user = self.request.user
        context["can_edit_cabinet_comments"] = user.groups.filter(
            name__in=["Admin", "MedicalAdmin"]
        ).exists()

        return context

    @staticmethod
    def get_doctor_schedule_dates(current_date):
        """Получает даты приема врачей на текущий месяц с кэшированием"""
        cache_key = f"doctor_schedule_dates_{current_date.year}_{current_date.month}"
        cached_data = cache.get(cache_key)

        if cached_data:
            return cached_data

        # Определяем начало и конец текущего месяца
        month_start = current_date.replace(day=1)
        if month_start.month == 12:
            month_end = month_start.replace(year=month_start.year + 1, month=1, day=1)
        else:
            month_end = month_start.replace(month=month_start.month + 1, day=1)

        # Получаем уникальные даты приема врачей
        slots_this_month = (
            TimeSlot.objects.filter(
                date__gte=month_start,
                date__lt=month_end,
            )
            .exclude(doctor__specialization="nurse")
            .values(
                "doctor__surname",
                "doctor__first_name",
                "doctor__last_name",
                "doctor__specialization",
                "date",
            )
            .distinct()
            .order_by("doctor__surname", "date")
        )

        # Группируем по врачам
        doctor_dates = defaultdict(list)
        doctor_specializations = {}

        for slot in slots_this_month:
            doctor_key = f"{slot['doctor__surname']} {slot['doctor__first_name'][0]}.{slot['doctor__last_name'][0]}."
            if slot["date"] not in doctor_dates[doctor_key]:
                doctor_dates[doctor_key].append(slot["date"])
            if doctor_key not in doctor_specializations:
                # Получаем отображаемое название специализации
                doctor_specializations[doctor_key] = dict(
                    Doctor.DoctorSpecialization.choices
                ).get(slot["doctor__specialization"], slot["doctor__specialization"])

        # Преобразуем в список
        result = []
        for doctor_name in sorted(doctor_dates.keys()):
            result.append(
                {
                    "name": doctor_name,
                    "dates": sorted(doctor_dates[doctor_name]),
                    "specialization": doctor_specializations.get(doctor_name, ""),
                }
            )

        # Кэшируем на 1 час
        cache.set(cache_key, result, 3600)

        return result


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


class RescheduleRequestsView(MedicalAdminOrAdminRequiredMixin, TemplateView):
    """Список запросов на перезапись + лист ожидания"""

    template_name = "timetable/reschedule_requests.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Существующие записи с флагом needs_reschedule
        appointments = Appointment.objects.filter(
            needs_reschedule=True,
            status__in=[
                Appointment.AppointmentStatus.SCHEDULED,
                Appointment.AppointmentStatus.CONFIRMED,
            ],
        ).select_related(
            "patient", "time_slot__doctor", "time_slot__cabinet", "service"
        )

        # Лист ожидания (пациенты без текущих записей)
        waitlist_patients = (
            WaitlistPatient.objects.all()
            .select_related("doctor")
            .order_by("-created_at")
        )

        context.update(
            {
                "appointments": appointments,
                "waitlist_patients": waitlist_patients,
            }
        )

        return context


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


@login_required
@require_POST
@medical_admin_or_admin_required
def save_cabinet_day_comment(request):
    """Сохранение комментария кабинета"""
    date_str = request.POST.get("date")
    cabinet_id = request.POST.get("cabinet_id")
    comment_text = request.POST.get("comment", "").strip()

    try:
        date = datetime.strptime(date_str, "%Y-%m-%d").date()
        cabinet = Cabinet.objects.get(id=cabinet_id)

        # Создаем или обновляем комментарий
        comment_obj, created = CabinetDayComment.objects.update_or_create(
            date=date,
            cabinet=cabinet,
            defaults={
                "comment": comment_text,
            },
        )

        return JsonResponse(
            {
                "success": True,
                "message": "Комментарий сохранен",
                "created": created,
                "comment_id": comment_obj.id,
            }
        )

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)


class DoctorReportView(AdminRequiredMixin, TemplateView):
    template_name = "timetable/doctor_report.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["today"] = timezone.now().date()

        # Проверяем, есть ли дата в kwargs (если доступ через URL с датой)
        date_from_url = kwargs.get("date")

        if date_from_url:
            # Если доступ через URL типа /doctor-report/2026-01-21/
            try:
                start_date = datetime.strptime(date_from_url, "%Y-%m-%d").date()
                end_date = start_date
                is_period = False
                start_date_str = date_from_url
                end_date_str = date_from_url
            except ValueError:
                start_date = timezone.now().date()
                end_date = start_date
                is_period = False
                start_date_str = ""
                end_date_str = ""
                messages.error(self.request, "Неверный формат даты")
        else:
            # Получаем даты из GET параметров
            start_date_str = self.request.GET.get("start_date", "")
            end_date_str = self.request.GET.get("end_date", "")

            # Если не указаны даты, используем сегодняшнюю дату
            if not start_date_str:
                start_date = timezone.now().date()
                end_date = start_date
                is_period = False
            else:
                try:
                    start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
                    if end_date_str:
                        end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
                    else:
                        end_date = start_date
                    is_period = True
                except ValueError:
                    start_date = timezone.now().date()
                    end_date = start_date
                    is_period = False
                    messages.error(self.request, "Неверный формат даты")

        # Определяем названия ОМС услуг (только для ревматологов)
        OMS_PRIMARY = "Прием (осмотр, консультация) врача-ревматолога первичный"
        OMS_REPEAT = "Прием (осмотр, консультация) врача-ревматолога повторный (не позднее месяца от первичного)"

        # Определяем ключевые слова для PRP терапии
        PRP_KEYWORDS = ["PRP терапия", "PRP-терапия", "плазмолифтинг"]

        # Получаем записи за период
        appointments = (
            Appointment.objects.filter(
                time_slot__date__gte=start_date,
                time_slot__date__lte=end_date,
                status="completed",
            )
            .select_related(
                "time_slot__doctor",
                "service",
                "patient",
            )
            .order_by("time_slot__date")
        )

        # Группируем по врачам
        report_data = {}

        # Добавляем счетчики для сумм
        total_analyses_sum = 0
        total_xray_sum = 0

        for appointment in appointments:
            doctor = appointment.time_slot.doctor
            service = appointment.service
            service_name = service.name if service else ""
            service_category = service.category if service else None
            insurance_type = appointment.insurance_type
            service_price = service.price if service else 0

            if doctor not in report_data:
                report_data[doctor] = {
                    "oms_total": 0,
                    "oms_primary": 0,
                    "oms_repeat": 0,
                    "manipulations": 0,
                    "prp_therapy": 0,
                    "other_services": {},
                    "doctor_total_sum": 0,
                }

            # Проверяем тип оплаты через insurance_type
            is_oms = insurance_type == "oms"

            # Проверяем категорию услуги
            is_medical_blockade = service_category == "medical_blockades"

            # Проверяем, является ли услуга PRP терапией
            is_prp_therapy = any(
                keyword.lower() in service_name.lower() for keyword in PRP_KEYWORDS
            )

            # Если это медицинская блокада (манипуляция)
            if is_medical_blockade:
                if is_prp_therapy:
                    report_data[doctor]["prp_therapy"] += 1
                else:
                    report_data[doctor]["manipulations"] += 1
            else:
                # Для ревматологов считаем ОМС отдельно
                if doctor.specialization == "rheumatologist" and is_oms:
                    report_data[doctor]["oms_total"] += 1

                    # Проверяем тип консультации для ОМС
                    if service_name == OMS_PRIMARY:
                        report_data[doctor]["oms_primary"] += 1
                    elif service_name == OMS_REPEAT:
                        report_data[doctor]["oms_repeat"] += 1
                    else:
                        if service_name not in report_data[doctor]["other_services"]:
                            report_data[doctor]["other_services"][service_name] = 0
                        report_data[doctor]["other_services"][service_name] += 1
                else:
                    if service_name not in report_data[doctor]["other_services"]:
                        report_data[doctor]["other_services"][service_name] = 0
                    report_data[doctor]["other_services"][service_name] += 1

            if service and service.category:
                if service.category == "analyzes":  # анализы
                    # Проверяем, есть ли связанные анализы крови
                    if hasattr(appointment, "selected_blood_tests"):
                        # Суммируем стоимость всех выбранных анализов
                        tests_price = (
                            appointment.selected_blood_tests.aggregate(
                                total=Sum("blood_test__price")
                            )["total"]
                            or 0
                        )
                        total_analyses_sum += tests_price

                        # Добавляем также стоимость забора крови, если это отдельная услуга
                        if service.name.lower() in ["забор крови", "взятие крови"]:
                            total_analyses_sum += service_price
                    else:
                        total_analyses_sum += service_price
                elif service.category == "xray":  # рентген
                    total_xray_sum += service_price

            if doctor.surname == "Платицына" or "Платицына" in str(doctor):
                # Для анализов используем полную сумму
                if service and service.category == "analyzes":
                    report_data[doctor][
                        "doctor_total_sum"
                    ] += appointment.get_total_price
                else:
                    report_data[doctor]["doctor_total_sum"] += service_price

        context.update(
            {
                "start_date": start_date,
                "end_date": end_date,
                "is_period": is_period,
                "report_data": report_data,
                "selected_start_date": start_date_str,
                "selected_end_date": end_date_str,
                "total_analyses_sum": total_analyses_sum,
                "total_xray_sum": total_xray_sum,
            }
        )
        return context


class DoctorReportPeriodView(AdminRequiredMixin, TemplateView):
    """Страница выбора периода для отчета по врачам"""

    template_name = "timetable/doctor_report_period.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Устанавливаем даты по умолчанию
        today = timezone.now().date()
        first_day_of_month = today.replace(day=1)

        context["default_start"] = first_day_of_month
        context["default_end"] = today

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


@login_required
@require_POST
@admin_required
def move_doctor_to_cabinet(request):
    """Перенос врача с его слотами в другой кабинет"""
    try:
        doctor_id = request.POST.get("doctor_id")
        current_cabinet_id = request.POST.get("current_cabinet_id")
        new_cabinet_id = request.POST.get("new_cabinet_id")
        date_str = request.POST.get("date")
        move_appointments = request.POST.get("move_appointments") == "on"

        if not all([doctor_id, current_cabinet_id, new_cabinet_id, date_str]):
            return JsonResponse(
                {"success": False, "error": "Не все обязательные поля заполнены"}
            )

        # Преобразуем дату
        date = datetime.strptime(date_str, "%Y-%m-%d").date()

        # Получаем объекты
        doctor = Doctor.objects.get(id=doctor_id)
        current_cabinet = Cabinet.objects.get(id=current_cabinet_id)
        new_cabinet = Cabinet.objects.get(id=new_cabinet_id)

        # Проверяем, что текущий и новый кабинеты разные
        if current_cabinet.id == new_cabinet.id:
            return JsonResponse(
                {
                    "success": False,
                    "error": "Текущий и новый кабинет не могут совпадать",
                }
            )

        # Получаем все слоты врача в текущем кабинете на указанную дату
        slots = TimeSlot.objects.filter(
            date=date, doctor=doctor, cabinet=current_cabinet
        )

        # Проверяем конфликты в новом кабинете
        for slot in slots:
            conflicting_slots = TimeSlot.objects.filter(
                date=date,
                cabinet=new_cabinet,
                start_time__lt=slot.end_time,
                end_time__gt=slot.start_time,
                slot_type="working",
            ).exclude(doctor=doctor)

            if conflicting_slots.exists():
                # Простое сообщение без деталей
                return JsonResponse(
                    {
                        "success": False,
                        "error": "Обнаружены конфликты в расписании нового кабинета",
                    }
                )

        # Переносим слоты
        slots_moved = 0
        appointments_moved = 0

        for slot in slots:
            # Получаем все записи на этот слот
            appointments = slot.appointments.all() if move_appointments else []

            # Изменяем кабинет слота
            slot.cabinet = new_cabinet
            slot.save()
            slots_moved += 1

            # Если нужно, переносим записи
            if move_appointments:
                appointments_moved += appointments.count()

        # Логируем действие
        from django.contrib.admin.models import LogEntry, CHANGE
        from django.contrib.contenttypes.models import ContentType

        LogEntry.objects.log_action(
            user_id=request.user.id,
            content_type_id=ContentType.objects.get_for_model(TimeSlot).id,
            object_id="",
            object_repr=f"Перенос врача {doctor.surname} из каб.{current_cabinet.number} в каб.{new_cabinet.number} на {date}",
            action_flag=CHANGE,
            change_message=f"Перенесено слотов: {slots_moved}, записей: {appointments_moved}",
        )

        return JsonResponse(
            {
                "success": True,
                "message": "Врач успешно перенесен",
                "slots_moved": slots_moved,
                "appointments_moved": appointments_moved,
            }
        )

    except (Doctor.DoesNotExist, Cabinet.DoesNotExist) as e:
        return JsonResponse({"success": False, "error": "Не найден врач или кабинет"})
    except ValueError as e:
        return JsonResponse(
            {"success": False, "error": f"Ошибка формата данных: {str(e)}"}
        )
    except Exception as e:
        return JsonResponse(
            {"success": False, "error": f"Внутренняя ошибка сервера: {str(e)}"}
        )
