from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from timetable.models import BloodTest, BloodTestPrice


class Command(BaseCommand):
    help = (
        "Creates initial blood test price history from current BloodTest.price values."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--valid-from",
            type=str,
            default="2026-01-01",
            help="Start date for saved prices. Default: 2026-01-01",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview changes without writing to the database.",
        )
        parser.add_argument(
            "--update-existing",
            action="store_true",
            help=(
                "Update existing history rows for --valid-from to current "
                "BloodTest.price values. By default existing rows are kept as-is."
            ),
        )

    def handle(self, *args, **options):
        valid_from = self._parse_date(options["valid_from"])
        dry_run = options["dry_run"]
        update_existing = options["update_existing"]

        self.stdout.write(
            self.style.WARNING(
                f"{'DRY RUN: ' if dry_run else ''}"
                f"seeding blood test price history, valid_from={valid_from}, "
                f"update_existing={update_existing}"
            )
        )

        if dry_run:
            self._seed_prices(valid_from, update_existing, dry_run=True)
            return

        with transaction.atomic():
            self._seed_prices(valid_from, update_existing, dry_run=False)

    def _seed_prices(self, valid_from, update_existing, dry_run):
        created = 0
        updated = 0
        unchanged = 0
        skipped_existing = 0

        blood_tests = BloodTest.objects.select_related("category").order_by(
            "category__name",
            "code",
            "name",
        )

        for blood_test in blood_tests:
            entry = BloodTestPrice.objects.filter(
                blood_test=blood_test,
                valid_from=valid_from,
            ).first()

            if not entry:
                created += 1
                self.stdout.write(
                    f"{blood_test.code} | create history {valid_from}: {blood_test.price}"
                )
                if not dry_run:
                    BloodTestPrice.objects.create(
                        blood_test=blood_test,
                        valid_from=valid_from,
                        price=blood_test.price,
                    )
                continue

            if entry.price == blood_test.price:
                unchanged += 1
                continue

            if update_existing:
                updated += 1
                self.stdout.write(
                    f"{blood_test.code} | update history {valid_from}: {entry.price} -> {blood_test.price}"
                )
                if not dry_run:
                    entry.price = blood_test.price
                    entry.save(update_fields=["price"])
            else:
                skipped_existing += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"{blood_test.code} | history {valid_from} already exists "
                        f"with different price {entry.price}; current price is "
                        f"{blood_test.price}. Skipped."
                    )
                )

        summary = (
            f"Summary: created={created}, updated={updated}, unchanged={unchanged}, "
            f"skipped_existing={skipped_existing}"
        )
        self.stdout.write(self.style.SUCCESS(summary))

    @staticmethod
    def _parse_date(value):
        try:
            return date.fromisoformat(value)
        except ValueError as exc:
            raise CommandError(
                f"Invalid date for --valid-from: '{value}'. Use YYYY-MM-DD."
            ) from exc
