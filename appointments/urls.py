from django.urls import path

from appointments.apps import AppointmentsConfig
from appointments.views import (
    AppointmentCreateView,
    AppointmentUpdateView,
    AppointmentDeleteView,
    ProceduralAppointmentCreateView,
    ProceduralAppointmentUpdateView,
    update_appointment_status,
)

app_name = AppointmentsConfig.name

urlpatterns = [
    path(
        "create/<int:time_slot_id>/",
        AppointmentCreateView.as_view(),
        name="appointment_create",
    ),
    path(
        "update/<int:pk>/",
        AppointmentUpdateView.as_view(),
        name="appointment_update",
    ),
    path(
        "delete/<int:pk>/",
        AppointmentDeleteView.as_view(),
        name="appointment_delete",
    ),
    path(
        "create-procedural/",
        ProceduralAppointmentCreateView.as_view(),
        name="appointment_create_procedural",
    ),
    path(
        "update-procedural/<int:pk>/",
        ProceduralAppointmentUpdateView.as_view(),
        name="appointment_update_procedural",
    ),
    path(
        "<int:pk>/update-status/",
        update_appointment_status,
        name="appointment_update_status",
    ),
]
