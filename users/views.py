from django.contrib.auth.views import LoginView
from django.urls import reverse_lazy
from django.views.generic import CreateView, DetailView, UpdateView

from users.forms import UserProfileForm, UserRegisterForm
from users.models import User


class CustomLoginView(LoginView):
    template_name = "users/login.html"


class UserCreateView(CreateView):

    model = User
    form_class = UserRegisterForm
    success_url = reverse_lazy("users:login")


class UserUpdateView(UpdateView):

    model = User
    form_class = UserProfileForm
    success_url = reverse_lazy("timetable:home")


class UserDetailView(DetailView):
    model = User
    template_name = "users/profile_detail.html"
