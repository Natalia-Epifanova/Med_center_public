from django.urls import path

from appointments.views import update_appointment_status
from timetable.apps import TimetableConfig
from timetable.views import (
    CopyScheduleView,
    CopyWeeklyScheduleView,
    DoctorReportView,
    EmergencySlotCreateView,
    HomeView,
    RescheduleRequestsView,
    ScheduleDayView,
    TimeSlotCreateView,
    TimeSlotDeleteView,
    TimeSlotDetailView,
    TimeSlotUpdateView,
    save_day_comment,
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
    # Запросы на перезапись
    path(
        "reschedule-requests/",
        RescheduleRequestsView.as_view(),
        name="reschedule_requests",
    ),
    path("day-comment/save/", save_day_comment, name="save_day_comment"),
    path("doctor-report/<str:date>/", DoctorReportView.as_view(), name="doctor_report"),
    path("copy-schedule/", CopyScheduleView.as_view(), name="copy_schedule"),
    path(
        "copy-weekly-schedule/",
        CopyWeeklyScheduleView.as_view(),
        name="copy_weekly_schedule",
    ),
]
