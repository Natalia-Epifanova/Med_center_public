from django.contrib.auth.views import LogoutView
from django.urls import path

from users.apps import UsersConfig
from users.views import CustomLoginView, UserCreateView, UserDetailView, UserUpdateView

app_name = UsersConfig.name

urlpatterns = [
    path("login/", CustomLoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("register/", UserCreateView.as_view(), name="register"),
    path("profile/<int:pk>/", UserDetailView.as_view(), name="profile_detail"),
    path("profile/<int:pk>/update/", UserUpdateView.as_view(), name="edit_profile"),
]
