import json
from datetime import datetime

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DeleteView, DetailView, UpdateView

from appointments.forms.forms import (
    AppointmentForm,
    AppointmentSimpleEditForm,
    ProceduralAppointmentForm,
    ProceduralAppointmentUpdateForm,
)
from appointments.models import Appointment, AppointmentChain
from timetable.models import Cabinet, Doctor, TimeSlot
from timetable.utils import get_status_badge_class
from users.permissions.decorators import medical_admin_or_admin_required
from users.permissions.mixins import MedicalAdminOrAdminRequiredMixin


class AppointmentCreateView(MedicalAdminOrAdminRequiredMixin, CreateView):
    model = Appointment
    form_class = AppointmentForm
    template_name = "appointments/appointment_form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        time_slot = TimeSlot.objects.get(pk=self.kwargs["time_slot_id"])
        kwargs["time_slot"] = time_slot
        kwargs["doctor"] = time_slot.doctor  # Убедитесь, что передается doctor
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        time_slot = TimeSlot.objects.get(pk=self.kwargs["time_slot_id"])

        # Получаем следующий слот для отображения в форме
        next_slot = time_slot.get_next_consecutive_slot()

        context.update(
            {
                "time_slot": time_slot,
                "doctor": time_slot.doctor,  # Убедитесь, что передается в шаблон
                "next_slot": next_slot,
            }
        )
        return context

    @transaction.atomic
    def form_valid(self, form):
        try:
            # ВАЖНОЕ ИСПРАВЛЕНИЕ: Проверяем форму еще раз перед сохранением
            if not form.is_valid():
                # Если есть ошибки, показываем их пользователю
                for field, errors in form.errors.items():
                    for error in errors:
                        messages.error(self.request, f"Ошибка в поле {field}: {error}")
                return self.form_invalid(form)

            # Сохраняем результат form.save() в self.object
            self.object = form.save()
            messages.success(self.request, "Запись успешно создана!")
            return HttpResponseRedirect(self.get_success_url())

        except ValidationError as e:
            # Ловим ValidationError из формы
            messages.error(self.request, str(e))
            return self.form_invalid(form)
        except Exception as e:
            messages.error(self.request, f"Ошибка при создании записи: {str(e)}")
            return self.form_invalid(form)

    def get_success_url(self):
        # Теперь self.object будет доступен
        return reverse("timetable:schedule_day") + f"?date={self.object.time_slot.date}"

    def create_additional_appointment(self, main_appointment, appointment_data):
        """Создание дополнительной записи с проверкой пересечения времени"""

        # Получаем время основной записи
        main_time_slot = main_appointment.time_slot
        main_start = main_time_slot.start_time
        main_end = main_time_slot.end_time
        main_date = main_time_slot.date

        # Получаем время дополнительной записи
        additional_time_slot = TimeSlot.objects.get(id=appointment_data["time_slot_id"])
        additional_start = additional_time_slot.start_time
        additional_end = additional_time_slot.end_time
        additional_date = additional_time_slot.date

        # Проверяем, что даты совпадают (если это важно)
        if main_date != additional_date:
            # Разные даты - нет пересечения
            pass
        else:
            # Проверяем пересечение времени
            if additional_start < main_end and main_start < additional_end:
                raise ValidationError(
                    f"Время дополнительной записи ({additional_start.strftime('%H:%M')}-{additional_end.strftime('%H:%M')}) "
                    f"пересекается с временем основной записи ({main_start.strftime('%H:%M')}-{main_end.strftime('%H:%M')})"
                )


class AppointmentDetailView(MedicalAdminOrAdminRequiredMixin, DetailView):
    """Только просмотр записи - никакого редактирования"""

    model = Appointment
    template_name = "appointments/appointment_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        appointment = self.object

        # Собираем связанные записи для отображения
        related_appointments = appointment.get_chain_appointments()
        context["related_appointments"] = related_appointments
        context["has_related"] = len(related_appointments) > 1

        return context


