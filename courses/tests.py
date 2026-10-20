import datetime
from io import StringIO

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.testing import force_login_verified
from leads.models import ConsentRecord

from .models import Course, CourseWaitlistEntry
from .privacy import anonymise_entries


@override_settings(PUBLIC_CONTACT_EMAIL="owner@example.com", DEFAULT_FROM_EMAIL="hello@example.com", SITE_URL="https://example.com")
class CourseTestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.course = Course.objects.create(
            title="Build a Web App",
            slug="build-a-web-app",
            summary="Ship your first full-stack project.",
            description="For students who want a portfolio project.",
            outline="Setting up\nDatabases\nDeploying",
            expected_launch="Early 2027",
            is_published=True,
        )

    def post_data(self, **extra):
        data = {
            "name": "Asha Rao",
            "email": "asha@example.com",
            "phone": "",
            "consent_contact": "on",
            "consent_age": "on",
            "website": "",
        }
        data.update(extra)
        return data

    def url(self):
        return reverse("courses:detail", args=[self.course.slug])


class CoursePageTests(CourseTestCase):
    def test_list_shows_published_courses_only(self):
        Course.objects.create(title="Hidden Draft", slug="hidden-draft", summary="x", is_published=False)
        response = self.client.get(reverse("courses:list"))
        self.assertContains(response, "Build a Web App")
        self.assertContains(response, "Expected: Early 2027")
        self.assertNotContains(response, "Hidden Draft")

    def test_empty_list_has_a_helpful_message(self):
        Course.objects.all().delete()
        self.assertContains(self.client.get(reverse("courses:list")), "Our first course is being planned.")

    def test_detail_shows_outline_and_json_ld(self):
        response = self.client.get(self.url())
        self.assertContains(response, "Setting up")
        self.assertContains(response, "Deploying")
        self.assertContains(response, '"@type": "Course"')
        self.assertContains(response, "Opens Early 2027")

    def test_unpublished_course_is_404(self):
        Course.objects.filter(pk=self.course.pk).update(is_published=False)
        self.assertEqual(self.client.get(self.url()).status_code, 404)

    def test_pages_are_in_navigation_and_sitemap(self):
        self.assertContains(self.client.get(reverse("pages:home")), reverse("courses:list"))
        sitemap = self.client.get("/sitemap.xml").content.decode()
        self.assertIn("/courses/", sitemap)
        self.assertIn("/courses/build-a-web-app/", sitemap)

    def test_query_budget(self):
        with self.assertNumQueries(4):
            self.client.get(reverse("courses:list"))
        with self.assertNumQueries(4):
            self.client.get(self.url())


