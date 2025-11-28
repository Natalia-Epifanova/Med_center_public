from django.urls import path

from timetable.apps import TimetableConfig
from timetable.views import (
    HomeView,
    ScheduleDayView,
    TimeSlotCreateView,
    TimeSlotDetailView,
    TimeSlotUpdateView,
    TimeSlotDeleteView,
    AppointmentUpdateView,
    AppointmentDeleteView,
    RescheduleRequestsView,
    AppointmentCreateView,
    ProceduralAppointmentCreateView,
    save_day_comment,
    update_appointment_status,
    EmergencySlotCreateView,
    DoctorReportView,
)
from patients.views import (
    PatientListView,
    PatientCreateView,
    PatientUpdateView,
    PatientDetailView,
    PatientDeleteView,
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
    path(
        "emergency-slot/create/",
        EmergencySlotCreateView.as_view(),
        name="emergency_slot_create",
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
    path("day-comment/save/", save_day_comment, name="save_day_comment"),
    path(
        "appointment/<int:pk>/update-status/",
        update_appointment_status,
        name="update_appointment_status",
    ),
    path("doctor-report/<str:date>/", DoctorReportView.as_view(), name="doctor_report"),
]
