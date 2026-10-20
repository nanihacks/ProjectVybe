from unittest.mock import patch

from django.conf import settings
from django.core import mail
from django.core.cache import cache
from django.core.mail import EmailMessage
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from catalog.models import Category, Project, ProjectAddon, Service

from legal.models import LegalPage

from .models import ConsentRecord, Lead


class LeadModelTests(TestCase):
    def setUp(self):
        category = Category.objects.create(name="Web Development", slug="web-development")
        self.project = Project.objects.create(
            title="Web Project",
            slug="web-project",
            short_description="A web project.",
            description="Web project details.",
            category=category,
        )
        self.service = Service.objects.create(
            name="Documentation",
            slug="documentation",
            short_description="Documentation support.",
            description="Documentation service details.",
        )
        self.addon = ProjectAddon.objects.create(
            name="Documentation support",
            slug="lead-test-documentation",
            description="Project documentation support.",
        )

    def test_lead_creation_defaults_to_new_and_can_select_services(self):
        lead = Lead.objects.create(
            project=self.project,
            name="Test Visitor",
            email="visitor@example.com",
            phone="+910000000000",
            message="I would like more information.",
        )
        lead.selected_services.add(self.service)
        lead.selected_addons.add(self.addon)

        self.assertEqual(lead.status, Lead.Status.NEW)
        self.assertEqual(list(lead.selected_services.all()), [self.service])
        self.assertEqual(list(lead.selected_addons.all()), [self.addon])
        self.assertEqual(str(lead), "Test Visitor - visitor@example.com")

    def test_lead_project_is_optional_and_phone_can_be_blank(self):
        lead = Lead.objects.create(
            name="General Enquiry",
            email="general@example.com",
            message="I have a general question.",
        )

        self.assertIsNone(lead.project)
        self.assertEqual(lead.phone, "")
        self.assertEqual(lead.status, Lead.Status.NEW)


