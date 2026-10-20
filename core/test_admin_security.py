from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django_otp.plugins.otp_static.models import StaticDevice, StaticToken

from .testing import force_login_verified


PASSWORD = "a-long-test-password-123"
ALERT_SETTINGS = {
    "PUBLIC_CONTACT_EMAIL": "owner@example.com",
    "DEFAULT_FROM_EMAIL": "ProjectVybe <no-reply@example.com>",
}


class AdminTwoFactorTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_superuser(
            username="boss", email="boss@example.com", password=PASSWORD
        )
        cls.device = StaticDevice.objects.create(user=cls.user, name="backup", confirmed=True)
        StaticToken.objects.create(device=cls.device, token="abcd1234")

    def setUp(self):
        cache.clear()

    def login(self, **extra):
        data = {"username": "boss", "password": PASSWORD, "next": reverse("admin:index")}
        data.update(extra)
        return self.client.post(reverse("admin:login"), data, secure=True)

    def test_login_page_asks_for_a_one_time_password(self):
        response = self.client.get(reverse("admin:login"), secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="otp_token"')

    def test_password_alone_does_not_open_the_admin(self):
        response = self.login()

        self.assertEqual(response.status_code, 200)
        index = self.client.get(reverse("admin:index"), secure=True)
        self.assertEqual(index.status_code, 302)
        self.assertIn("login", index["Location"])

    def test_wrong_token_is_refused(self):
        self.login(otp_device=self.device.persistent_id, otp_token="00000000")

        index = self.client.get(reverse("admin:index"), secure=True)
        self.assertEqual(index.status_code, 302)

    def test_valid_token_opens_the_admin(self):
        response = self.login(otp_device=self.device.persistent_id, otp_token="abcd1234")

        self.assertEqual(response.status_code, 302)
        index = self.client.get(reverse("admin:index"), secure=True)
        self.assertEqual(index.status_code, 200)
        self.assertContains(index, "ProjectVybe Admin")

    def test_backup_token_works_only_once(self):
        self.login(otp_device=self.device.persistent_id, otp_token="abcd1234")
        self.client.logout()

        self.login(otp_device=self.device.persistent_id, otp_token="abcd1234")

        index = self.client.get(reverse("admin:index"), secure=True)
        self.assertEqual(index.status_code, 302)

    def test_user_without_a_device_cannot_use_a_plain_login(self):
        get_user_model().objects.create_superuser(
            username="nodevice", email="n@example.com", password=PASSWORD
        )
        self.client.post(
            reverse("admin:login"),
            {"username": "nodevice", "password": PASSWORD},
            secure=True,
        )

        index = self.client.get(reverse("admin:index"), secure=True)
        self.assertEqual(index.status_code, 302)


class AdminLockoutTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        get_user_model().objects.create_superuser(
            username="boss", email="boss@example.com", password=PASSWORD
        )

    def setUp(self):
        cache.clear()

    def bad_login(self, ip=None):
        extra = {"HTTP_X_FORWARDED_FOR": ip} if ip else {}
        return self.client.post(
            reverse("admin:login"),
            {"username": "boss", "password": "wrong-password"},
            secure=True,
            **extra,
        )

    @override_settings(AXES_FAILURE_LIMIT=5)
    def test_ip_is_locked_out_after_five_failures(self):
        for _ in range(4):
            self.assertEqual(self.bad_login().status_code, 200)

        # The fifth failure reaches the limit and locks the IP straight away.
        self.assertEqual(self.bad_login().status_code, 429)
        self.assertEqual(self.bad_login().status_code, 429)

    @override_settings(AXES_FAILURE_LIMIT=5)
    def test_a_locked_ip_cannot_log_in_even_with_the_right_password(self):
        for _ in range(6):
            self.bad_login()

        response = self.client.post(
            reverse("admin:login"),
            {"username": "boss", "password": PASSWORD},
            secure=True,
        )

        self.assertEqual(response.status_code, 429)

    @override_settings(AXES_FAILURE_LIMIT=3, TRUSTED_PROXY_COUNT=1)
    def test_lockout_uses_the_real_client_ip_behind_the_proxy(self):
        for _ in range(4):
            self.bad_login(ip="203.0.113.5")

        self.assertEqual(self.bad_login(ip="203.0.113.5").status_code, 429)
        # A different visitor behind the same proxy is not locked out.
        self.assertEqual(self.bad_login(ip="203.0.113.6").status_code, 200)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", **ALERT_SETTINGS)
class AdminAlertEmailTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.staff = user_model.objects.create_superuser(
            username="boss", email="boss@example.com", password=PASSWORD
        )
        cls.visitor = user_model.objects.create_user(
            username="reader", email="r@example.com", password=PASSWORD
        )

    def setUp(self):
        cache.clear()
        mail.outbox.clear()

    def test_staff_login_sends_one_alert_to_the_owner(self):
        force_login_verified(self.client, self.staff)

        self.assertEqual(len(mail.outbox), 1)
        alert = mail.outbox[0]
        self.assertEqual(alert.to, ["owner@example.com"])
        self.assertIn("admin login", alert.subject)
        self.assertIn("boss", alert.body)
        self.assertNotIn(PASSWORD, alert.body)

    def test_non_staff_login_sends_no_alert(self):
        self.client.force_login(self.visitor)

        self.assertEqual(len(mail.outbox), 0)

    def test_failed_logins_are_not_emailed(self):
        for _ in range(3):
            self.client.post(
                reverse("admin:login"),
                {"username": "boss", "password": "wrong"},
                secure=True,
            )

        self.assertEqual(len(mail.outbox), 0)

    @override_settings(AXES_FAILURE_LIMIT=3)
    def test_lockout_sends_a_single_alert_per_ip(self):
        for _ in range(8):
            self.client.post(
                reverse("admin:login"),
                {"username": "boss", "password": "wrong"},
                secure=True,
            )

        lockout_alerts = [m for m in mail.outbox if "lockout" in m.subject]
        self.assertEqual(len(lockout_alerts), 1)
        self.assertEqual(lockout_alerts[0].to, ["owner@example.com"])
        self.assertIn("127.0.0.1", lockout_alerts[0].body)
