import datetime
import hashlib
import hmac
import json
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from catalog.models import Category, Project, ProjectAddon, ProjectAddonPrice
from core.models import SiteSettings
from core.testing import force_login_verified
from leads.models import ConsentRecord

from .delivery import delivery_deadline, describe_deadline
from .gateway import GatewayError, RazorpayGateway
from .models import Order, PaymentEvent, ReceiptCounter, Refund, RefundRequest
from . import services


IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
OPEN, CLOSE = datetime.time(10, 0), datetime.time(19, 0)
MON_SAT = {0, 1, 2, 3, 4, 5}


def ist(year, month, day, hour, minute=0):
    return datetime.datetime(year, month, day, hour, minute, tzinfo=IST)


class FakeGateway(RazorpayGateway):
    """The real signature checks, with no network."""

    def __init__(self):
        super().__init__(key_id="rzp_test_key", key_secret="test_secret", webhook_secret="whsec")
        self.payment = {}
        self.fail_create = False
        self.refunds = []
        self.captures = []

    def _request(self, method, path, payload=None):
        if path == "/orders":
            if self.fail_create:
                raise GatewayError("down")
            return {"id": "order_TEST1"}
        if path.startswith("/payments/") and path.endswith("/refund"):
            self.refunds.append((path, payload))
            return {"id": "rfnd_1"}
        if path.startswith("/payments/") and path.endswith("/capture"):
            self.captures.append(path)
            self.payment = {**self.payment, "status": "captured"}
            return self.payment
        if path.startswith("/payments/"):
            return self.payment
        raise AssertionError(path)

    def sign_payment(self, order_id, payment_id):
        return hmac.new(b"test_secret", f"{order_id}|{payment_id}".encode(), hashlib.sha256).hexdigest()

    def sign_webhook(self, body):
        return hmac.new(b"whsec", body, hashlib.sha256).hexdigest()


class DeliveryDeadlineTests(TestCase):
    def deadline(self, paid, hours=2):
        return delivery_deadline(paid, hours, OPEN, CLOSE, MON_SAT)

    def test_inside_hours_is_paid_time_plus_window(self):
        # Monday 19 Oct 2026, 11:30
        self.assertEqual(self.deadline(ist(2026, 10, 19, 11, 30)), ist(2026, 10, 19, 13, 30))

    def test_window_that_passes_closing_goes_to_next_morning(self):
        self.assertEqual(self.deadline(ist(2026, 10, 19, 18, 0)), ist(2026, 10, 20, 12, 0))

    def test_exactly_fits_before_closing(self):
        self.assertEqual(self.deadline(ist(2026, 10, 19, 17, 0)), ist(2026, 10, 19, 19, 0))

    def test_night_goes_to_next_morning(self):
        self.assertEqual(self.deadline(ist(2026, 10, 19, 22, 0)), ist(2026, 10, 20, 12, 0))

    def test_early_morning_counts_from_opening_today(self):
        self.assertEqual(self.deadline(ist(2026, 10, 19, 7, 0)), ist(2026, 10, 19, 12, 0))

    def test_sunday_goes_to_monday(self):
        self.assertEqual(self.deadline(ist(2026, 10, 18, 12, 0)), ist(2026, 10, 19, 12, 0))

    def test_saturday_evening_skips_sunday(self):
        self.assertEqual(self.deadline(ist(2026, 10, 17, 18, 30)), ist(2026, 10, 19, 12, 0))

    def test_extra_hours_from_addons(self):
        self.assertEqual(self.deadline(ist(2026, 10, 19, 11, 0), hours=5), ist(2026, 10, 19, 16, 0))

    def test_window_longer_than_a_day_spills_over(self):
        # Opens 10:00, 9 working hours a day; 12 hours = 9 on Tuesday + 3 on Wednesday.
        self.assertEqual(self.deadline(ist(2026, 10, 19, 22, 0), hours=12), ist(2026, 10, 21, 13, 0))

    def test_describe_deadline(self):
        now = ist(2026, 10, 19, 11, 0)
        self.assertEqual(describe_deadline(ist(2026, 10, 19, 16, 30), now=now), "by 4:30 pm today")
        self.assertEqual(describe_deadline(ist(2026, 10, 20, 12, 0), now=now), "by 12:00 pm tomorrow")
        self.assertEqual(describe_deadline(ist(2026, 10, 22, 12, 0), now=now), "by 12:00 pm on Thu 22 Oct")


