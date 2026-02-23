from django.core.management.base import BaseCommand
from patients.models import Patient
from appointments.models import Appointment
import csv


class Command(BaseCommand):
    help = "Экспорт всех посещений пациентов (одна строка = одно посещение)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            type=str,
            default="all_visits.csv",
            help="Имя выходного файла",
        )
        parser.add_argument(
            "--start-date",
            type=str,
            help="Начальная дата (формат: YYYY-MM-DD)",
        )
        parser.add_argument(
            "--end-date",
            type=str,
            help="Конечная дата (формат: YYYY-MM-DD)",
        )

    def handle(self, *args, **options):
        output_file = options["output"]
        start_date = options.get("start_date")
        end_date = options.get("end_date")

        self.stdout.write(f"Начинаю экспорт посещений в {output_file}...")

        # Базовый запрос
        appointments = (
            Appointment.objects.filter(patient__isnull=False)  # Только с пациентами
            .select_related("patient", "time_slot__doctor", "service")
            .order_by("-time_slot__date", "-time_slot__start_time")
        )

        # Фильтр по датам
        if start_date:
            appointments = appointments.filter(time_slot__date__gte=start_date)
        if end_date:
            appointments = appointments.filter(time_slot__date__lte=end_date)

        total = appointments.count()

        if total == 0:
            self.stdout.write(self.style.WARNING("Нет посещений для экспорта"))
            return

        self.stdout.write(f"Найдено посещений: {total}")

        with open(output_file, "w", encoding="utf-8-sig", newline="") as csvfile:
            writer = csv.writer(csvfile)

            # Заголовки
            writer.writerow(
                [
                    "Фамилия",
                    "Имя",
                    "Отчество",
                    "Дата рождения",
                    "Дата посещения",
                    "Время посещения",
                    "Врач",
                    "Услуга",
                ]
            )

            processed = 0
            for apt in appointments.iterator(chunk_size=500):
                patient = apt.patient

                writer.writerow(
                    [
                        patient.surname,
                        patient.first_name,
                        patient.last_name or "",
                        (
                            patient.date_of_birth.strftime("%d.%m.%Y")
                            if patient.date_of_birth
                            else ""
                        ),
                        (
                            apt.time_slot.date.strftime("%d.%m.%Y")
                            if apt.time_slot
                            else "Н/Д"
                        ),
                        (
                            f"{apt.time_slot.start_time.strftime('%H:%M')}-{apt.time_slot.end_time.strftime('%H:%M')}"
                            if apt.time_slot
                            else "Н/Д"
                        ),
                        (
                            f"{apt.time_slot.doctor.surname} {apt.time_slot.doctor.first_name} {apt.time_slot.doctor.last_name or ''}".strip()
                            if apt.time_slot and apt.time_slot.doctor
                            else "Н/Д"
                        ),
                        apt.service.name if apt.service else "Н/Д",
                    ]
                )

                processed += 1
                if processed % 1000 == 0:
                    self.stdout.write(f"Обработано {processed}/{total} записей")

        self.stdout.write(
            self.style.SUCCESS(
                f"Успешно экспортировано {processed} записей в {output_file}"
            )
        )
