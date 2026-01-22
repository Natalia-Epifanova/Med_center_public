import os

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import (
    CreateView,
    DetailView,
    UpdateView,
    ListView,
    DeleteView,
)

from treatment.forms import DoctorTreatmentForm
from treatment.models import MKB10Diagnosis, DoctorTreatment
from treatment.services import TreatmentDocumentGenerator


class DoctorTreatmentCreateView(LoginRequiredMixin, CreateView):
    model = DoctorTreatment
    form_class = DoctorTreatmentForm
    template_name = "treatment/treatment_form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Получаем appointment из URL
        appointment_id = self.kwargs.get("appointment_id")
        if appointment_id:
            from appointments.models import Appointment

            context["appointment"] = Appointment.objects.get(id=appointment_id)
        return context

    def form_valid(self, form):
        # Привязываем appointment к форме
        appointment_id = self.kwargs.get("appointment_id")
        if appointment_id:
            from appointments.models import Appointment

            form.instance.appointment = Appointment.objects.get(id=appointment_id)
        return super().form_valid(form)

    def get_success_url(self):
        """Перенаправляем на детальную страницу приема"""
        return reverse_lazy("treatment:treatment_detail", kwargs={"pk": self.object.id})


class DoctorTreatmentDetailView(LoginRequiredMixin, DetailView):
    model = DoctorTreatment
    template_name = "treatment/treatment_detail.html"
    context_object_name = "treatment"


class DoctorTreatmentUpdateView(LoginRequiredMixin, UpdateView):
    model = DoctorTreatment
    form_class = DoctorTreatmentForm
    template_name = "treatment/treatment_form.html"

    def get_context_data(self, **kwargs):
        """Добавляем appointment в контекст"""
        context = super().get_context_data(**kwargs)
        # Получаем объект лечения
        treatment = self.get_object()
        # Добавляем appointment в контекст
        context["appointment"] = treatment.appointment
        return context

    def get_success_url(self):
        return reverse_lazy("treatment:treatment_detail", kwargs={"pk": self.object.id})


class DoctorTreatmentDeleteView(LoginRequiredMixin, DeleteView):
    model = DoctorTreatment
    template_name = "treatment/treatment_confirm_delete.html"

    def get_success_url(self):
        # После удаления возвращаемся к истории приемов пациента
        patient_id = self.object.appointment.patient.id
        return reverse_lazy(
            "treatment:patient_treatments", kwargs={"patient_id": patient_id}
        )


class PatientTreatmentListView(LoginRequiredMixin, ListView):
    """Список всех приемов конкретного пациента"""

    template_name = "treatment/patient_treatments.html"
    context_object_name = "treatments"

    def get_queryset(self):
        patient_id = self.kwargs.get("patient_id")
        from patients.models import Patient

        patient = Patient.objects.get(id=patient_id)

        # Получаем все приемы врача для этого пациента
        return (
            DoctorTreatment.objects.filter(appointment__patient=patient)
            .select_related("appointment__time_slot__doctor", "appointment__service")
            .order_by(
                "-appointment__time_slot__date", "-appointment__time_slot__start_time"
            )
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        patient_id = self.kwargs.get("patient_id")
        from patients.models import Patient

        context["patient"] = Patient.objects.get(id=patient_id)
        return context


class TreatmentPrintView(LoginRequiredMixin, View):
    """Генерация Word документа для приема врача"""

    def get(self, request, *args, **kwargs):
        from .models import DoctorTreatment

        treatment = get_object_or_404(DoctorTreatment, pk=kwargs["pk"])

        try:
            # Генерируем Word документ
            filepath, filename = TreatmentDocumentGenerator.generate_treatment_docx(
                treatment
            )

            # Читаем файл и возвращаем как ответ
            with open(filepath, "rb") as f:
                response = HttpResponse(
                    f.read(),
                    content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
                response["Content-Disposition"] = f'attachment; filename="{filename}"'

            # Удаляем временный файл
            try:
                os.remove(filepath)
            except:
                pass

            return response

        except Exception as e:
            # В случае ошибки возвращаем сообщение
            return HttpResponse(f"Ошибка при генерации документа: {str(e)}", status=500)


@login_required
def mkb10_search(request):
    """Поиск диагнозов МКБ-10 для AJAX запросов"""
    query = request.GET.get("q", "")
    if len(query) < 2:
        return JsonResponse([], safe=False)

    diagnoses = MKB10Diagnosis.search_by_name_or_code(query)[
        :10
    ]  # Ограничиваем 10 результатами
    results = [
        {
            "id": d.id,
            "code": d.code,
            "name": d.name,
            "chapter": d.chapter,
            "block": d.block,
        }
        for d in diagnoses
    ]

    return JsonResponse(results, safe=False)