class ReceiptNumberTests(TestCase):
    def test_sequential_within_a_financial_year(self):
        moment = ist(2026, 6, 1, 10)
        self.assertEqual(ReceiptCounter.issue(moment), "PV/2026-27/0001")
        self.assertEqual(ReceiptCounter.issue(moment), "PV/2026-27/0002")

    def test_new_year_starts_in_april(self):
        self.assertEqual(ReceiptCounter.issue(ist(2027, 3, 31, 23)), "PV/2026-27/0001")
        self.assertEqual(ReceiptCounter.issue(ist(2027, 4, 1, 0, 30)), "PV/2027-28/0001")
        self.assertEqual(ReceiptCounter.issue(ist(2027, 4, 2, 9)), "PV/2027-28/0002")


class GatewaySignatureTests(TestCase):
    def setUp(self):
        self.gateway = FakeGateway()

    def test_payment_signature(self):
        good = self.gateway.sign_payment("order_1", "pay_1")
        self.assertTrue(self.gateway.verify_payment_signature("order_1", "pay_1", good))
        self.assertFalse(self.gateway.verify_payment_signature("order_1", "pay_2", good))
        self.assertFalse(self.gateway.verify_payment_signature("order_1", "pay_1", ""))

    def test_webhook_signature(self):
        body = b'{"a": 1}'
        self.assertTrue(self.gateway.verify_webhook_signature(body, self.gateway.sign_webhook(body)))
        self.assertFalse(self.gateway.verify_webhook_signature(body, "bad"))
        self.assertFalse(self.gateway.verify_webhook_signature(body, ""))

    def test_no_webhook_secret_rejects_everything(self):
        gateway = RazorpayGateway(key_id="a", key_secret="b", webhook_secret="")
        self.assertFalse(gateway.verify_webhook_signature(b"x", "anything"))

    def test_test_mode_detection(self):
        self.assertTrue(self.gateway.is_test_mode)
        self.assertFalse(RazorpayGateway(key_id="rzp_live_x", key_secret="s").is_test_mode)

    def test_unconfigured_gateway_raises(self):
        with self.assertRaises(GatewayError):
            RazorpayGateway(key_id="", key_secret="").create_order(100, "r")


@override_settings(PUBLIC_CONTACT_EMAIL="owner@example.com", ORDERS_FROM_EMAIL="orders@example.com", SITE_URL="https://example.com")
class OrdersTestCase(TestCase):
    def setUp(self):
        cache.clear()  # rate-limit counters live in the cache and would leak between tests
        self.gateway = FakeGateway()
        for target in ("orders.services.get_gateway", "orders.views.get_gateway", "orders.admin.get_gateway"):
            patcher = mock.patch(target, return_value=self.gateway)
            patcher.start()
            self.addCleanup(patcher.stop)

        site = SiteSettings.get_solo()
        site.payments_enabled = True
        site.save()

        self.category = Category.objects.create(name="AI", slug="ai-orders")
        self.project = Project.objects.create(
            title="Smart Attendance",
            slug="smart-attendance",
            short_description="Short.",
            description="Long.",
            category=self.category,
            is_published=True,
            price=Decimal("5000"),
            accept_online_payment=True,
        )
        self.docs = ProjectAddon.objects.create(name="Documentation", slug="docs-o", price=Decimal("999"), extra_delivery_hours=2)
        self.viva = ProjectAddon.objects.create(name="Viva prep", slug="viva-o", price=Decimal("499"))
        self.free = ProjectAddon.objects.create(name="Setup guide", slug="guide-o")
        self.hidden = ProjectAddon.objects.create(name="Inactive", slug="inactive-o", price=Decimal("1"), is_active=False)
        self.unpriced = ProjectAddon.objects.create(name="Unpriced", slug="unpriced-o")
        self.project.addons.add(self.docs, self.viva, self.free, self.hidden, self.unpriced)
        ProjectAddonPrice.objects.create(project=self.project, addon=self.free, included_free=True)
        self.other_addon = ProjectAddon.objects.create(name="Other project", slug="other-o", price=Decimal("10"))

    def form_data(self, **extra):
        data = {
            "name": "Asha Rao",
            "email": "asha@example.com",
            "phone": "9876543210",
            "delivery_channel": "email",
            "consent_terms": "on",
            "consent_contact": "on",
            "consent_age": "on",
            "website": "",
        }
        data.update(extra)
        return data

    def place_order(self, addons=(), **extra):
        response = self.client.post(
            reverse("orders:checkout", args=[self.project.slug]), self.form_data(addons=list(addons), **extra)
        )
        return response

    def make_order(self, **extra):
        order = Order.objects.create(
            project=self.project,
            project_title=self.project.title,
            customer_name="Asha Rao",
            customer_email="asha@example.com",
            customer_phone="9876543210",
            subtotal=Decimal("5000"),
            total=Decimal("5000"),
            razorpay_order_id="order_TEST1",
            **extra,
        )
        order.items.create(kind="project", name=self.project.title, unit_price=Decimal("5000"), line_total=Decimal("5000"))
        return order

    def payment(self, order, **extra):
        data = {"id": "pay_1", "order_id": order.razorpay_order_id, "status": "captured", "amount": 500000, "currency": "INR", "method": "upi"}
        data.update(extra)
        self.gateway.payment = data
        return data

    def verify(self, order, payment_id="pay_1", signature=None):
        return self.client.post(
            reverse("orders:verify"),
            {
                "razorpay_order_id": order.razorpay_order_id,
                "razorpay_payment_id": payment_id,
                "razorpay_signature": signature or self.gateway.sign_payment(order.razorpay_order_id, payment_id),
            },
        )


