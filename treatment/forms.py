from django.forms import ModelForm

from timetable.mixins import StyleFormMixin
from treatment.models import DoctorTreatment


class DoctorTreatmentForm(StyleFormMixin, ModelForm):

    class Meta:
        model = DoctorTreatment
        fields = [
            "complaints",
            "life_anamnesis",
            "disease_anamnesis",
            "objective_status",
            "additional_surveys",
            "diagnosis",
            "mkb10_diagnoses",
            "recommendations",
        ]
