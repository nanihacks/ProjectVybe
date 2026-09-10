from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .admin import LeadAdmin
from .models import Lead


class LeadAdminTests(TestCase):
    def test_lead_is_registered_with_business_focused_admin_configuration(self):
        lead_admin = admin.site._registry[Lead]

        self.assertIsInstance(lead_admin, LeadAdmin)
        self.assertEqual(
            lead_admin.search_fields,
            ("name", "email", "phone", "project__title"),
        )
        self.assertIn("status", lead_admin.list_filter)
        self.assertIn("project", lead_admin.list_filter)
        self.assertEqual(lead_admin.list_editable, ("status",))

    def test_lead_status_choices_are_available(self):
        self.assertEqual(
            Lead.Status.values,
            ["new", "contacted", "in_progress", "completed", "closed"],
        )


class LeadAdminWorkflowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.lead = Lead.objects.create(
            name="Admin Lead",
            email="admin-lead@example.com",
            message="An enquiry visible in admin.",
        )
        user_model = get_user_model()
        cls.admin_user = user_model.objects.create_superuser(
            username="lead-admin",
            email="lead-admin@example.com",
            password="test-admin-password",
        )

    def setUp(self):
        self.client.force_login(self.admin_user)

    def test_authenticated_admin_can_search_leads(self):
        response = self.client.get(
            reverse("admin:leads_lead_changelist"),
            {"q": "admin-lead@example.com"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.lead.email)

    def test_lead_admin_requires_authentication(self):
        self.client.logout()

        response = self.client.get(reverse("admin:leads_lead_changelist"))

        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response["Location"])