class CheckoutAvailabilityTests(OrdersTestCase):
    def assertWhatsAppFlow(self):
        response = self.client.get(f"/projects/{self.project.slug}/")
        self.assertNotContains(response, reverse("orders:checkout", args=[self.project.slug]))
        self.assertContains(response, "data-enquiry-open")
        self.assertEqual(self.client.get(reverse("orders:checkout", args=[self.project.slug])).status_code, 404)

    def test_all_conditions_met_shows_checkout(self):
        response = self.client.get(f"/projects/{self.project.slug}/")
        self.assertContains(response, reverse("orders:checkout", args=[self.project.slug]))
        self.assertNotContains(response, "data-enquiry-open")
        self.assertEqual(self.client.get(reverse("orders:checkout", args=[self.project.slug])).status_code, 200)

    def test_master_switch_off(self):
        site = SiteSettings.get_solo()
        site.payments_enabled = False
        site.save()
        self.assertWhatsAppFlow()

    def test_project_flag_off(self):
        Project.objects.filter(pk=self.project.pk).update(accept_online_payment=False)
        self.assertWhatsAppFlow()

    def test_no_price(self):
        Project.objects.filter(pk=self.project.pk).update(price=None)
        self.assertWhatsAppFlow()

    def test_hidden_price(self):
        Project.objects.filter(pk=self.project.pk).update(show_price=False)
        self.assertWhatsAppFlow()

    def test_no_keys(self):
        self.gateway.key_id = self.gateway.key_secret = ""
        self.assertWhatsAppFlow()

    def test_unpublished_policy_blocks_checkout(self):
        from legal.models import LegalPage

        LegalPage.objects.filter(slug="refund-policy").update(is_published=False)
        self.assertWhatsAppFlow()


