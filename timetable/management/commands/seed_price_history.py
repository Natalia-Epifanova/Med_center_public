import csv
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from timetable.models import MedicalService, MedicalServicePrice


class Command(BaseCommand):
    help = (
        "Creates or updates price history for selected medical services and syncs "
        "the current MedicalService.price to the new price."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "file_path",
            nargs="?",
            type=str,
            help=(
                "Path to CSV file with columns: code,new_price or name,new_price. "
                "Optional old_price column is also supported."
            ),
        )
        parser.add_argument(
            "--old-from",
            type=str,
            default="2026-01-01",
            help="Start date for old prices. Default: 2026-01-01",
        )
        parser.add_argument(
            "--effective-from",
            type=str,
            default="2026-03-25",
            help="Start date for new prices. Default: 2026-03-25",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview changes without writing to the database.",
        )
        parser.add_argument(
            "--bootstrap-old-prices",
            action="store_true",
            help=(
                "Create old price history for all services on --old-from using the "
                "current MedicalService.price, and sync current price from existing "
                "history on/after --effective-from when present."
            ),
        )

    def handle(self, *args, **options):
        old_from = self._parse_date(options["old_from"], "--old-from")
        effective_from = self._parse_date(options["effective_from"], "--effective-from")

        if old_from >= effective_from:
            raise CommandError("--old-from must be earlier than --effective-from")

        bootstrap_old_prices = options["bootstrap_old_prices"]
        file_path_arg = options.get("file_path")

        if bootstrap_old_prices:
            if file_path_arg:
                raise CommandError(
                    "Do not pass file_path together with --bootstrap-old-prices"
                )

            self.stdout.write(
                self.style.WARNING(
                    f"{'DRY RUN: ' if options['dry_run'] else ''}"
                    f"bootstrapping old prices for all services, old_from={old_from}, "
                    f"effective_from={effective_from}"
                )
            )

            if options["dry_run"]:
                self._bootstrap_old_prices(
                    old_from=old_from,
                    effective_from=effective_from,
                    dry_run=True,
                )
                return

            with transaction.atomic():
                self._bootstrap_old_prices(
                    old_from=old_from,
                    effective_from=effective_from,
                    dry_run=False,
                )
            return

        if not file_path_arg:
            raise CommandError(
                "file_path is required unless --bootstrap-old-prices is used"
            )

        file_path = Path(file_path_arg)
        if not file_path.exists():
            raise CommandError(f"File not found: {file_path}")

        rows = self._read_csv(file_path)
        if not rows:
            raise CommandError("CSV file is empty")

        self.stdout.write(
            self.style.WARNING(
                f"{'DRY RUN: ' if options['dry_run'] else ''}"
                f"processing {len(rows)} row(s), old_from={old_from}, effective_from={effective_from}"
            )
        )

        if options["dry_run"]:
            self._process_rows(rows, old_from, effective_from, dry_run=True)
            return

        with transaction.atomic():
            self._process_rows(rows, old_from, effective_from, dry_run=False)

    def _process_rows(self, rows, old_from, effective_from, dry_run):
        created_old = 0
        updated_old = 0
        created_new = 0
        updated_new = 0
        synced_current = 0

        for index, row in enumerate(rows, start=2):
            service = self._find_service(row, index)
            new_price = self._parse_decimal(row.get("new_price"), "new_price", index)
            old_price = self._resolve_old_price(service, row, old_from, new_price, index)

            old_entry = service.prices.filter(valid_from=old_from).first()
            new_entry = service.prices.filter(valid_from=effective_from).first()

            if old_entry:
                if old_entry.price != old_price:
                    updated_old += 1
                    self.stdout.write(
                        f"[row {index}] {service.code} | old history {old_from}: {old_entry.price} -> {old_price}"
                    )
                    if not dry_run:
                        old_entry.price = old_price
                        old_entry.save(update_fields=["price"])
            else:
                created_old += 1
                self.stdout.write(
                    f"[row {index}] {service.code} | create old history {old_from}: {old_price}"
                )
                if not dry_run:
                    MedicalServicePrice.objects.create(
                        service=service, valid_from=old_from, price=old_price
                    )

            if new_entry:
                if new_entry.price != new_price:
                    updated_new += 1
                    self.stdout.write(
                        f"[row {index}] {service.code} | new history {effective_from}: {new_entry.price} -> {new_price}"
                    )
                    if not dry_run:
                        new_entry.price = new_price
                        new_entry.save(update_fields=["price"])
            else:
                created_new += 1
                self.stdout.write(
                    f"[row {index}] {service.code} | create new history {effective_from}: {new_price}"
                )
                if not dry_run:
                    MedicalServicePrice.objects.create(
                        service=service, valid_from=effective_from, price=new_price
                    )

            if service.price != new_price:
                synced_current += 1
                self.stdout.write(
                    f"[row {index}] {service.code} | sync current price: {service.price} -> {new_price}"
                )
                if not dry_run:
                    service.price = new_price
                    service.save(update_fields=["price"])

        summary = (
            f"Summary: created_old={created_old}, updated_old={updated_old}, "
            f"created_new={created_new}, updated_new={updated_new}, "
            f"synced_current={synced_current}"
        )
        self.stdout.write(self.style.SUCCESS(summary))

    def _bootstrap_old_prices(self, old_from, effective_from, dry_run):
        created_old = 0
        updated_old = 0
        synced_current = 0

        services = MedicalService.objects.all().order_by("code", "name")

        for service in services:
            old_entry = service.prices.filter(valid_from=old_from).first()
            if old_entry:
                if old_entry.price != service.price:
                    updated_old += 1
                    self.stdout.write(
                        f"{service.code} | old history {old_from}: {old_entry.price} -> {service.price}"
                    )
                    if not dry_run:
                        old_entry.price = service.price
                        old_entry.save(update_fields=["price"])
            else:
                created_old += 1
                self.stdout.write(
                    f"{service.code} | create old history {old_from}: {service.price}"
                )
                if not dry_run:
                    MedicalServicePrice.objects.create(
                        service=service,
                        valid_from=old_from,
                        price=service.price,
                    )

            latest_effective_entry = (
                service.prices.filter(valid_from__gte=effective_from)
                .order_by("-valid_from")
                .first()
            )
            if latest_effective_entry and service.price != latest_effective_entry.price:
                synced_current += 1
                self.stdout.write(
                    f"{service.code} | sync current price: {service.price} -> {latest_effective_entry.price}"
                )
                if not dry_run:
                    service.price = latest_effective_entry.price
                    service.save(update_fields=["price"])

        summary = (
            f"Summary: created_old={created_old}, updated_old={updated_old}, "
            f"synced_current={synced_current}"
        )
        self.stdout.write(self.style.SUCCESS(summary))

    def _find_service(self, row, index):
        code = (row.get("code") or "").strip()
        name = (row.get("name") or "").strip()

        if not code and not name:
            raise CommandError(
                f"Row {index}: one of 'code' or 'name' must be provided in the CSV"
            )

        if code:
            try:
                return MedicalService.objects.get(code=code)
            except MedicalService.DoesNotExist as exc:
                raise CommandError(f"Row {index}: service with code '{code}' not found") from exc
            except MedicalService.MultipleObjectsReturned as exc:
                raise CommandError(
                    f"Row {index}: multiple services found for code '{code}'"
                ) from exc

        matches = MedicalService.objects.filter(name=name)
        count = matches.count()
        if count == 1:
            return matches.first()
        if count == 0:
            raise CommandError(f"Row {index}: service with name '{name}' not found")
        raise CommandError(
            f"Row {index}: multiple services found for name '{name}', use code instead"
        )

    def _resolve_old_price(self, service, row, old_from, new_price, index):
        old_price_raw = (row.get("old_price") or "").strip()
        if old_price_raw:
            return self._parse_decimal(old_price_raw, "old_price", index)

        existing_old_entry = service.prices.filter(valid_from=old_from).first()
        if existing_old_entry:
            return existing_old_entry.price

        if service.price != new_price:
            return service.price

        raise CommandError(
            f"Row {index}: old_price is required for '{service.code}' because current price "
            f"is already equal to the new price and no old history exists for {old_from}"
        )

    @staticmethod
    def _read_csv(file_path):
        with file_path.open("r", encoding="utf-8-sig", newline="") as csvfile:
            reader = csv.DictReader(csvfile)
            return list(reader)

    @staticmethod
    def _parse_date(value, option_name):
        try:
            return date.fromisoformat(value)
        except ValueError as exc:
            raise CommandError(
                f"Invalid date for {option_name}: '{value}'. Use YYYY-MM-DD."
            ) from exc

    @staticmethod
    def _parse_decimal(value, field_name, index):
        if value is None or str(value).strip() == "":
            raise CommandError(f"Row {index}: '{field_name}' is required")

        normalized = str(value).strip().replace(",", ".")
        try:
            return Decimal(normalized)
        except InvalidOperation as exc:
            raise CommandError(
                f"Row {index}: invalid decimal in '{field_name}': '{value}'"
            ) from exc
