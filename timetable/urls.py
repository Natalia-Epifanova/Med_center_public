from django.urls import path

from timetable.apps import TimetableConfig
from timetable.views import HomeView

app_name = TimetableConfig.name
urlpatterns = [
    path("", HomeView.as_view(), name="home"),
]
