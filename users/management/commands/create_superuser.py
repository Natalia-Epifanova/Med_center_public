from django.core.management import BaseCommand

from users.models import User


class Command(BaseCommand):
    """
    Команда для создания суперпользователя.
    Создает администратора системы с полными правами:
    - Email: admin@example.com
    - Пароль: 12345qwerty
    - Права суперпользователя и персонала
    Пример использования:
        python manage.py create_superuser
    """

    def handle(self, *args, **options):
        """Создает и сохраняет суперпользователя."""
        user = User.objects.create(email="admin@example.com")
        user.set_password("12345qwerty")
        user.is_active = True
        user.is_staff = True
        user.is_superuser = True
        user.save()
