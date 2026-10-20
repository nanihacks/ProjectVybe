import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from leads.models import Lead
from leads.utils import _confirmation_message, _owner_message
from orders import emails
from orders.models import Order, Refund, RefundRequest

from .email_render import build_email
from .testing import force_login_verified


@override_settings(SITE_URL="https://example.com", PUBLIC_CONTACT_EMAIL="owner@example.com")
class BrandedEmailTests(TestCase):
    def html(self, message):
        self.assertEqual(len(message.alternatives), 1)
        content, mimetype = message.alternatives[0]
        self.assertEqual(mimetype, "text/html")
        return content

    def make_lead(self, **extra):
        return Lead.objects.create(
            name="Asha", email="asha@example.com", phone="9876543210", message="Hello there, long enough.", **extra
        )

    def make_order(self, **extra):
        order = Order.objects.create(
            project_title="Smart Attendance",
            customer_name="Asha",
            customer_email="asha@example.com",
            customer_phone="9876543210",
            subtotal=Decimal("124999"),
            total=Decimal("124999"),
            status=Order.Status.PAID,
            paid_at=timezone.now(),
            delivery_deadline=timezone.now() + datetime.timedelta(hours=2),
            receipt_number="PV/2026-27/0001",
            razorpay_payment_id="pay_1",
            **extra,
        )
        order.items.create(kind="project", name="Smart Attendance", unit_price=Decimal("124999"), line_total=Decimal("124999"))
        return order

    def test_builder_makes_text_and_html_with_logo_and_button(self):
        message = build_email(
            "Hi\r\nBcc: x@example.com",
            {"heading": "Hello", "paragraphs": ["Body"], "button_url": "https://example.com/go", "button_label": "Go"},
            to=["a@example.com"],
            from_email="f@example.com",
        )
        self.assertNotIn("\n", message.subject)
        self.assertIn("Body", message.body)
        self.assertIn("Go: https://example.com/go", message.body)
        html = self.html(message)
        self.assertIn("https://example.com/static/images/brand/projectvybe-logo-email.png", html)
        self.assertIn('href="https://example.com/go"', html)
        self.assertIn("owner@example.com", html)

    def test_no_button_when_no_url(self):
        message = build_email("S", {"heading": "H", "button_url": "", "button_label": "Go"}, to=["a@example.com"], from_email="f@example.com")
        self.assertNotIn(">Go<", self.html(message))

    def test_html_is_escaped_but_text_is_not_html(self):
        lead = self.make_lead()
        Lead.objects.filter(pk=lead.pk).update(name="<script>alert(1)</script>", message="<b>bold</b> & more text")
        lead.refresh_from_db()
        message = _owner_message(lead, "owner@example.com")
        html = self.html(message)
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("&lt;b&gt;bold&lt;/b&gt; &amp; more text", html)
        self.assertIn("<b>bold</b> & more text", message.body)

    def test_visitor_confirmation_never_echoes_input_in_either_version(self):
        lead = self.make_lead()
        Lead.objects.filter(pk=lead.pk).update(name="Mallory", message="evil.example spam link text", phone="99999 11111")
        lead.refresh_from_db()
        message = _confirmation_message(lead, "owner@example.com")
        for content in (message.body, self.html(message)):
            self.assertNotIn("Mallory", content)
            self.assertNotIn("evil.example", content)
            self.assertNotIn("99999", content)
            self.assertIn(lead.reference, content)

    def test_order_emails_show_indian_formatted_amounts(self):
        order = self.make_order()
        customer, owner = emails.build_paid_emails(order, "owner@example.com")
        for message in (customer, owner):
            self.assertIn("₹1,24,999", message.body)
            self.assertIn("₹1,24,999", self.html(message))
        self.assertIn(order.receipt_number, self.html(customer))
        self.assertIn(reverse("orders:receipt", args=[order.public_token]), self.html(customer))
        self.assertIn(reverse("admin:orders_order_change", args=[order.pk]), self.html(owner))
        self.assertEqual(customer.to, ["asha@example.com"])
        self.assertEqual(owner.reply_to, ["asha@example.com"])

    def test_delivered_email_has_link_button_only_when_a_link_exists(self):
        order = self.make_order(delivery_link="https://drive.google.com/file/abc", delivery_note="Read me first")
        message = emails.build_delivered_email(order, "owner@example.com")
        self.assertIn("https://drive.google.com/file/abc", self.html(message))
        self.assertIn("Read me first", message.body)
        order.delivery_link = ""
        self.assertNotIn("Open your files", self.html(emails.build_delivered_email(order, "owner@example.com")))

    def test_refund_emails(self):
        order = self.make_order()
        request = RefundRequest.objects.create(order=order, reference=order.reference, email=order.customer_email, reason="UNIQUE-REASON text")
        owner, ack = emails.build_refund_request_emails(request, "owner@example.com")
        self.assertIn("UNIQUE-REASON", self.html(owner))
        for content in (ack.body, self.html(ack)):
            self.assertNotIn("UNIQUE-REASON", content)
        refund = Refund.objects.create(order=order, amount=Decimal("500"), razorpay_refund_id="rfnd_1")
        processed = emails.build_refund_processed_email(refund, "owner@example.com")
        self.assertIn("rfnd_1", self.html(processed))


@override_settings(PUBLIC_CONTACT_EMAIL="owner@example.com", SITE_URL="https://example.com")
class EmailPreviewTests(TestCase):
    def setUp(self):
        self.staff = get_user_model().objects.create_superuser("boss", "boss@example.com", "pw")

    def test_visitors_cannot_open_the_preview(self):
        response = self.client.get(reverse("admin:email_preview"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response["Location"])

    def test_staff_see_the_list_and_each_preview(self):
        force_login_verified(self.client, self.staff)
        Lead.objects.create(name="Asha", email="asha@example.com", phone="9876543210", message="Hello there, long enough.")
        index = self.client.get(reverse("admin:email_preview"))
        self.assertContains(index, "Enquiry: email to you")

        html = self.client.get(reverse("admin:email_preview_detail", args=["enquiry-owner"]))
        self.assertContains(html, "New enquiry")
        text = self.client.get(reverse("admin:email_preview_detail", args=["enquiry-owner"]) + "?format=text")
        self.assertEqual(text["Content-Type"], "text/plain; charset=utf-8")

    def test_empty_kind_and_unknown_key(self):
        force_login_verified(self.client, self.staff)
        empty = self.client.get(reverse("admin:email_preview_detail", args=["order-overdue"]))
        self.assertContains(empty, "nothing to preview")
        self.assertEqual(self.client.get(reverse("admin:email_preview_detail", args=["nope"])).status_code, 404)
