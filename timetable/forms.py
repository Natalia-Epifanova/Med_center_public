from datetime import timedelta

from django import forms
from django.forms import ModelForm
from django.utils import timezone

from .mixins import StyleFormMixin
from .models import Cabinet, DayComment, Doctor, TimeSlot, CabinetDayComment


class TimeSlotForm(StyleFormMixin, ModelForm):
    """Упрощенная форма для добавления временных слотов"""

    ADD_TYPE_CHOICES = [
        ("single", "Добавить один слот"),
        ("multiple", "Добавить несколько слотов с интервалом"),
    ]

    add_type = forms.ChoiceField(
        choices=ADD_TYPE_CHOICES,
        widget=forms.RadioSelect(attrs={"class": "form-check-input"}),
        initial="single",
        label="Тип добавления",
    )

    # Поля для одиночного добавления
    single_start_time = forms.TimeField(
        widget=forms.TimeInput(attrs={"type": "time"}),
        required=False,
        label="Время начала",
    )
    single_end_time = forms.TimeField(
        widget=forms.TimeInput(attrs={"type": "time"}),
        required=False,
        label="Время окончания",
    )
    single_slot_type = forms.ChoiceField(
        choices=TimeSlot.SLOT_TYPE_CHOICES,
        initial="working",
        required=False,
        label="Тип слота",
    )
    single_description = forms.CharField(
        required=False,
        max_length=200,
        label="Описание",
        widget=forms.TextInput(attrs={"placeholder": "Например: Обед"}),
    )

    # Поля для множественного добавления
    multiple_start_time = forms.TimeField(
        widget=forms.TimeInput(attrs={"type": "time"}),
        required=False,
        label="Время начала диапазона",
    )
    multiple_end_time = forms.TimeField(
        widget=forms.TimeInput(attrs={"type": "time"}),
        required=False,
        label="Время окончания диапазона",
    )
    interval = forms.IntegerField(
        min_value=5,
        max_value=120,
        initial=20,
        required=False,
        label="Интервал (минуты)",
    )

    class Meta:
        model = TimeSlot
        fields = ["date", "cabinet", "doctor"]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
        }
        labels = {
            "date": "Дата расписания",
            "cabinet": "Кабинет",
            "doctor": "Врач",
        }


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


class DayCommentForm(StyleFormMixin, ModelForm):
    """Форма для комментария дня"""

    class Meta:
        model = DayComment
        fields = ["comment"]
        widgets = {
            "comment": forms.Textarea(
                attrs={
                    "rows": 3,
                    "class": "form-control",
                    "placeholder": "Например: Роза с 8-14",
                }
            ),
        }
        labels = {
            "comment": "Комментарий для дня",
        }


class CabinetDayCommentForm(forms.ModelForm):
    comment = forms.CharField(
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "class": "form-control",
                "placeholder": "Введите комментарий для этого кабинета на выбранную дату...",
            }
        ),
        required=False,
        label="",
    )

    class Meta:
        model = CabinetDayComment
        fields = ["comment"]


class CopyScheduleForm(StyleFormMixin, forms.Form):
    """Форма для копирования расписания с одного дня на другой"""

    source_date = forms.DateField(
        required=True,
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
        label="Дата, с которой копировать расписание",
    )

    target_date = forms.DateField(
        required=True,
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
        label="Дата, на которую копировать расписание",
    )

    COPY_TYPE_CHOICES = [
        ("all", "Все слоты"),
        ("by_cabinet", "Только определенные кабинеты"),
        ("by_doctor", "Только определенных врачей"),
    ]

    copy_type = forms.ChoiceField(
        choices=COPY_TYPE_CHOICES,
        initial="all",
        widget=forms.RadioSelect(attrs={"class": "form-check-input"}),
        label="Что копировать?",
    )

    # Динамические поля для выбора кабинетов/врачей
    cabinets = forms.ModelMultipleChoiceField(
        queryset=Cabinet.objects.all().order_by("number"),
        required=False,
        widget=forms.SelectMultiple(attrs={"class": "form-select", "size": "5"}),
        label="Кабинеты для копирования",
    )

    doctors = forms.ModelMultipleChoiceField(
        queryset=Doctor.objects.all().order_by("surname"),
        required=False,
        widget=forms.SelectMultiple(attrs={"class": "form-select", "size": "5"}),
        label="Врачи для копирования",
    )

    OVERRIDE_CHOICES = [
        ("skip", "Пропускать существующие слоты"),
        ("override", "Перезаписать существующие слоты"),
        ("delete_and_create", "Удалить все слоты и создать новые"),
    ]

    conflict_resolution = forms.ChoiceField(
        choices=OVERRIDE_CHOICES,
        initial="skip",
        widget=forms.RadioSelect(attrs={"class": "form-check-input"}),
        label="Что делать с существующими слотами на целевой дате?",
    )

    def clean(self):
        cleaned_data = super().clean()
        source_date = cleaned_data.get("source_date")
        target_date = cleaned_data.get("target_date")

        if source_date and target_date:
            if source_date == target_date:
                raise forms.ValidationError("Даты источника и цели не могут совпадать")

            if target_date < source_date:
                if not self.request.user.is_staff:
                    raise forms.ValidationError(
                        "Копирование на прошедшую дату разрешено только администраторам"
                    )

        copy_type = cleaned_data.get("copy_type")
        if copy_type == "by_cabinet" and not cleaned_data.get("cabinets"):
            raise forms.ValidationError(
                "Для копирования по кабинетам необходимо выбрать хотя бы один кабинет"
            )

        if copy_type == "by_doctor" and not cleaned_data.get("doctors"):
            raise forms.ValidationError(
                "Для копирования по врачам необходимо выбрать хотя бы одного врача"
            )

        return cleaned_data

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)

        # Предзаполняем текущей датой
        today = timezone.now().date()
        self.fields["source_date"].initial = today
        self.fields["target_date"].initial = today + timedelta(days=7)


