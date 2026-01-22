import os
import sys
import pandas as pd
from django.core.management.base import BaseCommand
from django.db import transaction
from django.conf import settings
from treatment.models import MKB10Diagnosis


class Command(BaseCommand):
    help = "Импорт кодов МКБ-10 из Excel файла"

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            type=str,
            help="Путь к Excel файлу с кодами МКБ-10",
            default="mkb10_codes.xlsx",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Очистить таблицу перед импортом",
            default=False,
        )
        parser.add_argument(
            "--sheet",
            type=str,
            help="Имя листа в Excel файле",
            default=0,  # можно использовать 0 для первого листа или имя листа
        )
        parser.add_argument(
            "--skip-first", type=int, help="Пропустить первые N строк", default=0
        )

    def handle(self, *args, **options):
        file_path = options["file"]
        sheet_name = options["sheet"]
        skip_rows = options["skip_first"]
        clear_table = options["clear"]

        # Проверка существования файла
        if not os.path.exists(file_path):
            self.stdout.write(self.style.ERROR(f"Файл не найден: {file_path}"))
            self.stdout.write("Создайте Excel файл со следующей структурой:")
            self.stdout.write("| Код | Название | Глава | Блок | Активность |")
            self.stdout.write("|-----|----------|-------|------|------------|")
            self.stdout.write(
                "| M00.0 | Стафилококковый артрит... | VIII | M00-M25 | Да |"
            )
            return

        try:
            # Чтение Excel файла
            self.stdout.write(f"Чтение файла: {file_path}")

            # Определение структуры файла
            df = pd.read_excel(
                file_path,
                sheet_name=sheet_name,
                skiprows=skip_rows,
                dtype=str,  # читаем все как строки
            )

            # Определение столбцов (может быть несколько форматов)
            column_mapping = {}

            # Поиск нужных столбцов по возможным названиям
            possible_columns = {
                "code": ["Код", "Код МКБ-10", "code", "Code"],
                "name": ["Название", "Название диагноза", "name", "Name", "Диагноз"],
                "chapter": ["Глава", "chapter", "Chapter"],
                "block": ["Блок", "block", "Block"],
                "is_active": ["Активный", "Активность", "is_active", "Active"],
            }

            for field, possible_names in possible_columns.items():
                for name in possible_names:
                    if name in df.columns:
                        column_mapping[field] = name
                        break

            self.stdout.write(f"Найдены колонки: {column_mapping}")

            if "code" not in column_mapping or "name" not in column_mapping:
                self.stdout.write("Доступные колонки в файле:")
                for col in df.columns:
                    self.stdout.write(f"  - {col}")
                raise ValueError(
                    'Не найдены обязательные колонки "Код" и "Название". '
                    "Проверьте заголовки в Excel файле."
                )

            # Очистка таблицы при необходимости
            if clear_table:
                self.stdout.write("Очистка существующих записей...")
                MKB10Diagnosis.objects.all().delete()

            # Импорт данных
            imported = 0
            updated = 0
            errors = []

            with transaction.atomic():
                for index, row in df.iterrows():
                    try:
                        code = str(row[column_mapping["code"]]).strip()
                        name = str(row[column_mapping["name"]]).strip()

                        # Проверка обязательных полей
                        if (
                            not code
                            or not name
                            or code.lower() == "nan"
                            or name.lower() == "nan"
                        ):
                            continue

                        # Получение дополнительных полей
                        chapter = (
                            row.get(column_mapping.get("chapter", ""), "").strip()
                            if column_mapping.get("chapter")
                            else ""
                        )
                        block = (
                            row.get(column_mapping.get("block", ""), "").strip()
                            if column_mapping.get("block")
                            else ""
                        )

                        # Обработка активности
                        if column_mapping.get("is_active"):
                            is_active_str = (
                                str(row[column_mapping["is_active"]]).strip().lower()
                            )
                            is_active = is_active_str in ["да", "yes", "true", "1", "+"]
                        else:
                            is_active = True

                        # Обновление или создание записи
                        obj, created = MKB10Diagnosis.objects.update_or_create(
                            code=code,
                            defaults={
                                "name": name,
                                "chapter": chapter,
                                "block": block,
                                "is_active": is_active,
                            },
                        )

                        if created:
                            imported += 1
                        else:
                            updated += 1

                    except Exception as e:
                        errors.append(f"Строка {index + 2}: {str(e)}")
                        self.stdout.write(
                            self.style.WARNING(f"Ошибка в строке {index + 2}: {str(e)}")
                        )

            # Вывод результатов
            self.stdout.write(
                self.style.SUCCESS(
                    f"Импорт завершен!\n"
                    f"Добавлено: {imported} записей\n"
                    f"Обновлено: {updated} записей\n"
                    f"Ошибок: {len(errors)}"
                )
            )

            if errors:
                self.stdout.write(self.style.ERROR("Список ошибок:"))
                for error in errors[:10]:  # показываем первые 10 ошибок
                    self.stdout.write(f"  - {error}")
                if len(errors) > 10:
                    self.stdout.write(f"  ... и еще {len(errors) - 10} ошибок")

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Ошибка импорта: {str(e)}"))
            import traceback

            traceback.print_exc()
