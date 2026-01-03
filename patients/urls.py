from django.urls import path

from . import views
from .views_api import check_patient_api, search_patients_api

app_name = "patients"

urlpatterns = [
    path("", views.PatientListView.as_view(), name="patient_list"),
    path("create/", views.PatientCreateView.as_view(), name="patient_create"),
    path("<int:pk>/", views.PatientDetailView.as_view(), name="patient_detail"),
    path("<int:pk>/update/", views.PatientUpdateView.as_view(), name="patient_update"),
    path("<int:pk>/delete/", views.PatientDeleteView.as_view(), name="patient_delete"),
    path(
        "<int:pk>/generate-doc/<str:doc_type>/",
        views.generate_document,
        name="generate_document",
    ),
    path(
        "api/check-patient/",
        check_patient_api,
        name="api_check_patient",
    ),
    path(
        "api/search-patients/",
        search_patients_api,
        name="api_search_patients",
    ),
]
