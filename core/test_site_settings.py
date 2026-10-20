from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from leads.models import Lead

from .models import SiteSettings
from .site import contact_email, whatsapp_number
from .testing import force_login_verified


def update_settings(**fields):
    SiteSettings.objects.filter(pk=1).update(**fields)


class SiteSettingsDefaultsTests(TestCase):
    def test_a_single_row_exists_after_migrating(self):
        self.assertEqual(SiteSettings.objects.count(), 1)
        self.assertEqual(SiteSettings.get_solo().pk, 1)

    def test_defaults_match_the_current_site_copy(self):
        home = self.client.get("/", secure=True)

        self.assertContains(home, "Build. Learn. Grow.")
        self.assertContains(home, "Practical technology projects, training, mentorship")
        self.assertContains(home, "Explore projects")
        self.assertContains(home, "Our services")
        self.assertContains(home, f'href="{reverse("pages:home")}#projects"')
        self.assertContains(home, "A technology-focused space for thoughtful software projects")
        self.assertNotContains(home, "announcement-bar")

    def test_there_can_only_be_one_settings_row(self):
        second = SiteSettings(footer_tagline="Another")
        second.save()

        self.assertEqual(SiteSettings.objects.count(), 1)


class ContactFallbackTests(TestCase):
    @override_settings(PUBLIC_CONTACT_EMAIL="env@example.com", WHATSAPP_NUMBER="911111111111")
    def test_blank_admin_values_fall_back_to_the_server_settings(self):
        self.assertEqual(contact_email(), "env@example.com")
        self.assertEqual(whatsapp_number(), "911111111111")

    @override_settings(PUBLIC_CONTACT_EMAIL="env@example.com", WHATSAPP_NUMBER="911111111111")
    def test_admin_values_win_over_the_server_settings(self):
        update_settings(contact_email="admin@example.com", whatsapp_number="922222222222")

        self.assertEqual(contact_email(), "admin@example.com")
        self.assertEqual(whatsapp_number(), "922222222222")

    @override_settings(PUBLIC_CONTACT_EMAIL="env@example.com")
    def test_a_database_error_falls_back_to_the_server_settings(self):
        with patch("core.site.get_site_settings", side_effect=RuntimeError("db down")):
            self.assertEqual(contact_email(), "env@example.com")

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        PUBLIC_CONTACT_EMAIL="env@example.com",
        DEFAULT_FROM_EMAIL="no-reply@example.com",
    )
    def test_enquiry_emails_go_to_the_address_set_in_admin(self):
        cache.clear()
        update_settings(contact_email="new-inbox@example.com")

        self.client.post(
            reverse("leads:enquiry"),
            {
                "name": "Visitor",
                "email": "visitor@example.com",
                "message": "I would like to talk about a project.",
                "consent_contact": "on",
                "consent_age": "on",
            },
            secure=True,
        )

        self.assertEqual(Lead.objects.count(), 1)
        self.assertEqual(mail.outbox[0].to, ["new-inbox@example.com"])
        self.assertEqual(mail.outbox[1].reply_to, ["new-inbox@example.com"])

    @override_settings(WHATSAPP_NUMBER="919876543210")
    def test_success_page_whatsapp_button_can_be_switched_off(self):
        cache.clear()
        data = {
            "name": "Visitor",
            "email": "visitor@example.com",
            "message": "I would like to talk about a project.",
            "consent_contact": "on",
            "consent_age": "on",
        }
        self.client.post(reverse("leads:enquiry"), data, secure=True)
        self.assertContains(self.client.get(reverse("leads:success"), secure=True), "Open WhatsApp")

        update_settings(show_whatsapp_button=False)

        self.assertNotContains(self.client.get(reverse("leads:success"), secure=True), "Open WhatsApp")

    def test_success_page_shows_the_reply_time_promise(self):
        cache.clear()
        update_settings(reply_time_promise="We reply within 3 hours on weekdays.")
        self.client.post(
            reverse("leads:enquiry"),
            {
                "name": "Visitor",
                "email": "visitor@example.com",
                "message": "I would like to talk about a project.",
                "consent_contact": "on",
                "consent_age": "on",
            },
            secure=True,
        )

        self.assertContains(
            self.client.get(reverse("leads:success"), secure=True),
            "We reply within 3 hours on weekdays.",
        )


