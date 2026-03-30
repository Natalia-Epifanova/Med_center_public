import logging
import os
from datetime import datetime

from django.conf import settings
from docxtpl import DocxTemplate

from patients.utils import get_russian_month_name
from treatment.utils import get_specialization_genitive


logger = logging.getLogger(__name__)


class TreatmentDocumentGenerator:
    """Класс для генерации документов Word для приемов врача"""

    @staticmethod
    def generate_treatment_docx(treatment):
        """Генерация документа Word для приема врача"""
        logger.info(
            "TreatmentDocumentGenerator.generate_treatment_docx: start treatment_id=%s appointment_id=%s patient_id=%s",
            getattr(treatment, "id", None),
            getattr(treatment.appointment, "id", None),
            getattr(treatment.appointment.patient, "id", None),
        )

        try:
            if treatment.appointment.time_slot.date:
                treatment_date = treatment.appointment.time_slot.date.strftime(
                    "%d.%m.%Y"
                )
                treatment_year = treatment.appointment.time_slot.date.strftime("%Y")
            else:
                treatment_date = ""
                treatment_year = datetime.now().strftime("%Y")

            if treatment.appointment.patient.date_of_birth:
                patient_birth_date = (
                    treatment.appointment.patient.date_of_birth.strftime("%d.%m.%Y")
                )
                patient_age = treatment.appointment.patient.age
                patient_birth_year = (
                    treatment.appointment.patient.date_of_birth.strftime("%Y")
                )
            else:
                patient_birth_date = ""
                patient_age = ""
                patient_birth_year = ""

            if treatment.mkb10_diagnoses.exists():
                mkb10_diagnoses = "\n".join(
                    diagnosis.code for diagnosis in treatment.mkb10_diagnoses.all()
                )
            else:
                mkb10_diagnoses = ""

            specialization_display = (
                treatment.appointment.time_slot.doctor.get_specialization_display()
            )
            specialization_genitive = get_specialization_genitive(
                specialization_display
            )

            context = {
                "patient_full_name": treatment.appointment.patient.full_name,
                "patient_surname": treatment.appointment.patient.surname,
                "patient_first_name": treatment.appointment.patient.first_name,
                "patient_last_name": treatment.appointment.patient.last_name or "",
                "patient_birth_date": patient_birth_date,
                "patient_b_day": (
                    treatment.appointment.patient.date_of_birth.strftime("%d")
                    if treatment.appointment.patient.date_of_birth
                    else ""
                ),
                "patient_b_month": (
                    treatment.appointment.patient.date_of_birth.strftime("%m")
                    if treatment.appointment.patient.date_of_birth
                    else ""
                ),
                "patient_b_month_name": (
                    get_russian_month_name(
                        treatment.appointment.patient.date_of_birth.month
                    )
                    if treatment.appointment.patient.date_of_birth
                    else ""
                ),
                "patient_b_year": patient_birth_year,
                "patient_age": patient_age,
                "doctor_full_name": f"{treatment.appointment.time_slot.doctor.surname} "
                f"{treatment.appointment.time_slot.doctor.first_name} "
                f"{treatment.appointment.time_slot.doctor.last_name}",
                "doctor_short_name": (
                    f"{treatment.appointment.time_slot.doctor.surname} "
                    f"{treatment.appointment.time_slot.doctor.first_name[0]}. "
                    f"{treatment.appointment.time_slot.doctor.last_name[0]}."
                ),
                "doctor_surname": treatment.appointment.time_slot.doctor.surname,
                "doctor_first_name": treatment.appointment.time_slot.doctor.first_name,
                "doctor_last_name": treatment.appointment.time_slot.doctor.last_name
                or "",
                "doctor_specialization": (
                    treatment.appointment.time_slot.doctor.get_specialization_display()
                ),
                "doctor_specialization_genitive": specialization_genitive,
                "treatment_date": treatment_date,
                "treatment_day": (
                    treatment.appointment.time_slot.date.strftime("%d")
                    if treatment.appointment.time_slot.date
                    else ""
                ),
                "treatment_month": (
                    treatment.appointment.time_slot.date.strftime("%m")
                    if treatment.appointment.time_slot.date
                    else ""
                ),
                "treatment_month_name": (
                    get_russian_month_name(treatment.appointment.time_slot.date.month)
                    if treatment.appointment.time_slot.date
                    else ""
                ),
                "treatment_year": treatment_year,
                "appointment_time": (
                    treatment.appointment.time_slot.start_time.strftime("%H:%M")
                    if treatment.appointment.time_slot.start_time
                    else ""
                ),
                "complaints": treatment.complaints or "",
                "life_anamnesis": treatment.life_anamnesis or "",
                "disease_anamnesis": treatment.disease_anamnesis or "",
                "objective_status": treatment.objective_status or "",
                "additional_surveys": treatment.additional_surveys or "",
                "diagnosis": treatment.diagnosis or "",
                "mkb10_diagnoses": mkb10_diagnoses,
                "recommendations": treatment.recommendations or "",
            }

            template_path = os.path.join(
                settings.BASE_DIR,
                "treatment",
                "templates",
                "treatment",
                "docs",
                "treatment_template.docx",
            )

            doc = DocxTemplate(template_path)
            doc.render(context)

            filename = (
                f"Прием_{treatment.appointment.patient.surname}_"
                f"{treatment_date.replace('.', '_')}_{datetime.now().strftime('%H%M%S')}.docx"
            )
            filepath = os.path.join(settings.MEDIA_ROOT, "temp_docs", filename)

            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            doc.save(filepath)

            logger.info(
                "TreatmentDocumentGenerator.generate_treatment_docx: success treatment_id=%s filepath=%s",
                getattr(treatment, "id", None),
                filepath,
            )
            return filepath, filename
        except Exception:
            logger.exception(
                "TreatmentDocumentGenerator.generate_treatment_docx: error treatment_id=%s appointment_id=%s",
                getattr(treatment, "id", None),
                getattr(treatment.appointment, "id", None),
            )
            raise
