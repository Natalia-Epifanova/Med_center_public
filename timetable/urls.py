from django.urls import path

from timetable.apps import TimetableConfig
from timetable.views import (
    HomeView,
    ScheduleDayView,
    TimeSlotCreateView,
    TimeSlotDetailView,
    TimeSlotUpdateView,
    TimeSlotDeleteView,
    PatientListView,
    PatientCreateView,
    PatientDetailView,
    PatientUpdateView,
    PatientDeleteView,
    AppointmentUpdateView,
    AppointmentDeleteView,
    RescheduleRequestsView,
    AppointmentCreateView,
    ProceduralAppointmentCreateView,
)
from timetable.views_api import (
    check_patient_api,
    get_available_slots,
    check_procedural_availability,
)

app_name = TimetableConfig.name
urlpatterns = [
    path("", HomeView.as_view(), name="home"),
    path("schedule/create/", TimeSlotCreateView.as_view(), name="schedule_create"),
    path("schedule/day/", ScheduleDayView.as_view(), name="schedule_day"),
    path("timeslot/<int:pk>/", TimeSlotDetailView.as_view(), name="timeslot_detail"),
    path(
        "timeslot/<int:pk>/update/",
        TimeSlotUpdateView.as_view(),
        name="timeslot_update",
    ),
    path(
        "timeslot/<int:pk>/delete/",
        TimeSlotDeleteView.as_view(),
        name="timeslot_delete",
    ),
    path("patients/", PatientListView.as_view(), name="patient_list"),
    path("patients/create/", PatientCreateView.as_view(), name="patient_create"),
    path("patients/<int:pk>/", PatientDetailView.as_view(), name="patient_detail"),
    path(
        "patients/<int:pk>/update/", PatientUpdateView.as_view(), name="patient_update"
    ),
    path(
        "patients/<int:pk>/delete/", PatientDeleteView.as_view(), name="patient_delete"
    ),
    path(
        "appointment/create/<int:time_slot_id>/",
        AppointmentCreateView.as_view(),
        name="appointment_create",
    ),
    path(
        "appointment/<int:pk>/update/",
        AppointmentUpdateView.as_view(),
        name="appointment_update",
    ),
    path(
        "appointment/<int:pk>/delete/",
        AppointmentDeleteView.as_view(),
        name="appointment_delete",
    ),
    # Запросы на перезапись
    path(
        "reschedule-requests/",
        RescheduleRequestsView.as_view(),
        name="reschedule_requests",
    ),
    path(
        "api/check-patient/",
        check_patient_api,
        name="api_check_patient",
    ),
    path(
        "api/get-available-slots/",
        get_available_slots,
        name="api_get_available_slots",
    ),
    path(
        "api/check-procedural-availability/",
        check_procedural_availability,
        name="api_check_procedural_availability",
    ),
    path(
        "appointment/create-procedural/",
        ProceduralAppointmentCreateView.as_view(),
        name="appointment_create_procedural",
    ),
]
