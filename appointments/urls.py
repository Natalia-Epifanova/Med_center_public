from django.urls import path

from appointments.apps import AppointmentsConfig
from appointments.views import (
    AppointmentCreateView,
    AppointmentDeleteOptionsView,
    AppointmentDetailView,
    AppointmentSimpleEditView,
    ProceduralAppointmentCreateView,
    ProceduralAppointmentUpdateView,
    update_appointment_status,
)
from appointments.views_api import (
    api_get_next_slot,
    check_procedural_availability,
    get_available_doctors_api,
    get_blood_tests,
    get_doctor_services_api,
    validate_additional_appointment_api,
    get_available_slots_for_doctor_api,
)

app_name = AppointmentsConfig.name

urlpatterns = [
    path(
        "create/<int:time_slot_id>/",
        AppointmentCreateView.as_view(),
        name="appointment_create",
    ),
    path(
        "edit/<int:pk>/",
        AppointmentSimpleEditView.as_view(),
        name="appointment_edit_simple",
    ),
    path("<int:pk>/", AppointmentDetailView.as_view(), name="appointment_detail"),
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
    path(
        "api/check-procedural-availability/",
        check_procedural_availability,
        name="api_check_procedural_availability",
    ),
    path("api/blood-tests/", get_blood_tests, name="api_blood_tests"),
    path("api/get-next-slot/", api_get_next_slot, name="api_get_next_slot"),
]
