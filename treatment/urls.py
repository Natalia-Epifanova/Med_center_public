from django.urls import path
from treatment.apps import TreatmentConfig
from treatment.views import (
    DoctorTreatmentCreateView,
    DoctorTreatmentDetailView,
    DoctorTreatmentUpdateView,
    DoctorTreatmentDeleteView,
    PatientTreatmentListView,
    mkb10_search,
)

app_name = TreatmentConfig.name

urlpatterns = [
    path(
        "create/<int:appointment_id>/",
        DoctorTreatmentCreateView.as_view(),
        name="treatment_create",
    ),
    path(
        "detail/<int:pk>/", DoctorTreatmentDetailView.as_view(), name="treatment_detail"
    ),
    path(
        "update/<int:pk>/", DoctorTreatmentUpdateView.as_view(), name="treatment_update"
    ),
    path(
        "delete/<int:pk>/", DoctorTreatmentDeleteView.as_view(), name="treatment_delete"
    ),
    path(
        "patient/<int:patient_id>/",
        PatientTreatmentListView.as_view(),
        name="patient_treatments",
    ),
    path("mkb10-search/", mkb10_search, name="mkb10_search"),
]
