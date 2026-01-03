from django.contrib.auth.views import LogoutView
from django.urls import path

from users.apps import UsersConfig
from users.views import (CustomLoginView, UserCreateView, UserDetailView,
                         UserPasswordChangeView, UserUpdateView)

app_name = UsersConfig.name

urlpatterns = [
    path("login/", CustomLoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(next_page="timetable:home"), name="logout"),
    path("profile/", UserDetailView.as_view(), name="profile"),
    path("profile/edit/", UserUpdateView.as_view(), name="edit_profile"),
    path(
        "profile/change-password/",
        UserPasswordChangeView.as_view(),
        name="change_password",
    ),
]