class CheckoutTotalsTests(OrdersTestCase):
    def test_server_calculates_the_total_and_snapshots_items(self):
        response = self.place_order(addons=[self.docs.pk, self.viva.pk, self.free.pk])
        order = Order.objects.get()
        self.assertRedirects(response, reverse("orders:pay", args=[order.public_token]), fetch_redirect_response=False)
        self.assertEqual(order.total, Decimal("6498"))
        self.assertEqual(order.status, Order.Status.CREATED)
        self.assertEqual(order.razorpay_order_id, "order_TEST1")
        self.assertEqual(
            sorted((i.name, i.line_total) for i in order.items.all()),
            [("Documentation", Decimal("999")), ("Setup guide", Decimal("0")), ("Smart Attendance", Decimal("5000")), ("Viva prep", Decimal("499"))],
        )
        self.assertIsNotNone(order.terms_version)
        self.assertIsNotNone(order.refund_policy_version)

    def test_tampered_prices_in_the_post_are_ignored(self):
        self.place_order(addons=[self.docs.pk], total="1", price="1", amount="1")
        self.assertEqual(Order.objects.get().total, Decimal("5999"))

    def test_project_override_price_is_used(self):
        ProjectAddonPrice.objects.create(project=self.project, addon=self.docs, price_override=Decimal("100"))
        self.place_order(addons=[self.docs.pk])
        self.assertEqual(Order.objects.get().total, Decimal("5100"))

    def test_sale_price_is_charged(self):
        Project.objects.filter(pk=self.project.pk).update(sale_price=Decimal("4000"))
        self.place_order()
        self.assertEqual(Order.objects.get().total, Decimal("4000"))

    def test_unknown_inactive_unpriced_and_foreign_addons_are_rejected(self):
        for bad in (self.hidden.pk, self.unpriced.pk, self.other_addon.pk, 99999, "abc"):
            with self.subTest(addon=bad):
                response = self.place_order(addons=[bad])
                self.assertEqual(response.status_code, 200)
                self.assertFalse(Order.objects.exists())

    def test_duplicate_addon_is_counted_once(self):
        self.place_order(addons=[self.docs.pk, self.docs.pk])
        self.assertEqual(Order.objects.get().total, Decimal("5999"))

    def test_consent_is_required_and_stored(self):
        response = self.client.post(
            reverse("orders:checkout", args=[self.project.slug]),
            {k: v for k, v in self.form_data().items() if k != "consent_terms"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Order.objects.exists())

        self.place_order()
        consent = ConsentRecord.objects.get(order=Order.objects.get())
        self.assertTrue(consent.contact_consent and consent.age_confirmed)
        self.assertFalse(consent.marketing_opt_in)
        self.assertIn("Terms and Conditions", consent.consent_text)

    def test_honeypot_blocks_bots(self):
        self.place_order(website="spam")
        self.assertFalse(Order.objects.exists())

    def test_bad_phone_is_rejected(self):
        self.place_order(phone="12")
        self.assertFalse(Order.objects.exists())

    def test_gateway_down_shows_error_and_marks_order_failed(self):
        self.gateway.fail_create = True
        response = self.place_order()
        self.assertEqual(response.status_code, 503)
        self.assertContains(response, "could not reach the payment service", status_code=503)
        self.assertEqual(Order.objects.get().status, Order.Status.FAILED)

    @override_settings(ENQUIRY_RATE_LIMIT=1)
    def test_rate_limited(self):
        cache.clear()
        self.assertEqual(self.place_order().status_code, 302)
        self.assertEqual(self.place_order().status_code, 429)

    def test_checkout_page_lists_only_purchasable_addons(self):
        html = self.client.get(reverse("orders:checkout", args=[self.project.slug])).content.decode()
        self.assertIn("Documentation", html)
        self.assertIn("Included", html)
        self.assertNotIn("Inactive", html)
        self.assertNotIn("Unpriced", html)
        self.assertNotIn("Other project", html)

    def test_pay_page_has_the_razorpay_details_and_test_banner(self):
        self.place_order()
        order = Order.objects.get()
        html = self.client.get(reverse("orders:pay", args=[order.public_token])).content.decode()
        self.assertIn('data-order-id="order_TEST1"', html)
        self.assertIn('data-amount="500000"', html)
        self.assertIn("TEST MODE", html)
        self.assertNotIn("test_secret", html)


class PaymentVerificationTests(OrdersTestCase):
    def test_valid_payment_marks_paid_once_with_receipt_and_two_emails(self):
        order = self.make_order()
        self.payment(order)
        response = self.verify(order)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["redirect"], reverse("orders:detail", args=[order.public_token]))

        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PAID)
        self.assertRegex(order.receipt_number, r"^PV/\d{4}-\d{2}/0001$")
        self.assertEqual(order.razorpay_payment_id, "pay_1")
        self.assertEqual(order.payment_method, "upi")
        self.assertIsNotNone(order.delivery_deadline)
        self.assertTrue(order.customer_emailed and order.owner_notified)
        self.assertEqual(sorted(m.to[0] for m in mail.outbox), ["asha@example.com", "owner@example.com"])

    def test_double_verify_issues_one_receipt_and_one_set_of_emails(self):
        order = self.make_order()
        self.payment(order)
        self.verify(order)
        number = Order.objects.get().receipt_number
        self.verify(order)
        self.assertEqual(Order.objects.get().receipt_number, number)
        self.assertEqual(ReceiptCounter.objects.get().last_number, 1)
        self.assertEqual(len(mail.outbox), 2)

    def test_bad_signature_is_rejected(self):
        order = self.make_order()
        self.payment(order)
        response = self.verify(order, signature="forged")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Order.objects.get().status, Order.Status.CREATED)
        self.assertEqual(mail.outbox, [])

    def test_amount_mismatch_is_not_paid(self):
        order = self.make_order()
        self.payment(order, amount=100)
        self.assertEqual(self.verify(order).status_code, 400)
        self.assertEqual(Order.objects.get().status, Order.Status.CREATED)

    def test_uncaptured_or_wrong_order_payment_is_not_paid(self):
        order = self.make_order()
        for override in ({"order_id": "order_OTHER"}, {"currency": "USD"}):
            with self.subTest(override=override):
                self.payment(order, **override)
                self.assertEqual(self.verify(order).status_code, 400)
                self.assertEqual(Order.objects.get().status, Order.Status.CREATED)

    def test_authorized_payment_is_captured_then_paid(self):
        order = self.make_order()
        self.payment(order, status="authorized")
        self.assertEqual(self.verify(order).status_code, 200)
        self.assertEqual(self.gateway.captures, ["/payments/pay_1/capture"])
        self.assertEqual(Order.objects.get().status, Order.Status.PAID)

    def test_authorized_payment_with_wrong_amount_is_not_captured(self):
        order = self.make_order()
        self.payment(order, status="authorized", amount=100)
        self.assertEqual(self.verify(order).status_code, 400)
        self.assertEqual(self.gateway.captures, [])

    def test_unknown_order_is_rejected(self):
        response = self.client.post(reverse("orders:verify"), {"razorpay_order_id": "order_NOPE", "razorpay_payment_id": "p", "razorpay_signature": "s"})
        self.assertEqual(response.status_code, 400)

    def test_gateway_unreachable_does_not_mark_paid(self):
        order = self.make_order()
        with mock.patch.object(self.gateway, "fetch_payment", side_effect=GatewayError("down")):
            self.assertEqual(self.verify(order).status_code, 400)
        self.assertEqual(Order.objects.get().status, Order.Status.CREATED)

    def test_deadline_includes_the_longest_addon_extra_hours(self):
        order = self.make_order()
        order.items.create(kind="addon", addon=self.docs, name="Documentation", unit_price=Decimal("999"), line_total=Decimal("999"), extra_delivery_hours=2)
        self.assertEqual(services.delivery_hours_for(order, SiteSettings.get_solo()), 4)
        Project.objects.filter(pk=self.project.pk).update(delivery_hours=6)
        order.project.refresh_from_db()
        self.assertEqual(services.delivery_hours_for(order, SiteSettings.get_solo()), 8)

    def test_order_pages(self):
        order = self.make_order()
        self.payment(order)
        # Unpaid: detail redirects to the failure page, receipt is hidden.
        self.assertEqual(self.client.get(reverse("orders:receipt", args=[order.public_token])).status_code, 404)
        self.verify(order)
        detail = self.client.get(reverse("orders:detail", args=[order.public_token]))
        self.assertContains(detail, order.reference)
        receipt = self.client.get(reverse("orders:receipt", args=[order.public_token]))
        self.assertContains(receipt, "Payment Receipt")
        self.assertContains(receipt, "₹5,000")
        self.assertContains(receipt, "not registered for GST")
        self.assertEqual(self.client.get(reverse("orders:detail", args=["00000000-0000-4000-8000-000000000000"])).status_code, 404)

    def test_receipt_becomes_tax_invoice_with_a_gstin(self):
        order = self.make_order()
        self.payment(order)
        self.verify(order)
        site = SiteSettings.get_solo()
        site.gstin = "29ABCDE1234F1Z5"
        site.save()
        self.assertContains(self.client.get(reverse("orders:receipt", args=[order.public_token])), "Tax Invoice")

    def test_failed_page_and_retry(self):
        order = self.make_order(status=Order.Status.FAILED)
        failed = self.client.get(reverse("orders:failed", args=[order.public_token]))
        self.assertContains(failed, "Try payment again")
        response = self.client.post(reverse("orders:retry", args=[order.public_token]))
        self.assertRedirects(response, reverse("orders:pay", args=[order.public_token]), fetch_redirect_response=False)
        self.assertEqual(Order.objects.get().status, Order.Status.CREATED)


