import csv
import io
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from catalog.models import Service
from core.testing import force_login_verified

from .models import ConsentRecord, Lead, PrivacyRequest
from .privacy import anonymise_leads, build_leads_csv, leads_past_retention


MAIL = {
    "EMAIL_BACKEND": "django.core.mail.backends.locmem.EmailBackend",
    "PUBLIC_CONTACT_EMAIL": "owner@example.com",
    "DEFAULT_FROM_EMAIL": "ProjectVybe <no-reply@example.com>",
}


def make_lead(name="Asha", email="asha@example.com", **fields):
    lead = Lead.objects.create(
        name=name, email=email, phone="+91 98765 43210", message="I want a project.", **fields
    )
    ConsentRecord.objects.create(
        lead=lead,
        contact_consent=True,
        age_confirmed=True,
        marketing_opt_in=True,
        privacy_policy_version="v1 (2026-10-18)",
        consent_text="text",
    )
    return lead


def age_lead(lead, days):
    Lead.objects.filter(pk=lead.pk).update(created_at=timezone.now() - timedelta(days=days))


@override_settings(**MAIL)
class PrivacyRequestFormTests(TestCase):
    def setUp(self):
        cache.clear()

    def post(self, **extra):
        data = {
            "kind": "delete",
            "email": "asha@example.com",
            "reference": "",
            "message": "Please remove my details.",
            "website": "",
        }
        data.update(extra)
        return self.client.post(reverse("pages:privacy_request"), data, secure=True)

    def test_form_page_lists_every_kind_of_request(self):
        response = self.client.get(reverse("pages:privacy_request"), secure=True)

        self.assertEqual(response.status_code, 200)
        for label in (
            "Withdraw my consent",
            "Stop sending me updates",
            "Send me a copy of my information",
            "Correct my information",
            "Delete my information",
        ):
            self.assertContains(response, label)
        self.assertContains(response, 'content="noindex')

    def test_privacy_request_is_linked_from_the_footer(self):
        response = self.client.get("/", secure=True)

        self.assertContains(response, f'href="{reverse("pages:privacy_request")}"')

    def test_valid_request_is_saved_and_redirects_to_a_confirmation_page(self):
        response = self.post()

        self.assertRedirects(
            response, reverse("pages:privacy_request_received"), fetch_redirect_response=False
        )
        saved = PrivacyRequest.objects.get()
        self.assertEqual(saved.kind, "delete")
        self.assertEqual(saved.status, PrivacyRequest.Status.OPEN)
        self.assertEqual(saved.request_number, f"PR-{saved.pk + 1000}")

    def test_confirmation_page_shows_the_number_and_survives_a_refresh(self):
        self.post()
        saved = PrivacyRequest.objects.get()

        for _ in range(2):
            response = self.client.get(reverse("pages:privacy_request_received"), secure=True)
            self.assertContains(response, saved.request_number)

    def test_confirmation_page_without_a_request_goes_back_to_the_form(self):
        response = self.client.get(reverse("pages:privacy_request_received"), secure=True)

        self.assertRedirects(response, reverse("pages:privacy_request"), fetch_redirect_response=False)

    def test_owner_is_told_and_the_requester_gets_a_fixed_acknowledgement(self):
        self.post(message="Secret detail http://evil.example please echo this")

        owner, acknowledgement = mail.outbox
        saved = PrivacyRequest.objects.get()
        self.assertEqual(owner.to, ["owner@example.com"])
        self.assertEqual(owner.reply_to, ["asha@example.com"])
        self.assertIn(saved.request_number, owner.subject)
        self.assertIn("Secret detail", owner.body)
        self.assertEqual(acknowledgement.to, ["asha@example.com"])
        self.assertIn(saved.request_number, acknowledgement.subject)
        self.assertNotIn("evil.example", acknowledgement.body)
        self.assertNotIn("Secret detail", acknowledgement.body)

    def test_reference_must_look_like_a_reference(self):
        response = self.post(reference="not-a-reference")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Enter a reference like PV-1042")
        self.assertEqual(PrivacyRequest.objects.count(), 0)

    def test_reference_is_normalised(self):
        self.post(reference=" pv-1042 ")

        self.assertEqual(PrivacyRequest.objects.get().reference, "PV-1042")

    def test_a_choice_and_valid_email_are_required(self):
        response = self.post(kind="", email="nope")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Please choose one option.")
        self.assertContains(response, "Enter a valid email address")
        self.assertEqual(PrivacyRequest.objects.count(), 0)

    def test_honeypot_blocks_bots(self):
        response = self.post(website="https://bot.example")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(PrivacyRequest.objects.count(), 0)

    def test_requests_are_rate_limited_per_ip(self):
        for _ in range(5):
            self.assertEqual(self.post().status_code, 302)

        blocked = self.post()

        self.assertEqual(blocked.status_code, 429)
        self.assertEqual(PrivacyRequest.objects.count(), 5)

    @override_settings(TURNSTILE_SITE_KEY="site", TURNSTILE_SECRET_KEY="secret")
    def test_turnstile_is_enforced_when_configured(self):
        response = self.post()

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "security check")
        self.assertEqual(PrivacyRequest.objects.count(), 0)


