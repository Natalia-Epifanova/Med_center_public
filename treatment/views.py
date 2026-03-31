import os
import logging

from django.contrib import messages
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

logger = logging.getLogger(__name__)


class DoctorTreatmentCreateView(LoginRequiredMixin, CreateView):
    model = DoctorTreatment
    form_class = DoctorTreatmentForm
    template_name = "treatment/treatment_form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        appointment_id = self.kwargs.get("appointment_id")
        if appointment_id:
            from appointments.models import Appointment

            appointment = Appointment.objects.get(id=appointment_id)
            context["appointment"] = appointment

            # Проверяем, есть ли у пациента предыдущие приемы
            has_previous_treatments = (
                DoctorTreatment.objects.filter(appointment__patient=appointment.patient)
                .exclude(appointment_id=appointment_id)
                .exists()
            )

            context["has_previous_treatments"] = has_previous_treatments
            context["patient_id"] = appointment.patient.id
            logger.info(
                "DoctorTreatmentCreateView.get_context_data: appointment_id=%s patient_id=%s doctor_id=%s has_previous_treatments=%s",
                appointment.id,
                getattr(appointment.patient, "id", None),
                getattr(appointment.time_slot.doctor, "id", None),
                has_previous_treatments,
            )

        return context

    def get_initial(self):
        """Заполняем начальные данные если были переданы для копирования"""
        initial = super().get_initial()

        # Получаем данные из GET-параметров для предзаполнения
        copy_from = self.request.GET.get("copy_from")
        copy_fields = self.request.GET.get("copy_fields", "")

        if copy_from and copy_fields:
            try:
                previous_treatment = DoctorTreatment.objects.get(id=copy_from)
                fields_to_copy = copy_fields.split(",")
                logger.info(
                    "DoctorTreatmentCreateView.get_initial: copy_from_treatment_id=%s copied_fields=%s",
                    previous_treatment.id,
                    fields_to_copy,
                )

                if "complaints" in fields_to_copy:
                    initial["complaints"] = previous_treatment.complaints
                if "life_anamnesis" in fields_to_copy:
                    initial["life_anamnesis"] = previous_treatment.life_anamnesis
                if "disease_anamnesis" in fields_to_copy:
                    initial["disease_anamnesis"] = previous_treatment.disease_anamnesis
                if "objective_status" in fields_to_copy:
                    initial["objective_status"] = previous_treatment.objective_status
                if "additional_surveys" in fields_to_copy:
                    initial["additional_surveys"] = (
                        previous_treatment.additional_surveys
                    )
                if "diagnosis" in fields_to_copy:
                    initial["diagnosis"] = previous_treatment.diagnosis
                if "recommendations" in fields_to_copy:
                    initial["recommendations"] = previous_treatment.recommendations
                if (
                    "mkb10_diagnoses" in fields_to_copy
                    and previous_treatment.mkb10_diagnoses.exists()
                ):
                    initial["mkb10_diagnoses"] = (
                        previous_treatment.mkb10_diagnoses.all()
                    )

            except DoctorTreatment.DoesNotExist:
                logger.warning(
                    "DoctorTreatmentCreateView.get_initial: previous_treatment_not_found copy_from=%s",
                    copy_from,
                )
                pass

        return initial

    def form_valid(self, form):
        try:
            appointment_id = self.kwargs.get("appointment_id")
            logger.info(
                "DoctorTreatmentCreateView.form_valid: start appointment_id=%s user_id=%s",
                appointment_id,
                getattr(self.request.user, "id", None),
            )
            if appointment_id:
                from appointments.models import Appointment

                form.instance.appointment = Appointment.objects.get(id=appointment_id)
            response = super().form_valid(form)
            logger.info(
                "DoctorTreatmentCreateView.form_valid: success treatment_id=%s appointment_id=%s patient_id=%s",
                getattr(self.object, "id", None),
                getattr(self.object.appointment, "id", None),
                getattr(self.object.appointment.patient, "id", None),
            )
            return response
        except Exception:
            logger.exception(
                "DoctorTreatmentCreateView.form_valid: error appointment_id=%s user_id=%s",
                self.kwargs.get("appointment_id"),
                getattr(self.request.user, "id", None),
            )
            form.add_error(
                None,
                "Не удалось сохранить прием. Данные формы остались на странице, проверьте их и попробуйте сохранить еще раз.",
            )
            messages.error(
                self.request,
                "Сохранение приема не завершилось. Проверьте данные формы и повторите попытку.",
            )
            return self.form_invalid(form)

    def get_success_url(self):
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
        logger.info(
            "DoctorTreatmentUpdateView.get_context_data: treatment_id=%s appointment_id=%s patient_id=%s",
            treatment.id,
            getattr(treatment.appointment, "id", None),
            getattr(treatment.appointment.patient, "id", None),
        )
        return context

    def get_success_url(self):
        return reverse_lazy("treatment:treatment_detail", kwargs={"pk": self.object.id})

    def form_valid(self, form):
        try:
            logger.info(
                "DoctorTreatmentUpdateView.form_valid: start treatment_id=%s appointment_id=%s user_id=%s",
                getattr(form.instance, "id", None),
                getattr(form.instance.appointment, "id", None),
                getattr(self.request.user, "id", None),
            )
            response = super().form_valid(form)
            logger.info(
                "DoctorTreatmentUpdateView.form_valid: success treatment_id=%s appointment_id=%s",
                getattr(self.object, "id", None),
                getattr(self.object.appointment, "id", None),
            )
            return response
        except Exception:
            logger.exception(
                "DoctorTreatmentUpdateView.form_valid: error treatment_id=%s appointment_id=%s user_id=%s",
                getattr(form.instance, "id", None),
                getattr(form.instance.appointment, "id", None),
                getattr(self.request.user, "id", None),
            )
            form.add_error(
                None,
                "Не удалось сохранить изменения приема. Данные формы остались на странице, проверьте их и попробуйте еще раз.",
            )
            messages.error(
                self.request,
                "Сохранение изменений не завершилось. Проверьте данные формы и повторите попытку.",
            )
            return self.form_invalid(form)


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
        logger.info(
            "PatientTreatmentListView.get_queryset: patient_id=%s user_id=%s",
            patient.id,
            getattr(self.request.user, "id", None),
        )

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
        logger.info(
            "TreatmentPrintView.get: start treatment_id=%s appointment_id=%s patient_id=%s user_id=%s",
            treatment.id,
            getattr(treatment.appointment, "id", None),
            getattr(treatment.appointment.patient, "id", None),
            getattr(request.user, "id", None),
        )

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
            except Exception:
                logger.warning(
                    "TreatmentPrintView.get: temporary_file_cleanup_failed filepath=%s",
                    filepath,
                    exc_info=True,
                )
                pass

            logger.info(
                "TreatmentPrintView.get: success treatment_id=%s filename=%s",
                treatment.id,
                filename,
            )
            return response

        except Exception as e:
            logger.exception(
                "TreatmentPrintView.get: error treatment_id=%s user_id=%s",
                kwargs["pk"],
                getattr(request.user, "id", None),
            )
            # В случае ошибки возвращаем сообщение
            return HttpResponse(f"Ошибка при генерации документа: {str(e)}", status=500)