class EnquiryWorkflowTests(TestCase):
    def setUp(self):
        cache.clear()
        self.category = Category.objects.create(
            name="Enquiry Category",
            slug="enquiry-category",
        )
        self.inactive_category = Category.objects.create(
            name="Inactive Enquiry Category",
            slug="inactive-enquiry-category",
            is_active=False,
        )
        self.project = Project.objects.create(
            title="Published Enquiry Project",
            slug="published-enquiry-project",
            short_description="A published project for enquiry tests.",
            description="Project details for enquiry tests.",
            category=self.category,
            is_published=True,
        )
        self.addon = ProjectAddon.objects.create(
            name="Documentation add-on",
            slug="enquiry-documentation-addon",
            description="Documentation support for this project.",
            is_active=True,
        )
        self.project.addons.add(self.addon)
        self.inactive_addon = ProjectAddon.objects.create(
            name="Inactive add-on",
            slug="inactive-enquiry-addon",
            description="An inactive project add-on.",
            is_active=False,
        )
        self.project.addons.add(self.inactive_addon)
        self.unpublished_project = Project.objects.create(
            title="Unpublished Enquiry Project",
            slug="unpublished-enquiry-project",
            short_description="An unpublished project.",
            description="This must not be selectable.",
            category=self.category,
            is_published=False,
        )
        self.inactive_category_project = Project.objects.create(
            title="Inactive Category Project",
            slug="inactive-category-project",
            short_description="A project in an inactive category.",
            description="This must not be selectable.",
            category=self.inactive_category,
            is_published=True,
        )
        self.service = Service.objects.create(
            name="Enquiry Documentation",
            slug="enquiry-documentation",
            short_description="Documentation support.",
            description="Documentation service details.",
            is_active=True,
        )
        self.inactive_service = Service.objects.create(
            name="Inactive Enquiry Service",
            slug="inactive-enquiry-service",
            short_description="An inactive service.",
            description="Inactive service details.",
            is_active=False,
        )

    def enquiry_url(self):
        return reverse("leads:enquiry")

    def valid_post_data(self):
        return {
            "name": "Enquiry Visitor",
            "email": "visitor@example.com",
            "phone": "+91 98765 43210",
            "project": str(self.project.pk),
            "selected_services": [str(self.service.pk)],
            "selected_addons": [str(self.addon.pk)],
            "message": "I would like to discuss this project.",
            "consent_contact": "on",
            "consent_age": "on",
            "website": "",
        }

    def general_post_data(self):
        data = self.valid_post_data()
        data.update({"project": "", "selected_services": [], "selected_addons": []})
        return data

    def test_enquiry_page_renders_without_creating_a_lead(self):
        response = self.client.get(self.enquiry_url(), secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "pages/enquiry.html")
        self.assertContains(response, "Submit enquiry")
        self.assertContains(response, 'name="name"')
        self.assertContains(response, 'name="email"')
        self.assertContains(response, 'name="phone"')
        self.assertContains(response, 'name="message"')
        self.assertNotContains(response, "Company services")
        self.assertNotContains(response, "Project add-ons")
        self.assertEqual(Lead.objects.count(), 0)

    def test_project_service_and_addon_context_is_preselected_from_safe_slugs(self):
        response = self.client.get(
            self.enquiry_url(),
            {
                "project": self.project.slug,
                "service": self.service.slug,
                "addon": self.addon.slug,
            },
            secure=True,
        )

        form = response.context["form"]
        self.assertEqual(response.status_code, 200)
        self.assertEqual(form.initial["project"], self.project.pk)
        self.assertEqual(form.initial["selected_services"], [self.service.pk])
        self.assertEqual(form.initial["selected_addons"], [self.addon.pk])

        invalid_context_response = self.client.get(
            self.enquiry_url(),
            {
                "project": self.unpublished_project.slug,
                "service": self.inactive_service.slug,
                "addon": self.inactive_addon.slug,
            },
            secure=True,
        )
        self.assertIsNone(invalid_context_response.context["selected_project"])
        self.assertIsNone(invalid_context_response.context["selected_service"])
        self.assertIsNone(invalid_context_response.context["selected_addon"])

    def test_project_enquiry_uses_two_steps_and_shows_project_options(self):
        response = self.client.get(
            self.enquiry_url(),
            {"project": self.project.slug},
            secure=True,
        )

        self.assertContains(response, "Step 1 of 2")
        self.assertContains(response, "Your information")
        self.assertContains(response, "Step 2 of 2")
        self.assertContains(response, "Choose project support")
        self.assertContains(response, "Project add-ons")
        self.assertContains(response, "Continue to WhatsApp")

    @override_settings(
        WHATSAPP_NUMBER="919876543210",
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        PUBLIC_CONTACT_EMAIL="owner@example.com",
        DEFAULT_FROM_EMAIL="ProjectVybe Enquiries <no-reply@example.com>",
    )
    def test_general_submission_redirects_to_success_page_and_sends_emails(self):
        response = self.client.post(
            self.enquiry_url(), self.general_post_data(), secure=True
        )

        self.assertRedirects(
            response,
            reverse("leads:success"),
            fetch_redirect_response=False,
        )
        lead = Lead.objects.get()
        self.assertEqual(lead.reference, f"PV-{lead.pk + 1000}")
        self.assertIsNone(lead.project)
        self.assertEqual(lead.phone, "+919876543210")
        self.assertEqual(lead.message, "I would like to discuss this project.")
        self.assertEqual(lead.status, Lead.Status.NEW)

        self.assertEqual(len(mail.outbox), 2)
        owner, confirmation = mail.outbox
        self.assertEqual(owner.to, ["owner@example.com"])
        self.assertEqual(owner.reply_to, ["visitor@example.com"])
        self.assertIn(lead.reference, owner.subject)
        self.assertIn("Enquiry Visitor", owner.subject)
        self.assertIn("Enquiry Visitor via ProjectVybe", owner.from_email)
        self.assertIn("no-reply@example.com", owner.from_email)
        self.assertIn("I would like to discuss this project.", owner.body)
        self.assertEqual(confirmation.to, ["visitor@example.com"])
        self.assertEqual(confirmation.reply_to, ["owner@example.com"])
        self.assertIn(lead.reference, confirmation.subject)
        lead.refresh_from_db()
        self.assertTrue(lead.owner_notified)
        self.assertTrue(lead.confirmation_sent)

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        PUBLIC_CONTACT_EMAIL="owner@example.com",
        DEFAULT_FROM_EMAIL="no-reply@example.com",
    )
    def test_visitor_confirmation_does_not_echo_visitor_input(self):
        data = self.general_post_data()
        data["message"] = "Please send spam link http://evil.example to everyone"
        data["name"] = "Mallory"
        data["phone"] = "+91 99999 11111"

        self.client.post(self.enquiry_url(), data, secure=True)

        confirmation = mail.outbox[1]
        self.assertNotIn("evil.example", confirmation.body)
        self.assertNotIn("Mallory", confirmation.body)
        self.assertNotIn("99999", confirmation.body)

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        PUBLIC_CONTACT_EMAIL="owner@example.com",
        DEFAULT_FROM_EMAIL="no-reply@example.com",
    )
    def test_newlines_in_name_cannot_inject_email_headers(self):
        data = self.general_post_data()
        data["name"] = "Eve\r\nBcc: victim@example.com"

        self.client.post(self.enquiry_url(), data, secure=True)

        owner = mail.outbox[0]
        self.assertNotIn("\n", owner.subject)
        self.assertNotIn("\n", owner.from_email)
        self.assertEqual(owner.bcc, [])

    @override_settings(
        WHATSAPP_NUMBER="919876543210",
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        PUBLIC_CONTACT_EMAIL="owner@example.com",
        DEFAULT_FROM_EMAIL="no-reply@example.com",
    )
    def test_project_wizard_emails_owner_and_redirects_to_whatsapp_with_reference(self):
        data = self.valid_post_data()
        data["project_wizard"] = "1"

        response = self.client.post(self.enquiry_url(), data, secure=True)

        lead = Lead.objects.get()
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].startswith("https://wa.me/919876543210?"))
        self.assertIn("Email%3A+visitor%40example.com", response["Location"])
        self.assertIn("Phone%3A+%2B919876543210", response["Location"])
        self.assertIn("Additional+services%3A", response["Location"])
        self.assertIn("Documentation+add-on", response["Location"])
        self.assertIn(f"Reference%3A+{lead.reference}", response["Location"])
        self.assertEqual(len(mail.outbox), 2)
        self.assertIn("Published Enquiry Project", mail.outbox[0].subject)
        self.assertTrue(lead.owner_notified or Lead.objects.get().owner_notified)

    @override_settings(
        WHATSAPP_NUMBER="",
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        PUBLIC_CONTACT_EMAIL="owner@example.com",
    )
    def test_project_wizard_without_whatsapp_falls_back_to_success_page(self):
        data = self.valid_post_data()
        data["project_wizard"] = "1"

        response = self.client.post(self.enquiry_url(), data, secure=True)

        self.assertRedirects(
            response, reverse("leads:success"), fetch_redirect_response=False
        )
        self.assertEqual(len(mail.outbox), 2)

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        PUBLIC_CONTACT_EMAIL="owner@example.com",
        DEFAULT_FROM_EMAIL="no-reply@example.com",
    )
    def test_email_failure_is_recorded_per_message_and_lead_is_still_saved(self):
        original_send = EmailMessage.send

        def fail_for_visitor(message, fail_silently=False):
            if message.to == ["visitor@example.com"]:
                raise OSError("smtp down")
            return original_send(message, fail_silently=fail_silently)

        with patch.object(EmailMessage, "send", fail_for_visitor):
            response = self.client.post(
                self.enquiry_url(), self.general_post_data(), secure=True
            )

        self.assertEqual(response.status_code, 302)
        lead = Lead.objects.get()
        self.assertTrue(lead.owner_notified)
        self.assertFalse(lead.confirmation_sent)

    @override_settings(PUBLIC_CONTACT_EMAIL="")
    def test_missing_contact_email_still_saves_lead_without_flags(self):
        response = self.client.post(
            self.enquiry_url(), self.general_post_data(), secure=True
        )

        self.assertEqual(response.status_code, 302)
        lead = Lead.objects.get()
        self.assertFalse(lead.owner_notified)
        self.assertFalse(lead.confirmation_sent)

    @override_settings(WHATSAPP_NUMBER="919876543210")
    def test_success_page_shows_reference_survives_refresh_and_offers_whatsapp(self):
        self.client.post(self.enquiry_url(), self.general_post_data(), secure=True)
        lead = Lead.objects.get()

        first = self.client.get(reverse("leads:success"), secure=True)
        second = self.client.get(reverse("leads:success"), secure=True)

        for response in (first, second):
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, lead.reference)
            self.assertContains(response, "Open WhatsApp")
            self.assertContains(response, "Reference%3A+" + lead.reference)
            self.assertContains(response, 'content="noindex')

    def test_success_page_without_a_submission_redirects_to_form(self):
        response = self.client.get(reverse("leads:success"), secure=True)

        self.assertRedirects(
            response, self.enquiry_url(), fetch_redirect_response=False
        )

    @override_settings(WHATSAPP_NUMBER="")
    def test_success_page_without_whatsapp_has_no_whatsapp_button(self):
        self.client.post(self.enquiry_url(), self.general_post_data(), secure=True)

        response = self.client.get(reverse("leads:success"), secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Open WhatsApp")

    def test_consent_boxes_are_rendered_unticked(self):
        for url in (
            self.enquiry_url(),
            f"{self.enquiry_url()}?project={self.project.slug}",
        ):
            response = self.client.get(url, secure=True)
            self.assertContains(response, 'name="consent_contact"')
            self.assertContains(response, 'name="consent_age"')
            self.assertContains(response, 'name="consent_marketing"')
            self.assertNotContains(response, "checked")

    def test_required_consent_is_enforced_and_no_lead_is_saved_without_it(self):
        for missing in ("consent_contact", "consent_age"):
            data = self.general_post_data()
            del data[missing]

            response = self.client.post(self.enquiry_url(), data, secure=True)

            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "Please tick this box")
            self.assertContains(response, f'id="id_{missing}_error"')
            self.assertEqual(Lead.objects.count(), 0)
            self.assertEqual(ConsentRecord.objects.count(), 0)
            self.assertEqual(len(mail.outbox), 0)

    def test_valid_submission_stores_a_consent_record(self):
        data = self.general_post_data()
        data["consent_marketing"] = "on"

        self.client.post(self.enquiry_url(), data, secure=True)

        consent = Lead.objects.get().consent
        self.assertTrue(consent.contact_consent)
        self.assertTrue(consent.age_confirmed)
        self.assertTrue(consent.marketing_opt_in)
        privacy = LegalPage.objects.get(slug="privacy-policy").latest_version
        self.assertEqual(consent.privacy_policy, privacy)
        self.assertEqual(consent.privacy_policy_version, privacy.label)
        self.assertIn("Privacy Policy", consent.consent_text)
        self.assertIsNone(consent.withdrawn_at)

    def test_marketing_consent_defaults_to_not_opted_in(self):
        self.client.post(self.enquiry_url(), self.general_post_data(), secure=True)

        self.assertFalse(Lead.objects.get().consent.marketing_opt_in)

    def test_consent_error_on_project_wizard_reopens_step_one(self):
        data = self.valid_post_data()
        data["project_wizard"] = "1"
        del data["consent_contact"]

        response = self.client.post(self.enquiry_url(), data, secure=True)

        self.assertContains(response, 'data-start-step="1"')

    def test_enquiry_post_is_rate_limited_per_ip(self):
        limit = settings.ENQUIRY_RATE_LIMIT
        for _ in range(limit):
            response = self.client.post(
                self.enquiry_url(), self.general_post_data(), secure=True
            )
            self.assertEqual(response.status_code, 302)

        blocked = self.client.post(
            self.enquiry_url(), self.general_post_data(), secure=True
        )

        self.assertEqual(blocked.status_code, 429)
        self.assertContains(blocked, "Too many enquiries", status_code=429)
        self.assertEqual(Lead.objects.count(), limit)

    def test_invalid_submissions_do_not_use_up_the_rate_limit(self):
        for _ in range(settings.ENQUIRY_RATE_LIMIT + 2):
            bad = self.general_post_data()
            bad["email"] = "nope"
            self.client.post(self.enquiry_url(), bad, secure=True)

        response = self.client.post(
            self.enquiry_url(), self.general_post_data(), secure=True
        )

        self.assertEqual(response.status_code, 302)

    def test_general_enquiry_can_omit_project_phone_and_services(self):
        data = self.general_post_data()
        data["phone"] = ""

        response = self.client.post(self.enquiry_url(), data, secure=True)

        self.assertEqual(response.status_code, 302)
        lead = Lead.objects.get()
        self.assertIsNone(lead.project)
        self.assertEqual(lead.phone, "")
        self.assertEqual(list(lead.selected_services.all()), [])
        self.assertEqual(list(lead.selected_addons.all()), [])

    def test_invalid_email_and_short_message_preserve_valid_form_data(self):
        data = self.valid_post_data()
        data.update({"email": "not-an-email", "message": "Too short"})

        response = self.client.post(self.enquiry_url(), data, secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "pages/enquiry.html")
        self.assertEqual(Lead.objects.count(), 0)
        self.assertEqual(response.context["form"]["name"].value(), "Enquiry Visitor")
        self.assertContains(response, "Enter a valid email address")
        self.assertContains(response, "at least 10 characters")

    def test_invalid_fields_expose_accessible_error_references(self):
        data = self.valid_post_data()
        data.update({"email": "not-an-email", "message": "Too short"})

        response = self.client.post(self.enquiry_url(), data, secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'aria-invalid="true"')
        self.assertContains(response, 'aria-describedby="id_email_error"')
        self.assertContains(response, 'aria-describedby="id_message_error"')
        self.assertContains(response, 'id="id_email_error"')
        self.assertContains(response, 'id="id_message_error"')

    @override_settings(WHATSAPP_NUMBER="919876543210")
    def test_untrusted_input_is_encoded_before_whatsapp_rendering(self):
        data = self.valid_post_data()
        data["project_wizard"] = "1"
        data.update(
            {
                "name": '<script>alert("x")</script> & quoted',
                "message": "Unicode café\nSecond line & <tag>",
            }
        )

        response = self.client.post(self.enquiry_url(), data, secure=True)

        self.assertEqual(response.status_code, 302)
        self.assertIn("%3Cscript%3E", response["Location"])
        self.assertIn("%26", response["Location"])

    def test_unpublished_inactive_and_nonexistent_choices_are_rejected(self):
        unpublished_data = self.valid_post_data()
        unpublished_data["project"] = str(self.unpublished_project.pk)
        inactive_service_data = self.valid_post_data()
        inactive_service_data["selected_services"] = [str(self.inactive_service.pk)]
        inactive_addon_data = self.valid_post_data()
        inactive_addon_data["selected_addons"] = [str(self.inactive_addon.pk)]

        unpublished_response = self.client.post(
            self.enquiry_url(), unpublished_data, secure=True
        )
        inactive_service_response = self.client.post(
            self.enquiry_url(), inactive_service_data, secure=True
        )
        inactive_addon_response = self.client.post(
            self.enquiry_url(), inactive_addon_data, secure=True
        )

        self.assertEqual(unpublished_response.status_code, 200)
        self.assertEqual(inactive_service_response.status_code, 200)
        self.assertEqual(inactive_addon_response.status_code, 200)
        self.assertEqual(Lead.objects.count(), 0)
        self.assertContains(unpublished_response, "Select a valid choice")
        self.assertContains(inactive_service_response, "Select a valid choice")
        self.assertContains(inactive_addon_response, "Select a valid choice")

    def test_honeypot_rejects_obvious_bot_submission(self):
        data = self.valid_post_data()
        data["website"] = "https://bot.example"

        response = self.client.post(self.enquiry_url(), data, secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Lead.objects.count(), 0)
        self.assertContains(response, "This enquiry could not be submitted.")

    def test_csrf_is_required_for_form_submission(self):
        csrf_client = Client(enforce_csrf_checks=True)

        response = csrf_client.post(
            self.enquiry_url(),
            self.valid_post_data(),
            secure=True,
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(Lead.objects.count(), 0)


class LeadReferenceTests(TestCase):
    def test_reference_is_stable_and_offset_from_pk(self):
        lead = Lead.objects.create(
            name="Ref", email="ref@example.com", message="Reference test message."
        )

        self.assertEqual(lead.reference, f"PV-{lead.pk + 1000}")
        self.assertEqual(Lead().reference, "")