class AnonymiseTests(TestCase):
    def test_personal_details_are_removed_but_the_record_remains(self):
        lead = make_lead()
        lead.selected_services.add(
            Service.objects.create(
                name="Svc", slug="svc", short_description="s", description="d", is_active=True
            )
        )

        changed = anonymise_leads(Lead.objects.filter(pk=lead.pk))

        lead.refresh_from_db()
        self.assertEqual(changed, 1)
        self.assertEqual(lead.name, "Anonymised")
        self.assertEqual(lead.email, f"anonymised-{lead.pk}@example.invalid")
        self.assertEqual(lead.phone, "")
        self.assertEqual(lead.message, "[removed]")
        self.assertIsNotNone(lead.anonymised_at)
        self.assertEqual(lead.selected_services.count(), 0)
        self.assertTrue(lead.reference)
        self.assertIsNotNone(lead.consent.withdrawn_at)

    def test_already_anonymised_enquiries_are_skipped(self):
        lead = make_lead()
        anonymise_leads(Lead.objects.filter(pk=lead.pk))

        self.assertEqual(anonymise_leads(Lead.objects.filter(pk=lead.pk)), 0)

    def test_only_the_selected_enquiries_change(self):
        target = make_lead("Target", "target@example.com")
        other = make_lead("Other", "other@example.com")

        anonymise_leads(Lead.objects.filter(pk=target.pk))

        other.refresh_from_db()
        self.assertEqual(other.name, "Other")
        self.assertIsNone(other.anonymised_at)


class CsvExportTests(TestCase):
    def rows(self, queryset):
        return list(csv.DictReader(io.StringIO(build_leads_csv(queryset))))

    def test_export_contains_the_enquiry_and_its_consent(self):
        lead = make_lead()

        (row,) = self.rows(Lead.objects.filter(pk=lead.pk))

        self.assertEqual(row["reference"], lead.reference)
        self.assertEqual(row["name"], "Asha")
        self.assertEqual(row["email"], "asha@example.com")
        self.assertEqual(row["message"], "I want a project.")
        self.assertEqual(row["agreed_to_contact"], "yes")
        self.assertEqual(row["marketing_updates"], "yes")
        self.assertEqual(row["privacy_policy_version"], "v1 (2026-10-18)")

    def test_cells_that_look_like_formulas_are_neutralised(self):
        lead = make_lead(name='=HYPERLINK("http://evil.example","x")')

        (row,) = self.rows(Lead.objects.filter(pk=lead.pk))

        self.assertTrue(row["name"].startswith("'="))


