from django.core.management import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    """
    Команда для создания суперпользователя.
    Создает администратора системы с полными правами:
    - Логин: admin
    - Email: admin@example.com
    - Пароль: 12345qwerty
    Пример использования:
        python manage.py create_superuser
    """

    help = "Создает суперпользователя"

    def handle(self, *args, **options):
        """Создает и сохраняет суперпользователя."""

        username = "admin"
        email = "admin@example.com"
        password = "12345qwerty"

        # Проверяем, не существует ли уже такой пользователь
        if User.objects.filter(username=username).exists():
            self.stdout.write(
                self.style.WARNING(f"Пользователь '{username}' уже существует")
            )
            return

        # Создаем суперпользователя
        try:
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
            )
            user.is_active = True
            user.is_staff = True
            user.is_superuser = True
            user.save()

            self.stdout.write(
                self.style.SUCCESS(f"✅ Суперпользователь создан успешно!")
            )
            self.stdout.write(f"   Логин: {username}")
            self.stdout.write(f"   Email: {email}")
            self.stdout.write(f"   Пароль: {password}")

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"❌ Ошибка при создании суперпользователя: {e}")
            )
