from django.urls import path

from . import views
from .apps import PatientsConfig
from .views import (
    WaitlistPatientListView,
    WaitlistPatientUpdateView,
    WaitlistPatientCreateView,
    WaitlistPatientDeleteView,
    add_patient_to_blacklist,
    remove_patient_from_blacklist,
)
from .views_api import (
    check_patient_api,
    check_patient_blacklist_api,
    search_patients_api,
    generate_new_card_number,
    get_max_card_number,
)

app_name = PatientsConfig.name

urlpatterns = [
    path("", views.PatientListView.as_view(), name="patient_list"),
    path("create/", views.PatientCreateView.as_view(), name="patient_create"),
    path("<int:pk>/", views.PatientDetailView.as_view(), name="patient_detail"),
    path("<int:pk>/update/", views.PatientUpdateView.as_view(), name="patient_update"),
    path("<int:pk>/delete/", views.PatientDeleteView.as_view(), name="patient_delete"),
    path(
        "<int:pk>/blacklist/add/",
        add_patient_to_blacklist,
        name="patient_blacklist_add",
    ),
    path(
        "<int:pk>/blacklist/remove/",
        remove_patient_from_blacklist,
        name="patient_blacklist_remove",
    ),
    path(
        "<int:pk>/generate-doc/<str:doc_type>/",
        views.generate_document,
        name="generate_document",
    ),
    # Маршруты для резервных списков
    path("reserve/", views.ReserveMainView.as_view(), name="reserve_main"),
    path(
        "reserve/create/",
        views.ReservePatientCreateView.as_view(),
        name="reserve_patient_create",
    ),
    path(
        "reserve/<int:pk>/update/",
        views.ReservePatientUpdateView.as_view(),
        name="reserve_patient_update",
    ),
    path(
        "reserve/<int:pk>/delete/",
        views.ReservePatientDeleteView.as_view(),
        name="reserve_patient_delete",
    ),
    # API маршруты
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
    path(
        "api/check-blacklist/",
        check_patient_blacklist_api,
        name="api_check_blacklist",
    ),
    path("get-max-card-number/", get_max_card_number, name="get_max_card_number"),
    path(
        "generate-new-card-number/<str:card_type>/",
        generate_new_card_number,
        name="generate_new_card_number",
    ),
    # Лист ожидания
    path("waitlist/", WaitlistPatientListView.as_view(), name="waitlist_list"),
    path(
        "waitlist/create/", WaitlistPatientCreateView.as_view(), name="waitlist_create"
    ),
    path(
        "waitlist/<int:pk>/update/",
        WaitlistPatientUpdateView.as_view(),
        name="waitlist_update",
    ),
    path(
        "waitlist/<int:pk>/delete/",
        WaitlistPatientDeleteView.as_view(),
        name="waitlist_delete",
    ),
]