class WebhookTests(OrdersTestCase):
    def post(self, event, order, event_id="evt_1", signature=None, **entity):
        payment = {"id": "pay_1", "order_id": order.razorpay_order_id, "amount": 500000, "currency": "INR", "method": "card", **entity}
        body = json.dumps({"event": event, "payload": {"payment": {"entity": payment}}}).encode()
        return self.client.post(
            reverse("orders:webhook"),
            data=body,
            content_type="application/json",
            HTTP_X_RAZORPAY_SIGNATURE=self.gateway.sign_webhook(body) if signature is None else signature,
            HTTP_X_RAZORPAY_EVENT_ID=event_id,
        )

    def test_bad_or_missing_signature_is_rejected(self):
        order = self.make_order()
        self.assertEqual(self.post("payment.captured", order, signature="bad").status_code, 400)
        self.assertEqual(self.post("payment.captured", order, signature="").status_code, 400)
        self.assertEqual(Order.objects.get().status, Order.Status.CREATED)
        self.assertFalse(PaymentEvent.objects.exists())

    def test_captured_marks_paid_when_the_browser_never_came_back(self):
        order = self.make_order()
        self.assertEqual(self.post("payment.captured", order).status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PAID)
        self.assertEqual(order.payment_method, "card")
        self.assertEqual(len(mail.outbox), 2)

    def test_duplicate_event_is_ignored(self):
        order = self.make_order()
        self.post("payment.captured", order)
        self.post("payment.captured", order)
        self.assertEqual(PaymentEvent.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 2)

    def test_verify_then_webhook_is_still_one_transition(self):
        order = self.make_order()
        self.payment(order)
        self.verify(order)
        self.post("payment.captured", order, event_id="evt_2")
        self.assertEqual(ReceiptCounter.objects.get().last_number, 1)
        self.assertEqual(len(mail.outbox), 2)

    def test_captured_with_wrong_amount_is_not_paid(self):
        order = self.make_order()
        self.post("payment.captured", order, amount=1)
        self.assertEqual(Order.objects.get().status, Order.Status.CREATED)

    def test_payment_failed_only_affects_unpaid_orders(self):
        order = self.make_order()
        self.post("payment.failed", order)
        self.assertEqual(Order.objects.get().status, Order.Status.FAILED)
        paid = self.make_order(status=Order.Status.PAID)
        paid.razorpay_order_id = "order_PAID"
        paid.save()
        self.post("payment.failed", paid, event_id="evt_9")
        self.assertEqual(Order.objects.get(pk=paid.pk).status, Order.Status.PAID)

    def test_refund_processed_updates_refund_order_and_emails_customer(self):
        order = self.make_order(status=Order.Status.PAID)
        refund = Refund.objects.create(order=order, amount=order.total, razorpay_refund_id="rfnd_1")
        body = json.dumps({"event": "refund.processed", "payload": {"refund": {"entity": {"id": "rfnd_1"}}}}).encode()
        response = self.client.post(
            reverse("orders:webhook"), data=body, content_type="application/json",
            HTTP_X_RAZORPAY_SIGNATURE=self.gateway.sign_webhook(body), HTTP_X_RAZORPAY_EVENT_ID="evt_r1",
        )
        self.assertEqual(response.status_code, 200)
        refund.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(refund.status, Refund.Status.PROCESSED)
        self.assertEqual(order.status, Order.Status.REFUNDED)
        self.assertEqual([m.to[0] for m in mail.outbox], ["asha@example.com"])

    def test_refund_failed_marks_the_refund_failed(self):
        order = self.make_order(status=Order.Status.PAID)
        refund = Refund.objects.create(order=order, amount=Decimal("100"), razorpay_refund_id="rfnd_1")
        body = json.dumps({"event": "refund.failed", "payload": {"refund": {"entity": {"id": "rfnd_1"}}}}).encode()
        self.client.post(
            reverse("orders:webhook"), data=body, content_type="application/json",
            HTTP_X_RAZORPAY_SIGNATURE=self.gateway.sign_webhook(body), HTTP_X_RAZORPAY_EVENT_ID="evt_r2",
        )
        refund.refresh_from_db()
        self.assertEqual(refund.status, Refund.Status.FAILED)
        self.assertEqual(Order.objects.get().status, Order.Status.PAID)

    def test_get_is_not_allowed(self):
        self.assertEqual(self.client.get(reverse("orders:webhook")).status_code, 405)