class WaitlistTests(CourseTestCase):
    def test_sign_up_saves_entry_consent_and_sends_two_emails(self):
        response = self.client.post(self.url(), self.post_data())
        self.assertRedirects(response, self.url(), fetch_redirect_response=False)
        entry = CourseWaitlistEntry.objects.get()
        self.assertEqual(entry.course, self.course)
        consent = ConsentRecord.objects.get(waitlist_entry=entry)
        self.assertTrue(consent.contact_consent and consent.age_confirmed)
        self.assertFalse(consent.marketing_opt_in)
        self.assertIn("emailing me about this course", consent.consent_text)
        self.assertEqual(sorted(m.to[0] for m in mail.outbox), ["asha@example.com", "owner@example.com"])

    def test_confirmation_shows_after_redirect_once(self):
        self.client.post(self.url(), self.post_data())
        self.assertContains(self.client.get(self.url()), "You're on the list.")
        self.assertNotContains(self.client.get(self.url()), "You're on the list.")

    def test_visitor_email_does_not_echo_input_and_html_is_escaped_for_owner(self):
        self.client.post(self.url(), self.post_data(name="<b>Mallory</b>"))
        visitor = next(m for m in mail.outbox if m.to == ["asha@example.com"])
        owner = next(m for m in mail.outbox if m.to == ["owner@example.com"])
        self.assertNotIn("Mallory", visitor.body)
        self.assertNotIn("Mallory", visitor.alternatives[0][0])
        self.assertIn("&lt;b&gt;Mallory&lt;/b&gt;", owner.alternatives[0][0])

    def test_duplicate_sign_up_looks_like_success_but_adds_nothing(self):
        self.client.post(self.url(), self.post_data())
        mail.outbox.clear()
        response = self.client.post(self.url(), self.post_data(email="ASHA@example.com"))
        self.assertRedirects(response, self.url(), fetch_redirect_response=False)
        self.assertEqual(CourseWaitlistEntry.objects.count(), 1)
        self.assertEqual(mail.outbox, [])

    def test_consent_is_required(self):
        data = self.post_data()
        del data["consent_contact"]
        response = self.client.post(self.url(), data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Please tick this box to continue.")
        self.assertFalse(CourseWaitlistEntry.objects.exists())

    def test_honeypot_and_bad_phone_are_rejected(self):
        self.client.post(self.url(), self.post_data(website="spam"))
        self.client.post(self.url(), self.post_data(phone="12"))
        self.assertFalse(CourseWaitlistEntry.objects.exists())

    @override_settings(ENQUIRY_RATE_LIMIT=1)
    def test_rate_limited(self):
        self.assertEqual(self.client.post(self.url(), self.post_data()).status_code, 302)
        self.assertEqual(self.client.post(self.url(), self.post_data(email="b@example.com")).status_code, 429)

    def test_closed_waitlist_refuses_sign_ups(self):
        Course.objects.filter(pk=self.course.pk).update(waitlist_open=False)
        self.assertEqual(self.client.post(self.url(), self.post_data()).status_code, 404)
        self.assertContains(self.client.get(self.url()), "Sign-ups for this course are closed")

    def test_general_waitlist_on_the_list_page(self):
        response = self.client.post(reverse("courses:list"), self.post_data())
        self.assertRedirects(response, reverse("courses:list"), fetch_redirect_response=False)
        self.assertIsNone(CourseWaitlistEntry.objects.get().course)
        self.assertContains(self.client.get(reverse("courses:list")), "You're on the list.")


class WaitlistAdminAndPrivacyTests(CourseTestCase):
    def setUp(self):
        super().setUp()
        self.entry = CourseWaitlistEntry.objects.create(name="=SUM(1)", email="asha@example.com", course=self.course)
        self.staff = get_user_model().objects.create_superuser("boss", "boss@example.com", "pw")
        force_login_verified(self.client, self.staff)

    def run_action(self, action, **extra):
        return self.client.post(
            reverse("admin:courses_coursewaitlistentry_changelist"),
            {"action": action, "_selected_action": [self.entry.pk], **extra},
        )

    def test_csv_export_neutralises_formulas(self):
        text = self.run_action("export_csv").content.decode()
        self.assertIn("'=SUM(1)", text)
        self.assertIn("Build a Web App", text)

    def test_anonymise_asks_first_then_removes_personal_details(self):
        self.assertContains(self.run_action("anonymise_selected"), "This cannot be undone")
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.name, "=SUM(1)")
        self.run_action("anonymise_selected", confirm="yes", post="yes")
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.name, "Anonymised")
        self.assertEqual(self.entry.email, f"anonymised-{self.entry.pk}@example.invalid")
        self.assertIsNotNone(self.entry.anonymised_at)

    def test_retention_command(self):
        old = CourseWaitlistEntry.objects.create(name="Old", email="old@example.com")
        CourseWaitlistEntry.objects.filter(pk=old.pk).update(created_at=timezone.now() - datetime.timedelta(days=800))
        out = StringIO()
        call_command("anonymise_old_waitlist", stdout=out)
        old.refresh_from_db()
        self.entry.refresh_from_db()
        self.assertEqual(old.name, "Anonymised")
        self.assertEqual(self.entry.name, "=SUM(1)")
        self.assertIn("Anonymised 1", out.getvalue())

    def test_anonymise_is_idempotent(self):
        self.assertEqual(anonymise_entries(CourseWaitlistEntry.objects.all()), 1)
        self.assertEqual(anonymise_entries(CourseWaitlistEntry.objects.all()), 0)

    def test_course_admin_lists_waitlist_count(self):
        self.assertContains(self.client.get(reverse("admin:courses_course_changelist")), "Build a Web App")
