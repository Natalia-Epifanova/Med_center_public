# appointments/management/commands/fix_price_discrepancies.py

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from appointments.models import Appointment
from timetable.models import MedicalService
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Исправляет расхождения в ценах между услугой и price_at_appointment для исторических записей"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Показать, что будет исправлено, но не применять изменения",
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Вывод подробной информации",
        )
        parser.add_argument(
            "--appointment-id",
            type=int,
            help="Исправить только конкретную запись по ID",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        verbose = options["verbose"]
        appointment_id = options.get("appointment_id")

        self.stdout.write(self.style.SUCCESS("Поиск записей с некорректными ценами..."))

        # 1. Находим все записи, где услуга есть, но price_at_appointment некорректен
        if appointment_id:
            appointments = Appointment.objects.filter(id=appointment_id)
            self.stdout.write(f"Проверка записи ID: {appointment_id}")
        else:
            appointments = Appointment.objects.exclude(service=None).all()

        problem_count = 0
        fixed_count = 0

        with transaction.atomic():
            # Создаем savepoint для возможного отката
            if dry_run:
                transaction.set_rollback(True)

            for appointment in appointments:
                try:
                    # Получаем текущую услугу
                    service = appointment.service

                    if not service:
                        if verbose:
                            self.stdout.write(
                                f"Запись {appointment.id}: нет услуги, пропускаем"
                            )
                        continue

                    # Рассчитываем ожидаемую цену
                    expected_price = service.price

                    # Получаем текущую сохраненную цену
                    current_price = appointment.price_at_appointment

                    # Проверяем расхождение более чем на 1 копейку
                    price_diff = abs((current_price or 0) - expected_price)

                    if price_diff > 0.01:  # Расхождение больше 1 копейки
                        problem_count += 1

                        if verbose or dry_run:
                            self.stdout.write(
                                f"Проблемная запись ID {appointment.id}: "
                                f'Услуга "{service.name}" ({service.price}), '
                                f"Текущая цена: {current_price}, "
                                f"Ожидаемая: {expected_price}"
                            )

                        if not dry_run:
                            # Исправляем цену
                            appointment.price_at_appointment = expected_price

                            # Пересчитываем итоговую сумму с анализами
                            tests_price = appointment.get_tests_price
                            service_price = expected_price
                            appointment.total_with_blood_tests = (
                                tests_price + service_price
                            )

                            appointment.save()
                            fixed_count += 1

                            if verbose:
                                self.stdout.write(
                                    f"  -> Исправлено: price_at_appointment = {expected_price}"
                                )

                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(
                            f"Ошибка при обработке записи {appointment.id}: {str(e)}"
                        )
                    )

        # 2. Проверяем записи с нулевой ценой, но с услугой
        self.stdout.write(
            "\n" + self.style.SUCCESS("Проверка записей с нулевой ценой...")
        )

        zero_price_appointments = Appointment.objects.filter(
            service__isnull=False, price_at_appointment__isnull=True
        )

        for appointment in zero_price_appointments:
            if appointment.service:
                problem_count += 1

                if verbose or dry_run:
                    self.stdout.write(
                        f"Запись ID {appointment.id}: "
                        f'Услуга "{appointment.service.name}" имеет цену {appointment.service.price}, '
                        f"но price_at_appointment = NULL"
                    )

                if not dry_run:
                    appointment.price_at_appointment = appointment.service.price
                    appointment.save()
                    fixed_count += 1

        # 3. Проверяем записи, где total_with_blood_tests не соответствует сумме
        self.stdout.write("\n" + self.style.SUCCESS("Проверка итоговых сумм..."))

        all_appointments = Appointment.objects.all()

        for appointment in all_appointments:
            try:
                # Рассчитываем правильную итоговую сумму
                tests_price = appointment.get_tests_price
                service_price = appointment.price_at_appointment or (
                    appointment.service.price if appointment.service else 0
                )
                correct_total = tests_price + service_price

                # Получаем текущую итоговую сумму
                current_total = appointment.total_with_blood_tests or 0

                # Проверяем расхождение
                if abs(current_total - correct_total) > 0.01:
                    problem_count += 1

                    if verbose or dry_run:
                        self.stdout.write(
                            f"Некорректная сумма ID {appointment.id}: "
                            f"Текущая total: {current_total}, "
                            f"Правильная: {correct_total} "
                            f"(услуга: {service_price}, анализы: {tests_price})"
                        )

                    if not dry_run:
                        appointment.total_with_blood_tests = correct_total
                        appointment.save()
                        fixed_count += 1

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f"Ошибка при проверке суммы для записи {appointment.id}: {str(e)}"
                    )
                )

        # Выводим итоги
        self.stdout.write("\n" + "=" * 50)

        if dry_run:
            self.stdout.write(
                self.style.WARNING(f"РЕЖИМ ПРОСМОТРА: Найдено проблем: {problem_count}")
            )
            self.stdout.write(
                self.style.WARNING(
                    "Изменения не применены. Используйте без --dry-run для исправления."
                )
            )
        else:
            if fixed_count > 0:
                self.stdout.write(
                    self.style.SUCCESS(f"Успешно исправлено записей: {fixed_count}")
                )
            else:
                self.stdout.write(self.style.SUCCESS("Проблемные записи не найдены"))

        self.stdout.write(self.style.SUCCESS("Проверка завершена!"))