@login_required
def mkb10_search(request):
    """Поиск диагнозов МКБ-10 для AJAX запросов"""
    query = request.GET.get("q", "")
    if len(query) < 2:
        logger.info(
            "mkb10_search: skipped_short_query query=%s user_id=%s",
            query,
            getattr(request.user, "id", None),
        )
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

    logger.info(
        "mkb10_search: success query=%s results_count=%s user_id=%s",
        query,
        len(results),
        getattr(request.user, "id", None),
    )
    return JsonResponse(results, safe=False)


class PatientTreatmentsForCopyView(LoginRequiredMixin, ListView):
    """Список приемов пациента для копирования (только для AJAX)"""

    template_name = "treatment/treatment_copy_select.html"
    context_object_name = "treatments"

    def get_queryset(self):
        patient_id = self.kwargs.get("patient_id")
        from patients.models import Patient

        patient = Patient.objects.get(id=patient_id)
        logger.info(
            "PatientTreatmentsForCopyView.get_queryset: patient_id=%s current_appointment=%s user_id=%s",
            patient.id,
            self.request.GET.get("current_appointment", None),
            getattr(self.request.user, "id", None),
        )

        return (
            DoctorTreatment.objects.filter(appointment__patient=patient)
            .select_related("appointment__time_slot__doctor", "appointment__service")
            .exclude(appointment_id=self.request.GET.get("current_appointment", None))
            .order_by(
                "-appointment__time_slot__date", "-appointment__time_slot__start_time"
            )
        )

    def get(self, request, *args, **kwargs):
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            treatments = self.get_queryset()
            data = [
                {
                    "id": t.id,
                    "date": t.appointment.time_slot.date.strftime("%d.%m.%Y"),
                    "time": t.appointment.time_slot.start_time.strftime("%H:%M"),
                    "doctor": f"{t.appointment.time_slot.doctor.surname} {t.appointment.time_slot.doctor.first_name[0]}.{t.appointment.time_slot.doctor.last_name[0]}.",
                    "service": t.appointment.service.name,
                    "has_complaints": bool(t.complaints),
                    "has_life_anamnesis": bool(t.life_anamnesis),
                    "has_disease_anamnesis": bool(t.disease_anamnesis),
                    "has_objective_status": bool(t.objective_status),
                    "has_additional_surveys": bool(t.additional_surveys),
                    "has_diagnosis": bool(t.diagnosis),
                    "has_mkb10": t.mkb10_diagnoses.exists(),
                    "has_recommendations": bool(t.recommendations),
                }
                for t in treatments[:20]  # Ограничиваем 20 последними приемами
            ]
            logger.info(
                "PatientTreatmentsForCopyView.get: ajax_success patient_id=%s returned_count=%s user_id=%s",
                self.kwargs.get("patient_id"),
                len(data),
                getattr(request.user, "id", None),
            )
            return JsonResponse({"treatments": data})
        return super().get(request, *args, **kwargs)


@login_required
def get_previous_treatment_data(request, pk):
    """Получение данных конкретного приема для копирования"""
    treatment = get_object_or_404(DoctorTreatment, pk=pk)
    logger.info(
        "get_previous_treatment_data: treatment_id=%s appointment_id=%s user_id=%s",
        treatment.id,
        getattr(treatment.appointment, "id", None),
        getattr(request.user, "id", None),
    )

    data = {
        "complaints": treatment.complaints,
        "life_anamnesis": treatment.life_anamnesis,
        "disease_anamnesis": treatment.disease_anamnesis,
        "objective_status": treatment.objective_status,
        "additional_surveys": treatment.additional_surveys,
        "diagnosis": treatment.diagnosis,
        "recommendations": treatment.recommendations,
        "mkb10_diagnoses": list(treatment.mkb10_diagnoses.values("id", "code", "name")),
    }

    return JsonResponse(data)
