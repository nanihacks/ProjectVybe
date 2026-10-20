from django.core.management.base import BaseCommand, CommandError

from leads.privacy import DEFAULT_RETENTION_MONTHS, anonymise_leads, leads_past_retention


class Command(BaseCommand):
    help = (
        "Remove personal details from enquiries older than the retention period "
        "stated in the Privacy Policy (24 months). Run it monthly from a Render Cron Job."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--months",
            type=int,
            default=DEFAULT_RETENTION_MONTHS,
            help=f"Keep enquiries this many months (default {DEFAULT_RETENTION_MONTHS}).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Only report how many enquiries would be anonymised.",
        )

    def handle(self, *args, **options):
        months = options["months"]
        if months < 1:
            raise CommandError("--months must be at least 1.")

        due = leads_past_retention(months)
        count = due.count()
        if options["dry_run"]:
            self.stdout.write(f"{count} enquiries are older than {months} months (dry run, nothing changed).")
            return

        changed = anonymise_leads(due)
        self.stdout.write(self.style.SUCCESS(f"Anonymised {changed} enquiries older than {months} months."))