class CopyWeeklyScheduleForm(forms.Form):
    """Форма для копирования расписания по недельному шаблону с выбором недель"""

    # Неделя-источник
    source_week_start = forms.DateField(
        required=True,
        widget=forms.DateInput(
            attrs={"type": "date", "class": "form-control", "id": "source_week_start"}
        ),
        label="Начало недели, С которой копировать",
    )

    # Неделя-цель
    target_week_start = forms.DateField(
        required=True,
        widget=forms.DateInput(
            attrs={"type": "date", "class": "form-control", "id": "target_week_start"}
        ),
        label="Начало недели, На которую копировать",
    )

    # Дни для копирования
    WEEKDAY_CHOICES = [
        (0, "Понедельник"),
        (1, "Вторник"),
        (2, "Среда"),
        (3, "Четверг"),
        (4, "Пятница"),
        (5, "Суббота"),
        (6, "Воскресенье"),
    ]

    days_to_copy = forms.MultipleChoiceField(
        choices=WEEKDAY_CHOICES,
        required=True,
        widget=forms.CheckboxSelectMultiple(attrs={"class": "form-check-input"}),
        label="Дни недели для копирования",
    )

    # Опции фильтрации (опционально)
    copy_type = forms.ChoiceField(
        choices=[
            ("all", "Все слоты"),
            ("by_cabinet", "Только определенные кабинеты"),
            ("by_doctor", "Только определенных врачей"),
        ],
        initial="all",
        widget=forms.RadioSelect(attrs={"class": "form-check-input"}),
        label="Что копировать?",
        required=False,
    )

    cabinets = forms.ModelMultipleChoiceField(
        queryset=Cabinet.objects.all().order_by("number"),
        required=False,
        widget=forms.SelectMultiple(attrs={"class": "form-select", "size": "5"}),
        label="Кабинеты для копирования",
    )

    doctors = forms.ModelMultipleChoiceField(
        queryset=Doctor.objects.all().order_by("surname"),
        required=False,
        widget=forms.SelectMultiple(attrs={"class": "form-select", "size": "5"}),
        label="Врачи для копирования",
    )

    # Обработка конфликтов
    conflict_resolution = forms.ChoiceField(
        choices=[
            ("skip", "Пропускать существующие слоты"),
            ("override", "Перезаписать существующие слоты"),
        ],
        initial="skip",
        widget=forms.RadioSelect(attrs={"class": "form-check-input"}),
        label="Что делать с существующими слотами?",
        required=False,
    )

    def clean(self):
        cleaned_data = super().clean()
        source_week_start = cleaned_data.get("source_week_start")
        target_week_start = cleaned_data.get("target_week_start")

        if source_week_start and target_week_start:
            # Проверяем, что это понедельники (начало недели)
            if source_week_start.weekday() != 0:
                raise forms.ValidationError(
                    "Дата начала недели-источника должна быть понедельником"
                )

            if target_week_start.weekday() != 0:
                raise forms.ValidationError(
                    "Дата начала недели-цели должна быть понедельником"
                )

            # Предотвращаем копирование на ту же неделю
            if source_week_start == target_week_start:
                raise forms.ValidationError(
                    "Нельзя копировать расписание на ту же неделю"
                )

        # Проверяем, что выбраны дни
        days_to_copy = cleaned_data.get("days_to_copy")
        if not days_to_copy:
            raise forms.ValidationError("Выберите хотя бы один день для копирования")

        return cleaned_data

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Предзаполняем ближайшие понедельники
        today = timezone.now().date()

        # Ближайший прошедший понедельник (источник)
        last_monday = today - timedelta(days=today.weekday())

        # Ближайший будущий понедельник (цель)
        if today.weekday() == 0:
            next_monday = today + timedelta(days=7)
        else:
            days_until_monday = (7 - today.weekday()) % 7
            next_monday = today + timedelta(days=days_until_monday)

        self.fields["source_week_start"].initial = last_monday
        self.fields["target_week_start"].initial = next_monday
        self.fields["days_to_copy"].initial = [
            "0",
            "1",
            "2",
            "3",
            "4",
        ]  # Пн-Пт по умолчанию
