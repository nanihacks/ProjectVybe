from django.core import mail
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from catalog.models import Category, Project, ProjectAddon, Service

from .models import Lead


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
            "website": "",
        }

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
        DEFAULT_FROM_EMAIL="no-reply@example.com",
    )
    def test_valid_submission_saves_lead_and_renders_inline_success(self):
        data = self.valid_post_data()
        data.update({"project": "", "selected_services": [], "selected_addons": []})
        response = self.client.post(
            self.enquiry_url(),
            data,
            secure=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "pages/enquiry.html")
        self.assertContains(response, "We've received your enquiry.")
        self.assertNotContains(response, "wa.me")
        self.assertContains(response, "Explore projects")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["owner@example.com"])
        self.assertNotIn("Project:", mail.outbox[0].body)
        self.assertNotIn("Project add-ons:", mail.outbox[0].body)
        lead = Lead.objects.get()
        self.assertEqual(lead.name, "Enquiry Visitor")
        self.assertEqual(lead.email, "visitor@example.com")
        self.assertEqual(lead.phone, "+91 98765 43210")
        self.assertIsNone(lead.project)
        self.assertEqual(list(lead.selected_services.all()), [])
        self.assertEqual(list(lead.selected_addons.all()), [])
        self.assertEqual(lead.message, "I would like to discuss this project.")
        self.assertEqual(lead.status, Lead.Status.NEW)

    @override_settings(
        WHATSAPP_NUMBER="919876543210",
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        PUBLIC_CONTACT_EMAIL="owner@example.com",
        DEFAULT_FROM_EMAIL="no-reply@example.com",
    )
    def test_project_wizard_saves_lead_and_offers_whatsapp_with_all_context(self):
        data = self.valid_post_data()
        data["project_wizard"] = "1"

        response = self.client.post(self.enquiry_url(), data, secure=True)

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].startswith("https://wa.me/919876543210?"))
        self.assertIn("Email%3A+visitor%40example.com", response["Location"])
        self.assertIn("Phone%3A+%2B91+98765+43210", response["Location"])
        self.assertIn("Additional+services%3A", response["Location"])
        self.assertIn("Documentation+add-on", response["Location"])
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(Lead.objects.count(), 1)

    def test_general_enquiry_can_omit_project_phone_and_services(self):
        data = self.valid_post_data()
        data.update(
            {
                "phone": "",
                "project": "",
                "selected_services": [],
                "selected_addons": [],
            }
        )

        response = self.client.post(self.enquiry_url(), data, secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "We've received your enquiry.")
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

    @override_settings(WHATSAPP_NUMBER="919876543210")
    def test_general_success_does_not_offer_whatsapp_context(self):
        data = self.valid_post_data()
        data.update({"project": "", "selected_services": [], "selected_addons": []})
        response = self.client.post(
            self.enquiry_url(),
            data,
            secure=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "pages/enquiry.html")
        self.assertContains(response, "Thank you")
        self.assertNotContains(response, "Continue on WhatsApp")
        self.assertNotContains(response, "wa.me/919876543210")
        self.assertEqual(Lead.objects.count(), 1)

    @override_settings(WHATSAPP_NUMBER="")
    def test_missing_whatsapp_configuration_keeps_success_flow_usable(self):
        response = self.client.post(
            self.enquiry_url(),
            self.valid_post_data(),
            secure=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "wa.me")
        self.assertContains(response, "Explore projects")

    def test_csrf_is_required_for_form_submission(self):
        csrf_client = Client(enforce_csrf_checks=True)

        response = csrf_client.post(
            self.enquiry_url(),
            self.valid_post_data(),
            secure=True,
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(Lead.objects.count(), 0)
