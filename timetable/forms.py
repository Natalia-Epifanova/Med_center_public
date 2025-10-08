from django import forms

from .models import Cabinet, Doctor, TimeSlot


class TimeSlotForm(forms.Form):
    """Форма для добавления одного слота или нескольких слотов с интервалом"""

    date = forms.DateField(
        label="Дата расписания",
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )
    cabinet = forms.ModelChoiceField(
        label="Кабинет",
        queryset=Cabinet.objects.all(),
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    doctor = forms.ModelChoiceField(
        label="Врач",
        queryset=Doctor.objects.all(),
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    # Выбор типа добавления
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

    # Поля для одного слота
    single_start_time = forms.TimeField(
        label="Время начала",
        widget=forms.TimeInput(attrs={"type": "time", "class": "form-control"}),
        required=False,
    )
    single_end_time = forms.TimeField(
        label="Время окончания",
        widget=forms.TimeInput(attrs={"type": "time", "class": "form-control"}),
        required=False,
    )
    single_slot_type = forms.ChoiceField(
        label="Тип слота",
        choices=TimeSlot.SLOT_TYPE_CHOICES,
        initial="working",
        widget=forms.Select(attrs={"class": "form-control"}),
        required=False,
    )
    single_description = forms.CharField(
        label="Описание",
        max_length=100,
        required=False,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Например: Обед"}
        ),
    )

    # Поля для нескольких слотов
    multiple_start_time = forms.TimeField(
        label="Время начала",
        widget=forms.TimeInput(attrs={"type": "time", "class": "form-control"}),
        required=False,
    )
    multiple_end_time = forms.TimeField(
        label="Время окончания",
        widget=forms.TimeInput(attrs={"type": "time", "class": "form-control"}),
        required=False,
    )
    interval = forms.IntegerField(
        label="Интервал (минуты)",
        min_value=5,
        max_value=120,
        initial=20,
        widget=forms.NumberInput(attrs={"class": "form-control"}),
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