class HomepageSettingsTests(TestCase):
    def test_hero_text_and_buttons_come_from_settings(self):
        update_settings(
            hero_eyebrow="New batch",
            hero_heading="Learn by building",
            hero_text="Join our next cohort.",
            hero_primary_label="See courses",
            hero_primary_url="/services/",
            hero_secondary_label="Talk to us",
            hero_secondary_url="/enquiry/",
            hero_note="",
        )

        home = self.client.get("/", secure=True)

        self.assertContains(home, "Learn by building")
        self.assertContains(home, "Join our next cohort.")
        self.assertContains(home, 'href="/services/">See courses')
        self.assertContains(home, 'href="/enquiry/">Talk to us</a>')
        self.assertNotContains(home, "hero__note")

    def test_hero_text_is_escaped(self):
        update_settings(hero_heading="<script>alert(1)</script>")

        home = self.client.get("/", secure=True)

        self.assertNotContains(home, "<script>alert(1)</script>")
        self.assertContains(home, "&lt;script&gt;alert(1)&lt;/script&gt;")

    def test_sections_can_be_hidden_individually(self):
        sections = {
            "show_categories_section": 'aria-labelledby="categories-title"',
            "show_featured_section": 'aria-labelledby="featured-title"',
            "show_services_section": 'aria-labelledby="services-title"',
            "show_process_section": 'aria-labelledby="process-title"',
            "show_value_section": 'aria-labelledby="value-title"',
        }
        home = self.client.get("/", secure=True)
        for marker in sections.values():
            self.assertContains(home, marker)

        for flag, marker in sections.items():
            update_settings(**{flag: False})
            self.assertNotContains(self.client.get("/", secure=True), marker, msg_prefix=flag)
            update_settings(**{flag: True})

    def test_hero_link_skips_the_missing_anchor_when_categories_are_hidden(self):
        update_settings(show_categories_section=False)

        home = self.client.get("/", secure=True)

        self.assertNotContains(home, f'href="{reverse("pages:home")}#projects"')
        self.assertContains(home, f'href="{reverse("pages:project_catalogue")}"')


class AnnouncementBarTests(TestCase):
    def test_bar_shows_text_and_link_when_enabled(self):
        update_settings(
            announcement_enabled=True,
            announcement_text="Admissions open for November",
            announcement_link_url="/enquiry/",
            announcement_link_label="Apply",
        )

        home = self.client.get("/", secure=True)

        self.assertContains(home, "Admissions open for November")
        self.assertContains(home, 'href="/enquiry/">Apply</a>')
        self.assertContains(home, "data-announcement-close")

    def test_bar_is_hidden_when_switched_off_or_empty(self):
        update_settings(announcement_enabled=False, announcement_text="Hidden text")
        self.assertNotContains(self.client.get("/", secure=True), "Hidden text")

        update_settings(announcement_enabled=True, announcement_text="  ")
        self.assertNotContains(self.client.get("/", secure=True), "announcement-bar")

    def test_bar_disappears_after_its_end_time(self):
        update_settings(
            announcement_enabled=True,
            announcement_text="Ends soon",
            announcement_ends_at=timezone.now() - timedelta(minutes=1),
        )
        self.assertNotContains(self.client.get("/", secure=True), "Ends soon")

        update_settings(announcement_ends_at=timezone.now() + timedelta(hours=1))
        self.assertContains(self.client.get("/", secure=True), "Ends soon")

    def test_bar_text_is_escaped(self):
        update_settings(announcement_enabled=True, announcement_text="<b>Big</b> news")

        self.assertNotContains(self.client.get("/", secure=True), "<b>Big</b>")


class FooterAndBrandTests(TestCase):
    def test_footer_shows_business_details_and_social_links(self):
        update_settings(
            footer_tagline="Make things.",
            legal_name="ProjectVybe Labs LLP",
            gstin="22AAAAA0000A1Z5",
            phone="+91 98765 43210",
            address="12 Example Street\nHyderabad",
            business_hours="Mon-Sat 10am-6pm",
            instagram_url="https://instagram.com/projectvybe",
            github_url="https://github.com/projectvybe",
            linkedin_url="",
        )

        home = self.client.get("/", secure=True)

        self.assertContains(home, "Make things.")
        self.assertContains(home, "ProjectVybe Labs LLP")
        self.assertContains(home, "GSTIN 22AAAAA0000A1Z5")
        self.assertContains(home, 'href="tel:+919876543210"')
        self.assertContains(home, "12 Example Street<br>Hyderabad")
        self.assertContains(home, "Mon-Sat 10am-6pm")
        self.assertContains(home, 'href="https://instagram.com/projectvybe"')
        self.assertContains(home, 'href="https://github.com/projectvybe"')
        self.assertNotContains(home, "LinkedIn")

    def test_gstin_is_not_shown_until_set(self):
        self.assertNotContains(self.client.get("/", secure=True), "GSTIN")

    def test_default_share_image_is_used_when_a_page_has_none(self):
        with patch(
            "core.context_processors.cloudinary_url",
            return_value="https://res.cloudinary.com/demo/share.jpg",
        ):
            home = self.client.get("/", secure=True)

        self.assertContains(home, '<meta property="og:image" content="https://res.cloudinary.com/demo/share.jpg">')
        self.assertContains(home, 'content="summary_large_image"')

    def test_no_share_image_means_no_og_image_tag(self):
        home = self.client.get("/", secure=True)

        self.assertNotContains(home, 'property="og:image"')
        self.assertContains(home, 'content="summary"')


class SiteSettingsAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin_user = get_user_model().objects.create_superuser(
            username="settings-admin", email="s@example.com", password="a-long-test-password-123"
        )

    def test_staff_can_open_the_settings_page_with_all_groups(self):
        force_login_verified(self.client, self.admin_user)

        response = self.client.get(reverse("admin:core_sitesettings_changelist"), secure=True, follow=True)

        self.assertEqual(response.status_code, 200)
        for heading in ("Contact", "Business details", "Announcement bar", "Homepage", "Maintenance mode"):
            self.assertContains(response, heading)

    def test_anonymous_visitors_are_sent_to_the_login_page(self):
        response = self.client.get(reverse("admin:core_sitesettings_changelist"), secure=True)

        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response["Location"])
