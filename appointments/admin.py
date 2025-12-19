from django.contrib import admin

from .models import Appointment, AppointmentBloodTest, AppointmentChain


@admin.register(AppointmentChain)
class AppointmentChainAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "main_appointment_link",
        "related_appointment_link",
        "chain_type",
        "order",
        "created_at",
    ]
    list_filter = ["chain_type", "created_at"]
    search_fields = [
        "main_appointment__patient__surname",
        "main_appointment__patient__first_name",
        "related_appointment__patient__surname",
        "related_appointment__patient__first_name",
    ]
    raw_id_fields = ["main_appointment", "related_appointment"]
    readonly_fields = ["created_at"]

    def main_appointment_link(self, obj):
        return f"Запись #{obj.main_appointment.id} ({obj.main_appointment.patient})"

    main_appointment_link.short_description = "Основная запись"

    def related_appointment_link(self, obj):
        return (
            f"Запись #{obj.related_appointment.id} ({obj.related_appointment.patient})"
        )

    related_appointment_link.short_description = "Связанная запись"

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related(
                "main_appointment",
                "main_appointment__patient",
                "main_appointment__time_slot",
                "main_appointment__time_slot__doctor",
                "related_appointment",
                "related_appointment__patient",
                "related_appointment__time_slot",
                "related_appointment__time_slot__doctor",
            )
        )


# Обновляем существующий AppointmentAdmin
@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "patient_info",
        "doctor_info",
        "date_display",
        "time_display",
        "service_name",
        "status",
        "chain_type_display",
        "is_chain_main",
    ]
    list_filter = [
        "status",
        "chain_type",
        "is_chain_main",
        "time_slot__date",
        "insurance_type",
    ]
    search_fields = [
        "patient__surname",
        "patient__first_name",
        "patient__phone_number",
        "time_slot__doctor__surname",
        "service__name",
    ]
    raw_id_fields = ["patient", "time_slot", "service", "previous_appointment"]
    readonly_fields = [
        "price_at_appointment",
        "total_with_blood_tests",
        "date",
        "start_time",
        "end_time",
        "doctor",
        "cabinet",
    ]

    def patient_info(self, obj):
        return f"{obj.patient.surname} {obj.patient.first_name}"

    patient_info.short_description = "Пациент"

    def doctor_info(self, obj):
        return obj.doctor.surname if obj.doctor else "-"

    doctor_info.short_description = "Врач"

    def date_display(self, obj):
        return obj.date

    date_display.short_description = "Дата"
    date_display.admin_order_field = "time_slot__date"

    def time_display(self, obj):
        return f"{obj.start_time}-{obj.end_time}"

    time_display.short_description = "Время"

    def service_name(self, obj):
        return obj.service.name if obj.service else "-"

    service_name.short_description = "Услуга"

    def chain_type_display(self, obj):
        return obj.get_chain_type_display()

    chain_type_display.short_description = "Тип цепочки"

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related(
                "patient",
                "time_slot",
                "time_slot__doctor",
                "time_slot__cabinet",
                "service",
            )
        )

    # Добавляем inline для связанных записей
    class AppointmentChainInline(admin.TabularInline):
        model = AppointmentChain
        fk_name = "main_appointment"
        extra = 0
        max_num = 5
        readonly_fields = ["created_at"]
        raw_id_fields = ["related_appointment"]
        fields = ["related_appointment", "chain_type", "order", "created_at"]

    inlines = [AppointmentChainInline]

    # Поля для отображения в форме редактирования
    fieldsets = (
        (
            "Основная информация",
            {"fields": ("patient", "time_slot", "service", "status", "insurance_type")},
        ),
        (
            "Цепочка записей",
            {
                "fields": (
                    "chain_type",
                    "is_chain_main",
                    "previous_appointment",
                    "is_consecutive",
                    "occupies_two_slots",
                )
            },
        ),
        (
            "Дополнительно",
            {
                "fields": (
                    "needs_reschedule",
                    "comment",
                    "price_at_appointment",
                    "total_with_blood_tests",
                )
            },
        ),
    )
