# management/commands/export_patients.py
import pandas as pd
from django.core.management.base import BaseCommand
from patients.models import Patient
from datetime import datetime
import os


class Command(BaseCommand):
    help = "Экспорт всех пациентов в Excel файл"

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            type=str,
            default=None,
            help="Путь к выходному файлу (по умолчанию: patients_export_дата.xlsx)",
        )
        parser.add_argument(
            "--format",
            type=str,
            choices=["excel", "csv"],
            default="excel",
            help="Формат экспорта: excel или csv",
        )
        parser.add_argument(
            "--fields",
            type=str,
            default=None,
            help="Список полей для экспорта через запятую (по умолчанию: все поля)",
        )

    def handle(self, *args, **options):
        # Получаем всех пациентов
        patients = Patient.objects.all().order_by("surname", "first_name", "last_name")

        self.stdout.write(f"Найдено {patients.count()} пациентов")

        # Определяем поля для экспорта
        if options["fields"]:
            fields = [field.strip() for field in options["fields"].split(",")]
        else:
            # Все основные поля модели
            fields = [
                "id",
                "surname",
                "first_name",
                "last_name",
                "date_of_birth",
                "gender",
                "phone_number",
                "card_number",
                "card_number_IP",
                "card_number_OMS",
                "area",
                "locality",
                "city",
                "district",
                "street",
                "home",
                "building",
                "apartment",
                "passport_series",
                "passport_number",
                "polis_oms",
                "snils",
                "insurance_company",
            ]

        # Создаем список данных
        data = []
        for patient in patients:
            patient_data = {}
            for field in fields:
                value = getattr(patient, field)

                # Преобразуем значения для читаемости
                if field == "gender":
                    value = patient.get_gender_display() if value else ""
                elif field == "date_of_birth" and value:
                    value = value.strftime("%d.%m.%Y")

                patient_data[field] = value

            # Добавляем вычисляемые поля
            patient_data["full_name"] = patient.full_name
            patient_data["age"] = patient.age if patient.age else ""
            patient_data["full_address"] = patient.full_address

            data.append(patient_data)

        # Создаем DataFrame
        df = pd.DataFrame(data)

        # Определяем путь к файлу
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if options["output"]:
            output_path = options["output"]
        else:
            if options["format"] == "excel":
                output_path = f"patients_export_{timestamp}.xlsx"
            else:
                output_path = f"patients_export_{timestamp}.csv"

        # Сохраняем в нужном формате
        if options["format"] == "excel":
            # Создаем Excel writer с настройками
            with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Пациенты', index=False)

                # Настраиваем ширину колонок
                worksheet = writer.sheets['Пациенты']
                for i, col in enumerate(df.columns):
                    column_width = max(df[col].astype(str).map(len).max(), len(col)) + 2
                    worksheet.column_dimensions[chr(65 + i)].width = min(column_width, 50)

                self.stdout.write(self.style.SUCCESS(f"Данные сохранены в файл: {output_path}"))

        else:  # CSV
            df.to_csv(output_path, index=False, encoding='utf-8-sig')
            self.stdout.write(self.style.SUCCESS(f"Данные сохранены в файл: {output_path}"))

        # Выводим статистику
        self.stdout.write(f"Всего экспортировано: {len(df)} записей")
        self.stdout.write(f"Поля экспорта: {', '.join(df.columns.tolist())}")
        self.stdout.write(f"Путь к файлу: {os.path.abspath(output_path)}")