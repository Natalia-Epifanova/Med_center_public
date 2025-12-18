from django.urls import path

from appointments.apps import AppointmentsConfig
from appointments.views import (
    AppointmentCreateView,
    # AppointmentDeleteView,
    # AppointmentUpdateView,
    ProceduralAppointmentCreateView,
    ProceduralAppointmentUpdateView,
    update_appointment_status,
    AppointmentSimpleEditView,
    AppointmentDetailView,
    AppointmentDeleteOptionsView,
)
from appointments.views_api import (
    get_doctor_services_api,
    get_available_slots_for_doctor_api,
    validate_additional_appointment_api,
    get_available_doctors_api,
)

app_name = AppointmentsConfig.name

urlpatterns = [
    path(
        "create/<int:time_slot_id>/",
        AppointmentCreateView.as_view(),
        name="appointment_create",
    ),
    # path(
    #     "update/<int:pk>/",
    #     AppointmentUpdateView.as_view(),
    #     name="appointment_update",
    # ),
    path(
        "edit/<int:pk>/",
        AppointmentSimpleEditView.as_view(),
        name="appointment_edit_simple",
    ),
    path("<int:pk>/", AppointmentDetailView.as_view(), name="appointment_detail"),
    # path(
    #     "delete/<int:pk>/",
    #     AppointmentDeleteView.as_view(),
    #     name="appointment_delete",
    # ),
    path(
        "delete/<int:pk>/",
        AppointmentDeleteOptionsView.as_view(),
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
    path("api/doctor-services/", get_doctor_services_api, name="api_doctor_services"),
    path(
        "api/available-slots-for-doctor/",
        get_available_slots_for_doctor_api,
        name="api_available_slots_for_doctor",
    ),
    path(
        "api/validate-additional-appointment/",
        validate_additional_appointment_api,
        name="api_validate_additional_appointment",
    ),
    path(
        "api/available-doctors/",
        get_available_doctors_api,
        name="api_available_doctors",
    ),
]
