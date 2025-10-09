from django import forms
from django.forms import ModelForm

from .models import Cabinet, Doctor, TimeSlot, Appointment, MedicalService, Patient


class StyleFormMixin:
    """
    Миксин для стилизации форм. Добавляет CSS-класс 'form-control' ко всем полям формы.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if "class" not in field.widget.attrs:
                field.widget.attrs["class"] = "form-control"


class TimeSlotForm(StyleFormMixin, ModelForm):
    """Упрощенная форма для добавления временных слотов"""

    class Meta:
        model = TimeSlot
        fields = (
            [  # Убираем отсюда поля времени и типа, так как они будут в кастомных полях
                "date",
                "cabinet",
                "doctor",
            ]
        )
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
        }
        labels = {
            "date": "Дата расписания",
            "cabinet": "Кабинет",
            "doctor": "Врач",
        }

    # Оставляем только кастомные поля
    ADD_TYPE_CHOICES = [
        ("single", "Добавить один слот"),
        ("multiple", "Добавить несколько слотов с интервалом"),
    ]
    add_type = forms.ChoiceField(
        label="Тип добавления",
        choices=ADD_TYPE_CHOICES,
        widget=forms.RadioSelect(attrs={"class": "form-check-input"}),
        initial="single",
    )

    # Поля для одиночного добавления
    single_start_time = forms.TimeField(
        label="Время начала",
        widget=forms.TimeInput(attrs={"type": "time"}),
        required=False,
    )
    single_end_time = forms.TimeField(
        label="Время окончания",
        widget=forms.TimeInput(attrs={"type": "time"}),
        required=False,
    )
    single_slot_type = forms.ChoiceField(
        label="Тип слота",
        choices=TimeSlot.SLOT_TYPE_CHOICES,
        initial="working",
        required=False,
    )
    single_description = forms.CharField(
        label="Описание",
        widget=forms.TextInput(attrs={"placeholder": "Например: Обед"}),
        required=False,
        max_length=200,
    )

    # Поля для множественного добавления
    multiple_start_time = forms.TimeField(
        label="Время начала диапазона",
        widget=forms.TimeInput(attrs={"type": "time"}),
        required=False,
    )
    multiple_end_time = forms.TimeField(
        label="Время окончания диапазона",
        widget=forms.TimeInput(attrs={"type": "time"}),
        required=False,
    )
    interval = forms.IntegerField(
        label="Интервал (минуты)",
        min_value=5,
        max_value=120,
        initial=20,
        widget=forms.NumberInput(),
        required=False,
    )

    def clean(self):
        cleaned_data = super().clean()
        add_type = cleaned_data.get("add_type")

        if add_type == "single":
            start_time = cleaned_data.get("single_start_time")
            end_time = cleaned_data.get("single_end_time")

            if not start_time or not end_time:
                raise forms.ValidationError(
                    "Для одиночного слота необходимо указать время начала и окончания"
                )

            if start_time >= end_time:
                raise forms.ValidationError(
                    "Время начала должно быть раньше времени окончания"
                )

        elif add_type == "multiple":
            start_time = cleaned_data.get("multiple_start_time")
            end_time = cleaned_data.get("multiple_end_time")
            interval = cleaned_data.get("interval")

            if not start_time or not end_time:
                raise forms.ValidationError(
                    "Для нескольких слотов необходимо указать время начала и окончания"
                )

            if start_time >= end_time:
                raise forms.ValidationError(
                    "Время начала должно быть раньше времени окончания"
                )

            if not interval or interval <= 0:
                raise forms.ValidationError("Интервал должен быть положительным числом")

        return cleaned_data


class TimeSlotUpdateForm(StyleFormMixin, ModelForm):
    """Форма для редактирования существующего слота"""

    class Meta:
        model = TimeSlot
        fields = [
            "date",
            "cabinet",
            "doctor",
            "start_time",
            "end_time",
            "slot_type",
            "description",
        ]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "start_time": forms.TimeInput(attrs={"type": "time"}),
            "end_time": forms.TimeInput(attrs={"type": "time"}),
            "description": forms.TextInput(attrs={"placeholder": "Например: Обед"}),
        }
        labels = {
            "date": "Дата расписания",
            "cabinet": "Кабинет",
            "doctor": "Врач",
            "start_time": "Время начала",
            "end_time": "Время окончания",
            "slot_type": "Тип слота",
            "description": "Описание",
        }


class PatientForm(StyleFormMixin, ModelForm):
    """Форма для создания/редактирования пациента"""

    class Meta:
        model = Patient
        fields = [
            "surname",
            "first_name",
            "last_name",
            "phone_number",
            "card_number",
            "date_of_birth",
            "registration_address",
            "residential_address",
        ]
        widgets = {
            "date_of_birth": forms.DateInput(attrs={"type": "date"}),
        }

    def clean(self):
        cleaned_data = super().clean()
        # Можно добавить простую проверку на дубликаты
        surname = cleaned_data.get("surname")
        first_name = cleaned_data.get("first_name")
        date_of_birth = cleaned_data.get("date_of_birth")

        if surname and first_name and date_of_birth:
            existing = Patient.objects.filter(
                surname__iexact=surname,
                first_name__iexact=first_name,
                date_of_birth=date_of_birth,
            ).exclude(pk=self.instance.pk if self.instance else None)

            if existing.exists():
                raise forms.ValidationError(
                    "Пациент с такими ФИО и датой рождения уже существует в базе"
                )
        return cleaned_data
