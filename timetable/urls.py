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
]
