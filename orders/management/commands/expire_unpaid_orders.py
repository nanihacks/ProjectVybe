from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from orders.models import Order


class Command(BaseCommand):
    help = "Cancel orders that were never paid within 24 hours. Run it daily from a Render Cron Job."

    def add_arguments(self, parser):
        parser.add_argument("--hours", type=int, default=24)

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(hours=options["hours"])
        changed = Order.objects.filter(
            status__in=(Order.Status.CREATED, Order.Status.FAILED), created_at__lt=cutoff
        ).update(status=Order.Status.CANCELLED)
        self.stdout.write(f"Unpaid orders cancelled: {changed}.")
