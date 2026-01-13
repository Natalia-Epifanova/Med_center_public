# appointments/management/commands/check_price_history.py

from django.core.management.base import BaseCommand
from appointments.models import Appointment
from django.db.models import F, Q, FloatField
from django.db.models.functions import Cast, Abs
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Анализ записей с расхождениями в ценах"

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS("Анализ записей с расхождениями в ценах...")
        )

        # 1. Записи, где цена в записи отличается от текущей цены услуги
        discrepancies = (
            Appointment.objects.annotate(
                price_diff=Abs(
                    Cast(F("price_at_appointment"), FloatField())
                    - Cast(F("service__price"), FloatField())
                )
            )
            .filter(
                service__isnull=False,
                price_at_appointment__isnull=False,
                price_diff__gt=0.01,  # Расхождение больше 1 копейки
            )
            .select_related("service", "patient", "time_slot__doctor")
        )

        self.stdout.write(
            f"Найдено записей с расхождением цен: {discrepancies.count()}"
        )

        for app in discrepancies[:20]:  # Показываем первые 20
            self.stdout.write(
                f"ID: {app.id} | "
                f"Пациент: {app.patient.get_full_name()} | "
                f"Врач: {app.doctor.surname} | "
                f"Дата: {app.date} | "
                f'Услуга: "{app.service.name}" | '
                f"Цена услуги: {app.service.price} | "
                f"Цена в записи: {app.price_at_appointment} | "
                f"Разница: {abs(app.service.price - app.price_at_appointment)}"
            )

        if discrepancies.count() > 20:
            self.stdout.write(f"... и еще {discrepancies.count() - 20} записей")

        # 2. Записи с нулевой или пустой ценой
        zero_price = Appointment.objects.filter(
            Q(price_at_appointment__isnull=True) | Q(price_at_appointment=0)
        ).exclude(service=None)

        self.stdout.write(
            f"\nНайдено записей с нулевой/пустой ценой: {zero_price.count()}"
        )

        # 3. Записи с некорректной итоговой суммой
        appointments_with_tests = Appointment.objects.filter(
            selected_blood_tests__isnull=False
        ).distinct()

        problem_total = 0
        for app in appointments_with_tests:
            tests_price = app.get_tests_price
            service_price = app.price_at_appointment or (
                app.service.price if app.service else 0
            )
            correct_total = tests_price + service_price

            if (
                app.total_with_blood_tests
                and abs(app.total_with_blood_tests - correct_total) > 0.01
            ):
                problem_total += 1

        self.stdout.write(
            f"Найдено записей с некорректной итоговой суммой: {problem_total}"
        )

        # 4. Сводная статистика
        self.stdout.write("\n" + "=" * 50)
        self.stdout.write("СВОДНАЯ СТАТИСТИКА:")
        self.stdout.write(f"Всего записей в системе: {Appointment.objects.count()}")
        self.stdout.write(f"Записей с расхождением цен: {discrepancies.count()}")
        self.stdout.write(f"Записей с нулевой/пустой ценой: {zero_price.count()}")
        self.stdout.write(f"Записей с анализами: {appointments_with_tests.count()}")
        self.stdout.write(f"Записей с некорректной итоговой суммой: {problem_total}")

        self.stdout.write(self.style.SUCCESS("\nДля исправления проблем выполните:"))
        self.stdout.write("  python manage.py fix_price_discrepancies.py")
        self.stdout.write(
            "  python manage.py fix_price_discrepancies.py --dry-run  (для просмотра)"
        )
