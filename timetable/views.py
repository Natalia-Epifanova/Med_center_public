from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseRedirect
from django.urls import reverse_lazy
from django.views.generic import (
    TemplateView,
    CreateView,
    UpdateView,
    DeleteView,
    DetailView,
)

from timetable.forms import TimeSlotForm, TimeSlotUpdateForm
from timetable.models import TimeSlot


class HomeView(TemplateView):
    template_name = "timetable/home.html"


class TimeSlotCreateView(LoginRequiredMixin, CreateView):
    model = TimeSlot
    form_class = TimeSlotForm
    template_name = "timetable/schedule_create.html"
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
                single_start_time = form.cleaned_data.get("single_start_time")
                single_end_time = form.cleaned_data.get("single_end_time")
                single_slot_type = form.cleaned_data.get("single_slot_type")
                single_description = form.cleaned_data.get("single_description") or ""

                if single_start_time and single_end_time:
                    slot = TimeSlot(
                        date=date,
                        cabinet=cabinet,
                        doctor=doctor,
                        start_time=single_start_time,
                        end_time=single_end_time,
                        slot_type=single_slot_type,
                        description=single_description,
                    )
                    created_slots.append(slot)

            elif add_type == "multiple":
                start_time = form.cleaned_data.get("multiple_start_time")
                end_time = form.cleaned_data.get("multiple_end_time")
                interval = form.cleaned_data.get("interval")

                if start_time and end_time and interval:
                    current_time = start_time
                    while current_time < end_time:
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

            for slot in created_slots:
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

        return HttpResponseRedirect(self.get_success_url())

    def form_invalid(self, form):
        return super().form_invalid(form)


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
