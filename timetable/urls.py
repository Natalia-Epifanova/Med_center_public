from django.urls import path

from timetable.apps import TimetableConfig
from timetable.views import HomeView, ScheduleCreateView, ScheduleDayView

app_name = TimetableConfig.name
urlpatterns = [
    path("", HomeView.as_view(), name="home"),
    path("schedule/create/", ScheduleCreateView.as_view(), name="schedule_create"),
    path("schedule/day/", ScheduleDayView.as_view(), name="schedule_day"),
]
