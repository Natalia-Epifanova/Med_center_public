from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", RedirectView.as_view(url="/timetable/")),
    path("timetable/", include("timetable.urls", namespace="timetable")),
    path("users/", include("users.urls", namespace="users")),
    path("patients/", include("patients.urls", namespace="patients")),
    path("appointments/", include("appointments.urls", namespace="appointments")),
]
