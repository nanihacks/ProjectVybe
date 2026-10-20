from django.core.management.base import BaseCommand, CommandError

from courses.privacy import DEFAULT_RETENTION_MONTHS, anonymise_entries, entries_past_retention


class Command(BaseCommand):
    help = "Remove personal details from waitlist sign-ups older than the retention period (24 months)."

    def add_arguments(self, parser):
        parser.add_argument("--months", type=int, default=DEFAULT_RETENTION_MONTHS)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        months = options["months"]
        if months < 1:
            raise CommandError("--months must be at least 1.")
        due = entries_past_retention(months)
        if options["dry_run"]:
            self.stdout.write(f"{due.count()} sign-ups are older than {months} months (dry run, nothing changed).")
            return
        self.stdout.write(self.style.SUCCESS(f"Anonymised {anonymise_entries(due)} sign-ups older than {months} months."))
