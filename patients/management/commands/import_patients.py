from django.core.management.base import BaseCommand
import sys
import os

from patients.import_script import backup_patients, import_patients_from_excel

# Добавляем путь к проекту
sys.path.append("C:/Users/user/PycharmProjects/Revmamed")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "your_project.settings")

import django

django.setup()


class Command(BaseCommand):
    help = "Импорт пациентов из Excel файла"

    def add_arguments(self, parser):
        parser.add_argument("file_path", type=str, help="Путь к Excel файлу")
        parser.add_argument(
            "--no-backup",
            action="store_true",
            help="Не создавать резервную копию перед импортом",
        )
        parser.add_argument(
            "--test",
            action="store_true",
            help="Тестовый режим (обработать только первые 10 строк)",
        )

    def handle(self, *args, **options):
        file_path = options["file_path"]

        if not os.path.exists(file_path):
            self.stdout.write(self.style.ERROR(f"Файл не найден: {file_path}"))
            return

        self.stdout.write(f"Начинаем импорт из файла: {file_path}")

        if not options["no_backup"]:
            self.stdout.write("Создание резервной копии...")
            backup_patients()

        self.stdout.write("Запуск импорта...")
        stats = import_patients_from_excel(file_path)

        if stats:
            self.stdout.write(self.style.SUCCESS("Импорт завершен успешно!"))
            self.stdout.write(f'Создано: {stats["created"]}')
            self.stdout.write(f'Обновлено: {stats["updated"]}')
            self.stdout.write(f'Пропущено: {stats["skipped"]}')
            self.stdout.write(f'Ошибок: {stats["errors"]}')
