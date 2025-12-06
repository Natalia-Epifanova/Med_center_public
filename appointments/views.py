import json
from datetime import datetime

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import render, redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, UpdateView, DeleteView

from appointments.forms import (
    AppointmentForm,
    AppointmentUpdateForm,
    ProceduralAppointmentForm,
    ProceduralAppointmentUpdateForm,
)
from appointments.models import Appointment
from timetable.models import TimeSlot, Cabinet, Doctor
from timetable.views import get_status_badge_class


# Create your views here.
class AppointmentCreateView(CreateView):
    model = Appointment
    form_class = AppointmentForm
    template_name = "appointments/appointment_form.html"

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
    template_name = "appointments/appointment_update_form.html"

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
    template_name = "appointments/appointment_confirm_delete.html"

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


class ProceduralAppointmentCreateView(LoginRequiredMixin, CreateView):
    """Создание записи в процедурный кабинет без привязки к слоту"""

    model = Appointment
    form_class = ProceduralAppointmentForm
    template_name = "appointments/procedural_appointment_form.html"

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
    template_name = "appointments/procedural_appointment_update_form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["current_appointment"] = self.object
        kwargs["selected_date"] = self.object.date
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Получаем выбранные анализы для передачи в JavaScript
        selected_tests = self.object.selected_blood_tests.all()

        # ВАЖНОЕ ИСПРАВЛЕНИЕ: Получаем ID самих анализов крови
        initial_test_ids = [test.blood_test.id for test in selected_tests]

        # ДЛЯ ОТЛАДКИ
        print(f"DEBUG: Appointment ID: {self.object.id}")
        print(
            f"DEBUG: Selected AppointmentBloodTest objects count: {selected_tests.count()}"
        )
        print(f"DEBUG: BloodTest IDs: {initial_test_ids}")
        print(f"DEBUG: JSON dumps result: {json.dumps(initial_test_ids)}")

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
