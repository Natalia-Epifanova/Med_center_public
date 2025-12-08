from django.contrib.auth.views import LoginView, PasswordChangeView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import CreateView, DetailView, UpdateView

from users.forms import UserRegisterForm, UserProfileForm, CustomPasswordChangeForm
from users.models import User


class CustomLoginView(LoginView):
    template_name = "users/login.html"

    def get_success_url(self):
        # Проверяем, если пользователь в группе Admin или Medical Center Administrator
        user = self.request.user
        if user.groups.filter(
            name__in=["Admin", "Medical Center Administrator"]
        ).exists():
            return reverse_lazy("timetable:schedule_day")
        return reverse_lazy("timetable:home")


class UserCreateView(CreateView):
    model = User
    form_class = UserRegisterForm
    template_name = "users/register.html"
    success_url = reverse_lazy("users:login")


class UserUpdateView(LoginRequiredMixin, UpdateView):
    model = User
    form_class = UserProfileForm
    template_name = "users/edit_profile.html"
    success_url = reverse_lazy("users:profile")

    def get_object(self):
        return self.request.user


class UserDetailView(LoginRequiredMixin, DetailView):
    model = User
    template_name = "users/profile_detail.html"

    def get_object(self):
        return self.request.user


class UserPasswordChangeView(LoginRequiredMixin, PasswordChangeView):
    """Изменение пароля пользователя"""

    form_class = CustomPasswordChangeForm
    template_name = "users/change_password.html"
    success_url = reverse_lazy("users:profile")
