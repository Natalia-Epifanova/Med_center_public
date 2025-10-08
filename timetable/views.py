from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import FormView, TemplateView

from timetable.forms import TimeSlotForm
from timetable.models import TimeSlot


class HomeView(TemplateView):
    template_name = "timetable/home.html"


class ScheduleCreateView(LoginRequiredMixin, FormView):
    template_name = "timetable/schedule_create.html"
    form_class = TimeSlotForm
    success_url = reverse_lazy("timetable:schedule_create")

    def form_valid(self, form):
        date = form.cleaned_data["date"]
        cabinet = form.cleaned_data["cabinet"]
        doctor = form.cleaned_data["doctor"]
        add_type = form.cleaned_data["add_type"]

        created_slots = []
        saved_count = 0

        try:
            if add_type == "single":
                slot = TimeSlot(
                    date=date,
                    cabinet=cabinet,
                    doctor=doctor,
                    start_time=form.cleaned_data["single_start_time"],
                    end_time=form.cleaned_data["single_end_time"],
                    slot_type=form.cleaned_data["single_slot_type"],
                    description=form.cleaned_data["single_description"] or "",
                )
                created_slots.append(slot)

            elif add_type == "multiple":
                start_time = form.cleaned_data["multiple_start_time"]
                end_time = form.cleaned_data["multiple_end_time"]
                interval = form.cleaned_data["interval"]

                current_time = start_time
                while current_time < end_time:
                    # Исправленная версия без timezone
                    end_time_slot = (
                        datetime.combine(date, current_time)
                        + timedelta(minutes=interval)
                    ).time()

                    if end_time_slot > end_time:
                        break

                    slot = TimeSlot(
                        date=date,
                        cabinet=cabinet,
                        doctor=doctor,
                        start_time=current_time,
                        end_time=end_time_slot,
                        slot_type="working",
                        description="",
                    )
                    created_slots.append(slot)
                    current_time = end_time_slot

            # Сохраняем слоты с проверкой на дубликаты
            for slot in created_slots:
                # Более строгая проверка на пересечения
                conflicting_slots = TimeSlot.objects.filter(
                    date=slot.date,
                    cabinet=slot.cabinet,
                    start_time__lt=slot.end_time,
                    end_time__gt=slot.start_time,
                )

                if not conflicting_slots.exists():
                    slot.save()
                    saved_count += 1
                else:
                    messages.warning(
                        self.request,
                        f"Слот {slot.start_time}-{slot.end_time} пересекается с существующим",
                    )

            if saved_count > 0:
                messages.success(self.request, f"Успешно создано {saved_count} слотов")
            else:
                messages.warning(self.request, "Не было создано ни одного нового слота")

        except Exception as e:
            messages.error(self.request, f"Ошибка при создании слотов: {str(e)}")
            return self.form_invalid(form)

        return super().form_valid(form)


class ScheduleDayView(LoginRequiredMixin, TemplateView):
    template_name = "timetable/schedule_day.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        date = self.request.GET.get("date")

        if date:
            try:
                selected_date = datetime.strptime(date, "%Y-%m-%d").date()
                context["selected_date"] = selected_date

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

            except ValueError:
                messages.error(self.request, "Неверный формат даты")

        return context