class RefundRequestTests(OrdersTestCase):
    def submit(self, **extra):
        data = {"reference": "PVO-1001", "email": "asha@example.com", "reason": "The files did not open.", "website": ""}
        data.update(extra)
        return self.client.post(reverse("orders:refund_request"), data)

    def test_saved_matched_and_both_emails_sent(self):
        order = self.make_order(status=Order.Status.PAID)
        self.assertEqual(order.reference, "PVO-1001")
        response = self.submit()
        self.assertRedirects(response, reverse("orders:refund_request_received"))
        refund_request = RefundRequest.objects.get()
        self.assertEqual(refund_request.order, order)
        self.assertEqual(refund_request.status, RefundRequest.Status.OPEN)
        self.assertEqual(sorted(m.to[0] for m in mail.outbox), ["asha@example.com", "owner@example.com"])

    def test_acknowledgement_does_not_echo_input(self):
        self.make_order(status=Order.Status.PAID)
        self.submit(reason="UNIQUE-REASON-TEXT for the owner")
        customer = next(m for m in mail.outbox if m.to == ["asha@example.com"])
        owner = next(m for m in mail.outbox if m.to == ["owner@example.com"])
        self.assertNotIn("UNIQUE-REASON-TEXT", customer.body)
        self.assertIn("UNIQUE-REASON-TEXT", owner.body)

    def test_wrong_email_is_saved_but_not_matched(self):
        self.make_order(status=Order.Status.PAID)
        self.submit(email="someone@else.com")
        self.assertIsNone(RefundRequest.objects.get().order)

    def test_validation_and_honeypot(self):
        self.submit(reference="BAD")
        self.submit(reason="short")
        self.submit(website="spam")
        self.assertFalse(RefundRequest.objects.exists())

    @override_settings(ENQUIRY_RATE_LIMIT=1)
    def test_rate_limited(self):
        cache.clear()
        self.assertEqual(self.submit().status_code, 302)
        self.assertEqual(self.submit().status_code, 429)

    def test_received_page_needs_a_session(self):
        self.assertRedirects(self.client.get(reverse("orders:refund_request_received")), reverse("orders:refund_request"))


