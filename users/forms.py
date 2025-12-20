from django import forms
from django.contrib.auth.forms import (PasswordChangeForm, UserChangeForm,
                                       UserCreationForm)
from django.forms import Form, ModelForm

from users.models import User


class UserRegisterForm(UserCreationForm):
    """Форма регистрации пользователя"""

    class Meta:
        model = User
        fields = ("username", "email", "phone", "password1", "password2")
        labels = {
            "username": "Логин",
            "email": "Email (необязательно)",
            "phone": "Телефон",
        }
        help_texts = {
            "username": "Обязательное поле. 150 символов или меньше. Только буквы, цифры и @/./+/-/_.",
        }


class UserProfileForm(ModelForm):
    """Форма редактирования профиля (без пароля)"""

    class Meta:
        model = User
        fields = ("username", "email", "phone", "first_name", "last_name")
        labels = {
            "username": "Логин",
            "email": "Email",
            "phone": "Телефон",
            "first_name": "Имя",
            "last_name": "Фамилия",
        }


class CustomPasswordChangeForm(PasswordChangeForm):
    """Кастомная форма смены пароля"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Кастомизируем labels если нужно
        self.fields["old_password"].label = "Текущий пароль"
        self.fields["new_password1"].label = "Новый пароль"
        self.fields["new_password2"].label = "Подтверждение нового пароля"
