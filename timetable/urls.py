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
    save_cabinet_day_comment,
)
from timetable.views_api import week_schedule_preview, delete_all_doctor_slots

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
    path(
        "api/week-schedule-preview/",
        week_schedule_preview,
        name="week_schedule_preview",
    ),
    path(
        "delete-all-doctor-slots/",
        delete_all_doctor_slots,
        name="delete_all_doctor_slots",
    ),
    path(
        "save-cabinet-comment/", save_cabinet_day_comment, name="save_cabinet_comment"
    ),
]