class AppointmentSimpleEditView(MedicalAdminOrAdminRequiredMixin, UpdateView):
    """Простое редактирование - только слот, услуга, тип оплаты"""

    model = Appointment
    form_class = AppointmentSimpleEditForm
    template_name = "appointments/appointment_edit_simple.html"

    def get_success_url(self):
        messages.success(self.request, f"Запись #{self.object.id} успешно обновлена")
        return reverse("appointments:appointment_detail", kwargs={"pk": self.object.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["appointment"] = self.object
        return context


class AppointmentDeleteOptionsView(MedicalAdminOrAdminRequiredMixin, DeleteView):
    """Удаление с выбором опций"""

    model = Appointment
    template_name = "appointments/appointment_delete_options.html"

    # Исправляем метод get_success_url
    def get_success_url(self):
        # Получаем объект записи (уже удаленный)
        appointment = self.object

        # Если объект существует и у него есть дата, возвращаем на эту дату
        if appointment and hasattr(appointment, "date") and appointment.date:
            return (
                reverse_lazy("timetable:schedule_day")
                + f"?date={appointment.date.strftime('%Y-%m-%d')}"
            )

        # Иначе возвращаем на сегодняшнюю дату
        return (
            reverse_lazy("timetable:schedule_day")
            + f"?date={timezone.now().date().strftime('%Y-%m-%d')}"
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        appointment = self.object

        # Получаем ВСЕ связанные записи
        all_related = self.find_all_related_appointments(appointment)
        context["related_appointments"] = all_related
        context["has_related"] = len(all_related) > 1

        return context

    def find_all_related_appointments(self, appointment):
        """Находит ВСЕ связанные записи рекурсивно"""
        found = set()

        def find_recursive(app):
            if app in found:
                return

            found.add(app)

            # 1. Через AppointmentChain
            # Записи, где app - основная
            for chain in AppointmentChain.objects.filter(main_appointment=app):
                find_recursive(chain.related_appointment)

            # Записи, где app - связанная
            for chain in AppointmentChain.objects.filter(related_appointment=app):
                find_recursive(chain.main_appointment)

            # 2. Через previous_appointment
            # Следующие записи
            next_app = Appointment.objects.filter(previous_appointment=app).first()
            if next_app:
                find_recursive(next_app)

            # Предыдущие записи
            if app.previous_appointment:
                find_recursive(app.previous_appointment)

        find_recursive(appointment)
        return sorted(found, key=lambda x: (x.date, x.start_time))

    @transaction.atomic
    def delete(self, request, *args, **kwargs):
        """Обрабатывает DELETE запрос"""
        self.object = self.get_object()

        # Сохраняем дату перед удалением, чтобы использовать в redirect
        appointment_date = self.object.date
        appointment_id = self.object.id

        # Определяем действие из POST данных или GET параметров
        action = request.POST.get("action", request.GET.get("action", "single"))

        try:
            if action == "with_related" or action == "all":
                # Находим все связанные записи
                all_appointments = self.find_all_related_appointments(self.object)
                appointment_ids = [a.id for a in all_appointments]

                # ВАЖНО: Удаляем в обратном порядке, чтобы избежать проблем с foreign key
                deleted_count = 0
                for appointment in reversed(all_appointments):
                    try:
                        # Сохраняем ID для логов
                        app_id = appointment.id

                        # Удаляем запись (это вызовет каскадное удаление связанных объектов)
                        appointment.delete()

                        deleted_count += 1

                    except Exception as e:
                        messages.error(request, f"Ошибка при удалении: {str(e)}")

                messages.success(request, f"Удалено {deleted_count} записей")

            else:
                # Удаляем только эту запись
                appointment_id = self.object.id
                self.object.delete()
                messages.success(request, f"Запись #{appointment_id} удалена")

        except Exception as e:
            messages.error(request, f"Ошибка при удалении: {str(e)}")
            # Возвращаем обратно на страницу удаления если ошибка
            return self.get(request, *args, **kwargs)

        # Перенаправляем на расписание НА ТУ ЖЕ ДАТУ
        return redirect(
            reverse("timetable:schedule_day")
            + f"?date={appointment_date.strftime('%Y-%m-%d')}"
        )

    def post(self, request, *args, **kwargs):
        """Обрабатывает POST запрос (делегируем delete)"""
        return self.delete(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        """Обрабатывает GET запрос для отображения формы"""
        try:
            return super().get(request, *args, **kwargs)
        except Appointment.DoesNotExist:
            # Если запись уже удалена, перенаправляем на расписание
            messages.info(request, "Эта запись уже была удалена")
            # Попытаемся получить дату из URL параметров
            date_param = request.GET.get("date")
            if date_param:
                return redirect(
                    reverse("timetable:schedule_day") + f"?date={date_param}"
                )
            return redirect("timetable:schedule_day")


class ProceduralAppointmentCreateView(MedicalAdminOrAdminRequiredMixin, CreateView):
    """Создание записи в процедурный кабинет с поддержкой цепочек"""

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

        # Находим процедурный кабинет и врача-медсестру
        self.procedural_cabinet = Cabinet.objects.get(number=6)
        self.nurse_doctor = Doctor.objects.filter(specialization="nurse").first()

        # Передаем selected_date в форму
        kwargs["selected_date"] = self.selected_date
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Для цепочек нам нужен ID врача-медсестры
        nurse_doctor_id = self.nurse_doctor.id if self.nurse_doctor else None

        context.update(
            {
                "selected_date": self.selected_date,
                "procedural_cabinet": self.procedural_cabinet,
                "nurse_doctor": self.nurse_doctor,
                "nurse_doctor_id": nurse_doctor_id,  # Добавляем для JavaScript
            }
        )

        return context

    def get_success_url(self):
        return reverse("timetable:schedule_day") + f"?date={self.selected_date}"


class ProceduralAppointmentDetailView(MedicalAdminOrAdminRequiredMixin, DetailView):
    """Просмотр процедурной записи - используем обычный шаблон"""

    model = Appointment
    template_name = "appointments/appointment_detail.html"  # Используем тот же шаблон

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        appointment = self.object

        # Собираем связанные записи для отображения
        related_appointments = appointment.get_chain_appointments()
        context["related_appointments"] = related_appointments
        context["has_related"] = len(related_appointments) > 1

        return context


class ProceduralAppointmentUpdateView(MedicalAdminOrAdminRequiredMixin, UpdateView):
    """Редактирование записи в процедурный кабинет"""

    model = Appointment
    form_class = ProceduralAppointmentUpdateForm  # Используем новую упрощенную форму
    template_name = "appointments/procedural_appointment_edit_simple.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["current_appointment"] = self.object
        kwargs["selected_date"] = self.object.date
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Получаем выбранные анализы
        selected_tests = self.object.selected_blood_tests.all()
        initial_test_ids = [test.blood_test.id for test in selected_tests]

        context.update(
            {
                "selected_date": self.object.date,
                "procedural_cabinet": self.object.cabinet,
                "nurse_doctor": self.object.doctor,
                "initial_test_ids": json.dumps(initial_test_ids),
                "current_appointment": self.object,
                "appointment": self.object,
            }
        )
        return context

    def get_initial(self):
        initial = super().get_initial()

        # Заполняем время
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
                self.request,
                f"Запись #{self.object.id} в процедурный кабинет успешно обновлена!",
            )
            return response
        except Exception as e:
            messages.error(self.request, f"Ошибка при обновлении записи: {str(e)}")
            return self.form_invalid(form)

    def get_success_url(self):
        return reverse("appointments:appointment_detail", kwargs={"pk": self.object.pk})


@require_POST
@csrf_exempt
@medical_admin_or_admin_required
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
        return JsonResponse({"success": False, "error": str(e)}, status=500)