class OrderAdminTests(OrdersTestCase):
    def setUp(self):
        super().setUp()
        self.staff = get_user_model().objects.create_superuser("boss", "boss@example.com", "pw")
        force_login_verified(self.client, self.staff)

    def paid_order(self):
        order = self.make_order()
        self.payment(order)
        self.verify(order)
        mail.outbox.clear()
        return Order.objects.get(pk=order.pk)

    def run_action(self, action, orders, **extra):
        data = {"action": action, "_selected_action": [o.pk for o in orders], **extra}
        return self.client.post(reverse("admin:orders_order_changelist"), data)

    def test_paid_orders_cannot_be_deleted_and_money_fields_are_read_only(self):
        order = self.paid_order()
        response = self.client.get(reverse("admin:orders_order_change", args=[order.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'name="total"')
        self.assertNotContains(response, 'name="status"')
        delete = self.client.post(reverse("admin:orders_order_delete", args=[order.pk]), {"post": "yes"})
        self.assertEqual(delete.status_code, 403)
        self.assertTrue(Order.objects.filter(pk=order.pk).exists())

    def test_mark_delivered_asks_then_emails_customer(self):
        order = self.paid_order()
        self.assertContains(self.run_action("mark_delivered", [order]), "Mark delivered")
        self.assertEqual(Order.objects.get().status, Order.Status.PAID)

        self.run_action(
            "mark_delivered", [order], confirm="yes", post="yes",
            delivery_link="https://drive.google.com/file/abc", delivery_note="Open README first.",
        )
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.DELIVERED)
        self.assertIsNotNone(order.delivered_at)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("https://drive.google.com/file/abc", mail.outbox[0].body)
        self.assertIn("Open README first.", mail.outbox[0].body)
        self.assertEqual(mail.outbox[0].to, ["asha@example.com"])

    def test_mark_processing(self):
        order = self.paid_order()
        self.run_action("mark_processing", [order])
        self.assertEqual(Order.objects.get().status, Order.Status.PROCESSING)

    def test_issue_refund_calls_gateway_and_records_pending_refund(self):
        order = self.paid_order()
        self.assertContains(self.run_action("issue_refund", [order]), "Issue refund")
        self.run_action("issue_refund", [order], confirm="yes", post="yes", amount="1000.50", reason="Partial")
        refund = Refund.objects.get()
        self.assertEqual(refund.amount, Decimal("1000.50"))
        self.assertEqual(refund.status, Refund.Status.PENDING)
        self.assertEqual(refund.razorpay_refund_id, "rfnd_1")
        self.assertEqual(refund.created_by, self.staff)
        self.assertEqual(self.gateway.refunds, [("/payments/pay_1/refund", {"amount": 100050, "notes": {}})])

    def test_cannot_refund_more_than_remaining(self):
        order = self.paid_order()
        self.run_action("issue_refund", [order], confirm="yes", post="yes", amount="5000.01")
        self.assertFalse(Refund.objects.exists())
        self.assertEqual(self.gateway.refunds, [])

    def test_refund_gateway_error_records_nothing(self):
        order = self.paid_order()
        with mock.patch.object(self.gateway, "refund", side_effect=GatewayError("nope")):
            self.run_action("issue_refund", [order], confirm="yes", post="yes", amount="100")
        self.assertFalse(Refund.objects.exists())

    def test_csv_export(self):
        order = self.paid_order()
        response = self.run_action("export_csv", [order])
        text = response.content.decode()
        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
        self.assertIn(order.receipt_number, text)
        self.assertIn("PVO-1001", text)
        self.assertIn("pay_1", text)
        self.assertIn("5000.00", text)

    def test_csv_neutralises_formulas(self):
        order = self.paid_order()
        Order.objects.filter(pk=order.pk).update(customer_name="=HYPERLINK(1)")
        self.assertIn("'=HYPERLINK(1)", self.run_action("export_csv", [order]).content.decode())

    def test_search_by_reference(self):
        order = self.paid_order()
        response = self.client.get(reverse("admin:orders_order_changelist"), {"q": order.reference})
        self.assertContains(response, order.customer_name)

    def test_test_mode_banner_on_changelist(self):
        self.assertContains(self.client.get(reverse("admin:orders_order_changelist")), "TEST MODE")

    def test_refund_request_actions_do_not_move_money(self):
        order = self.paid_order()
        request = RefundRequest.objects.create(order=order, reference=order.reference, email=order.customer_email, reason="Not working")
        self.client.post(
            reverse("admin:orders_refundrequest_changelist"),
            {"action": "approve_requests", "_selected_action": [request.pk]},
        )
        request.refresh_from_db()
        self.assertEqual(request.status, RefundRequest.Status.APPROVED)
        self.assertEqual(request.handled_by, self.staff)
        self.assertFalse(Refund.objects.exists())
        self.assertEqual(self.gateway.refunds, [])


class CommandTests(OrdersTestCase):
    def test_overdue_alert_sent_once(self):
        past = timezone.now() - datetime.timedelta(hours=1)
        overdue = self.make_order(status=Order.Status.PAID, delivery_deadline=past, paid_at=past)
        self.make_order(status=Order.Status.PAID, delivery_deadline=timezone.now() + datetime.timedelta(hours=3), paid_at=past)
        self.make_order(status=Order.Status.DELIVERED, delivery_deadline=past, paid_at=past)

        call_command("send_overdue_alerts")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, f"Overdue: {overdue.reference}")
        overdue.refresh_from_db()
        self.assertIsNotNone(overdue.overdue_alert_sent_at)

        call_command("send_overdue_alerts")
        self.assertEqual(len(mail.outbox), 1)

    def test_expire_unpaid_orders(self):
        old = self.make_order()
        Order.objects.filter(pk=old.pk).update(created_at=timezone.now() - datetime.timedelta(hours=25))
        fresh = self.make_order()
        paid_old = self.make_order(status=Order.Status.PAID)
        Order.objects.filter(pk=paid_old.pk).update(created_at=timezone.now() - datetime.timedelta(days=5))

        call_command("expire_unpaid_orders")
        self.assertEqual(Order.objects.get(pk=old.pk).status, Order.Status.CANCELLED)
        self.assertEqual(Order.objects.get(pk=fresh.pk).status, Order.Status.CREATED)
        self.assertEqual(Order.objects.get(pk=paid_old.pk).status, Order.Status.PAID)


class SiteSettingsPaymentTests(TestCase):
    def test_defaults_keep_payments_off(self):
        site = SiteSettings.get_solo()
        self.assertFalse(site.payments_enabled)
        self.assertEqual(site.delivery_window_hours, 2)
        self.assertEqual(site.working_day_set, MON_SAT)

    def test_working_days_validation(self):
        from django.core.exceptions import ValidationError

        for bad in ("", "7", "a,b", "-1"):
            with self.subTest(value=bad), self.assertRaises(ValidationError):
                SiteSettings(working_days=bad).full_clean()

    def test_closing_must_be_after_opening(self):
        from django.core.exceptions import ValidationError

        with self.assertRaises(ValidationError):
            SiteSettings(business_open_time=OPEN, business_close_time=OPEN).full_clean()
