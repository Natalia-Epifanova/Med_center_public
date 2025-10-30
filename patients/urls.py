from django.urls import path
from . import views

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
]
