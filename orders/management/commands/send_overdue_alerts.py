from django.core.management.base import BaseCommand
from django.utils import timezone

from orders.emails import send_overdue_alert
from orders.models import Order


class Command(BaseCommand):
    help = (
        "Email the owner once for each paid order that is past its delivery deadline. "
        "Run it every 15 minutes from a Render Cron Job."
    )

    def handle(self, *args, **options):
        now = timezone.now()
        overdue = Order.objects.filter(
            status__in=(Order.Status.PAID, Order.Status.PROCESSING),
            delivery_deadline__lt=now,
            overdue_alert_sent_at__isnull=True,
        )
        sent = 0
        for order in overdue:
            if send_overdue_alert(order.pk):
                Order.objects.filter(pk=order.pk).update(overdue_alert_sent_at=now)
                sent += 1
        self.stdout.write(f"Overdue alerts sent: {sent}.")
