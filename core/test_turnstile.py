import io
import json
from unittest.mock import MagicMock, patch
from urllib.error import URLError

from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from catalog.models import Category, Project
from leads.models import Lead

from . import turnstile


KEYS = {"TURNSTILE_SITE_KEY": "site-key", "TURNSTILE_SECRET_KEY": "secret-key"}


def cloudflare_says(payload):
    response = MagicMock()
    response.__enter__.return_value = io.BytesIO(json.dumps(payload).encode())
    return response


class TurnstileVerifyTests(SimpleTestCase):
    def test_disabled_without_keys_and_never_calls_cloudflare(self):
        with patch("core.turnstile.urlopen") as urlopen:
            self.assertFalse(turnstile.is_enabled())
            self.assertTrue(turnstile.verify("", "1.2.3.4"))
            urlopen.assert_not_called()

    @override_settings(**KEYS)
    def test_missing_token_is_rejected_without_calling_cloudflare(self):
        with patch("core.turnstile.urlopen") as urlopen:
            self.assertFalse(turnstile.verify("", "1.2.3.4"))
            urlopen.assert_not_called()

    @override_settings(**KEYS)
    def test_cloudflare_success_and_failure_are_respected(self):
        with patch("core.turnstile.urlopen", return_value=cloudflare_says({"success": True})):
            self.assertTrue(turnstile.verify("token", "1.2.3.4"))
        with patch("core.turnstile.urlopen", return_value=cloudflare_says({"success": False})):
            self.assertFalse(turnstile.verify("token", "1.2.3.4"))

    @override_settings(**KEYS)
    def test_secret_and_token_are_sent_to_cloudflare(self):
        with patch(
            "core.turnstile.urlopen", return_value=cloudflare_says({"success": True})
        ) as urlopen:
            turnstile.verify("the-token", "1.2.3.4")

        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, turnstile.VERIFY_URL)
        body = request.data.decode()
        self.assertIn("secret=secret-key", body)
        self.assertIn("response=the-token", body)
        self.assertIn("remoteip=1.2.3.4", body)
        self.assertEqual(urlopen.call_args.kwargs["timeout"], 5)

    @override_settings(**KEYS)
    def test_network_errors_let_the_visitor_through(self):
        with patch("core.turnstile.urlopen", side_effect=URLError("down")):
            self.assertTrue(turnstile.verify("token", "1.2.3.4"))
        with patch("core.turnstile.urlopen", side_effect=TimeoutError()):
            self.assertTrue(turnstile.verify("token", "1.2.3.4"))


class TurnstileFormTests(TestCase):
    def setUp(self):
        cache.clear()
        category = Category.objects.create(name="Turnstile Cat", slug="turnstile-cat")
        self.project = Project.objects.create(
            title="Turnstile Project",
            slug="turnstile-project",
            short_description="Short.",
            description="Long.",
            category=category,
            is_published=True,
        )

    def post_data(self, **extra):
        data = {
            "name": "Visitor",
            "email": "visitor@example.com",
            "phone": "",
            "message": "I would like to talk about a project.",
            "consent_contact": "on",
            "consent_age": "on",
            "website": "",
        }
        data.update(extra)
        return data

    def test_widget_is_absent_when_turnstile_is_off(self):
        response = self.client.get(reverse("leads:enquiry"), secure=True)

        self.assertNotContains(response, "cf-turnstile")

    @override_settings(**KEYS)
    def test_widget_is_rendered_on_the_enquiry_page_and_the_project_modal(self):
        enquiry = self.client.get(reverse("leads:enquiry"), secure=True)
        detail = self.client.get(
            reverse("pages:project_detail", kwargs={"slug": self.project.slug}), secure=True
        )

        for response in (enquiry, detail):
            self.assertContains(response, 'data-sitekey="site-key"')
            self.assertContains(response, "challenges.cloudflare.com/turnstile/v0/api.js")
            self.assertNotContains(response, "secret-key")

    @override_settings(**KEYS)
    def test_submission_without_a_solved_challenge_is_rejected(self):
        response = self.client.post(reverse("leads:enquiry"), self.post_data(), secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "security check")
        self.assertEqual(Lead.objects.count(), 0)

    @override_settings(**KEYS)
    def test_cloudflare_rejection_blocks_the_lead(self):
        with patch("core.turnstile.urlopen", return_value=cloudflare_says({"success": False})):
            response = self.client.post(
                reverse("leads:enquiry"),
                self.post_data(**{"cf-turnstile-response": "bad"}),
                secure=True,
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Lead.objects.count(), 0)

    @override_settings(**KEYS)
    def test_a_solved_challenge_lets_the_enquiry_through(self):
        with patch("core.turnstile.urlopen", return_value=cloudflare_says({"success": True})):
            response = self.client.post(
                reverse("leads:enquiry"),
                self.post_data(**{"cf-turnstile-response": "good"}),
                secure=True,
            )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Lead.objects.count(), 1)

    @override_settings(**KEYS)
    def test_a_cloudflare_outage_does_not_lose_the_lead(self):
        with patch("core.turnstile.urlopen", side_effect=URLError("down")):
            response = self.client.post(
                reverse("leads:enquiry"),
                self.post_data(**{"cf-turnstile-response": "whatever"}),
                secure=True,
            )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Lead.objects.count(), 1)