class RetentionTests(TestCase):
    def setUp(self):
        self.old = make_lead("Old", "old@example.com")
        self.recent = make_lead("Recent", "recent@example.com")
        age_lead(self.old, 24 * 31)
        age_lead(self.recent, 24 * 29)

    def test_only_enquiries_older_than_the_period_are_due(self):
        self.assertEqual(list(leads_past_retention(24)), [self.old])

    def test_dry_run_changes_nothing(self):
        output = io.StringIO()

        call_command("anonymise_old_leads", "--dry-run", stdout=output)

        self.old.refresh_from_db()
        self.assertEqual(self.old.name, "Old")
        self.assertIn("1 enquiries are older than 24 months", output.getvalue())

    def test_real_run_anonymises_only_old_enquiries(self):
        output = io.StringIO()

        call_command("anonymise_old_leads", stdout=output)

        self.old.refresh_from_db()
        self.recent.refresh_from_db()
        self.assertEqual(self.old.name, "Anonymised")
        self.assertEqual(self.recent.name, "Recent")
        self.assertIn("Anonymised 1 enquiries", output.getvalue())

    def test_months_can_be_changed(self):
        call_command("anonymise_old_leads", "--months", "12", stdout=io.StringIO())

        self.recent.refresh_from_db()
        self.assertEqual(self.recent.name, "Anonymised")

    def test_a_nonsense_period_is_refused(self):
        with self.assertRaises(CommandError):
            call_command("anonymise_old_leads", "--months", "0", stdout=io.StringIO())

        self.old.refresh_from_db()
        self.assertEqual(self.old.name, "Old")

    def test_running_it_twice_is_harmless(self):
        call_command("anonymise_old_leads", stdout=io.StringIO())
        output = io.StringIO()

        call_command("anonymise_old_leads", stdout=output)

        self.assertIn("Anonymised 0 enquiries", output.getvalue())


class PrivacyAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = get_user_model().objects.create_superuser(
            username="privacy-admin", email="p@example.com", password="a-long-test-password-123"
        )

    def setUp(self):
        force_login_verified(self.client, self.staff)
        self.lead = make_lead()
        self.request = PrivacyRequest.objects.create(
            kind="delete", email="ASHA@example.com", reference=self.lead.reference
        )

    def test_request_page_lists_matching_enquiries_by_email_and_reference(self):
        other = make_lead("Asha Again", "asha@example.com")
        by_reference_only = make_lead("Different", "different@example.com")
        self.request.reference = by_reference_only.reference
        self.request.save()

        response = self.client.get(
            reverse("admin:leads_privacyrequest_change", args=[self.request.pk]), secure=True
        )

        self.assertContains(response, self.lead.reference)
        self.assertContains(response, other.reference)
        self.assertContains(response, by_reference_only.reference)

    def test_requests_cannot_be_added_by_hand(self):
        response = self.client.get(reverse("admin:leads_privacyrequest_add"), secure=True)

        self.assertEqual(response.status_code, 403)

    def test_closing_a_request_records_who_and_when(self):
        url = reverse("admin:leads_privacyrequest_change", args=[self.request.pk])

        self.client.post(url, {"status": "done", "staff_note": "Deleted on request."}, secure=True)

        self.request.refresh_from_db()
        self.assertEqual(self.request.status, "done")
        self.assertEqual(self.request.handled_by, self.staff)
        self.assertIsNotNone(self.request.handled_at)
        self.assertEqual(self.request.staff_note, "Deleted on request.")

    def test_mark_done_action(self):
        self.client.post(
            reverse("admin:leads_privacyrequest_changelist"),
            {"action": "mark_requests_done", "_selected_action": [self.request.pk]},
            secure=True,
        )

        self.request.refresh_from_db()
        self.assertEqual(self.request.status, "done")

    def test_export_action_returns_a_csv_download(self):
        response = self.client.post(
            reverse("admin:leads_lead_changelist"),
            {"action": "export_csv", "_selected_action": [self.lead.pk]},
            secure=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
        self.assertIn("attachment; filename=", response["Content-Disposition"])
        self.assertIn(self.lead.reference, response.content.decode())

    def test_anonymise_action_asks_for_confirmation_before_changing_anything(self):
        response = self.client.post(
            reverse("admin:leads_lead_changelist"),
            {"action": "anonymise_selected", "_selected_action": [self.lead.pk]},
            secure=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This cannot be undone")
        self.assertContains(response, self.lead.reference)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.name, "Asha")

    def test_confirming_the_anonymise_action_removes_the_details(self):
        response = self.client.post(
            reverse("admin:leads_lead_changelist"),
            {
                "action": "anonymise_selected",
                "_selected_action": [self.lead.pk],
                "confirm": "yes",
                "post": "yes",
            },
            secure=True,
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.name, "Anonymised")
        self.assertIsNotNone(self.lead.anonymised_at)
