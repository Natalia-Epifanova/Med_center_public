from django import forms
from django.forms import ModelForm

from timetable.mixins import StyleFormMixin
from treatment.models import DoctorTreatment


class DoctorTreatmentForm(StyleFormMixin, ModelForm):
    # Добавляем скрытые поля для данных копирования
    copy_from_treatment = forms.IntegerField(widget=forms.HiddenInput(), required=False)
    copy_fields = forms.CharField(widget=forms.HiddenInput(), required=False)

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
            "copy_from_treatment",
            "copy_fields",
        ]
