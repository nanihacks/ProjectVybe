from django.http import Http404, HttpResponse
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html, format_html_join
from django_otp.admin import OTPAdminSite


class ProjectVybeAdminSite(OTPAdminSite):
    """Admin that only lets staff in after they pass a one-time-password check."""

    site_header = "ProjectVybe Admin"
    site_title = "ProjectVybe Admin"
    index_title = "Manage ProjectVybe"

    # Keep the standard "admin" namespace so reverse("admin:...") keeps working.
    def __init__(self, name="admin"):
        super().__init__(name)

    def get_urls(self):
        return [
            path("email-preview/", self.admin_view(self.email_preview_index), name="email_preview"),
            path("email-preview/<slug:key>/", self.admin_view(self.email_preview), name="email_preview_detail"),
        ] + super().get_urls()

    def _email_samples(self):
        """{key: (label, builder)} using the newest real record of each kind (nothing is sent)."""
        from leads.models import Lead
        from leads.utils import _confirmation_message, _owner_message
        from orders import emails
        from orders.models import Order, Refund, RefundRequest

        owner = "owner@example.com"

        def newest(model, **filters):
            return model.objects.filter(**filters).order_by("-pk").first()

        def order_message(build, **filters):
            def make():
                order = newest(Order, **filters)
                return build(order) if order else None

            return make

        def lead_message(build):
            def make():
                lead = newest(Lead)
                return build(lead, owner) if lead else None

            return make

        def refund_request_messages():
            request = newest(RefundRequest)
            return emails.build_refund_request_emails(request, owner) if request else None

        def refund_processed():
            refund = newest(Refund)
            return emails.build_refund_processed_email(refund, owner) if refund else None

        paid = {"status__in": Order.PAID_STATUSES}
        return {
            "enquiry-owner": ("Enquiry: email to you", lead_message(_owner_message)),
            "enquiry-confirmation": ("Enquiry: email to the visitor", lead_message(_confirmation_message)),
            "order-paid-customer": (
                "Payment: email to the customer",
                order_message(lambda o: emails.build_paid_emails(o, owner)[0], **paid),
            ),
            "order-paid-owner": (
                "Payment: email to you",
                order_message(lambda o: emails.build_paid_emails(o, owner)[1], **paid),
            ),
            "order-delivered": (
                "Delivered: email to the customer",
                order_message(lambda o: emails.build_delivered_email(o, owner), **paid),
            ),
            "order-overdue": (
                "Overdue: email to you",
                order_message(lambda o: emails.build_overdue_email(o, owner), **paid),
            ),
            "refund-request-owner": (
                "Refund request: email to you",
                lambda: (refund_request_messages() or [None])[0],
            ),
            "refund-request-ack": (
                "Refund request: email to the customer",
                lambda: (refund_request_messages() or [None, None])[-1],
            ),
            "refund-processed": ("Refund processed: email to the customer", refund_processed),
        }

    # Previews show real customer data, so each needs view permission on the model it draws from.
    PREVIEW_PERMS = {
        "enquiry-owner": "leads.view_lead",
        "enquiry-confirmation": "leads.view_lead",
        "order-paid-customer": "orders.view_order",
        "order-paid-owner": "orders.view_order",
        "order-delivered": "orders.view_order",
        "order-overdue": "orders.view_order",
        "refund-request-owner": "orders.view_refundrequest",
        "refund-request-ack": "orders.view_refundrequest",
        "refund-processed": "orders.view_order",
    }

    def _allowed_samples(self, request):
        return {
            key: value
            for key, value in self._email_samples().items()
            if request.user.has_perm(self.PREVIEW_PERMS.get(key, ""))
        }

    def email_preview_index(self, request):
        samples = self._allowed_samples(request)
        rows = format_html_join(
            "",
            '<li><a href="{}">{}</a> (<a href="{}?format=text">plain text</a>)</li>',
            (
                (
                    reverse("admin:email_preview_detail", args=[key]),
                    label,
                    reverse("admin:email_preview_detail", args=[key]),
                )
                for key, (label, _) in samples.items()
            ),
        )
        context = {
            **self.each_context(request),
            "title": "Email preview",
            "content": format_html(
                "<p>Shows how each email looks, using your newest real enquiry, order or refund request. "
                "Nothing is sent. An email with no matching record yet shows a note instead.</p><ul>{}</ul>",
                rows,
            ),
        }
        return TemplateResponse(request, "admin/email_preview.html", context)

    def email_preview(self, request, key):
        samples = self._allowed_samples(request)
        if key not in samples:
            raise Http404
        message = samples[key][1]()
        if message is None:
            return HttpResponse("No record of this kind exists yet, so there is nothing to preview.", status=200)
        if request.GET.get("format") == "text":
            return HttpResponse(message.body, content_type="text/plain; charset=utf-8")
        html = message.alternatives[0][0]
        return HttpResponse(html, content_type="text/html; charset=utf-8")
