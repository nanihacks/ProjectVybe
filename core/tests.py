import os
import subprocess
import sys

from django.conf import settings
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from .views import error_500


def run_settings_process(environment):
    process_environment = os.environ.copy()
    process_environment.update(
        {
            "SECRET_KEY": "phase14-subprocess-test-secret",
            "DEBUG": "False",
            "DATABASE_URL": "",
            "ALLOWED_HOSTS": "projectvybe.com,www.projectvybe.com",
            "CSRF_TRUSTED_ORIGINS": "https://projectvybe.com,https://www.projectvybe.com",
            "SITE_URL": "https://projectvybe.com",
            "SECURE_SSL_REDIRECT": "True",
            "SESSION_COOKIE_SECURE": "True",
            "CSRF_COOKIE_SECURE": "True",
        }
    )
    process_environment.update(environment)
    return subprocess.run(
        [sys.executable, "-c", "import config.settings"],
        cwd=settings.BASE_DIR,
        env=process_environment,
        capture_output=True,
        text=True,
        check=False,
    )


class HealthCheckTests(TestCase):
    def test_health_check_returns_ok(self):
        response = self.client.get("/health/", secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})


class ErrorPageTests(TestCase):
    @override_settings(DEBUG=False)
    def test_server_error_template_is_generic_and_does_not_expose_configuration(self):
        request = RequestFactory().get("/", secure=True)
        response = error_500(request)

        self.assertEqual(response.status_code, 500)
        self.assertContains(response, "Something went wrong.", status_code=500)
        self.assertNotContains(response, "DATABASE_URL", status_code=500)
        self.assertNotContains(response, "SECRET_KEY", status_code=500)
        self.assertNotContains(response, "Traceback", status_code=500)


class SecurityHeaderTests(TestCase):
    def test_security_headers_are_present(self):
        response = self.client.get(reverse("pages:home"), secure=True)

        self.assertEqual(response.headers["X-Frame-Options"], "DENY")
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(
            response.headers["Referrer-Policy"],
            "strict-origin-when-cross-origin",
        )

    def test_hsts_header_is_added_only_when_configured(self):
        with self.settings(
            SECURE_SSL_REDIRECT=False,
            SECURE_HSTS_SECONDS=31536000,
            SECURE_HSTS_INCLUDE_SUBDOMAINS=True,
            SECURE_HSTS_PRELOAD=False,
        ):
            response = self.client.get(reverse("pages:home"), secure=True)

        self.assertEqual(
            response.headers["Strict-Transport-Security"],
            "max-age=31536000; includeSubDomains",
        )

    def test_cookie_security_settings_are_explicit(self):
        self.assertTrue(settings.SESSION_COOKIE_HTTPONLY)
        self.assertEqual(settings.SESSION_COOKIE_SAMESITE, "Lax")
        self.assertTrue(settings.CSRF_COOKIE_HTTPONLY)
        self.assertEqual(settings.CSRF_COOKIE_SAMESITE, "Lax")


class ProductionConfigurationTests(TestCase):
    def test_development_can_use_sqlite_without_database_url(self):
        process = run_settings_process(
            {
                "DEBUG": "True",
                "DATABASE_URL": "",
                "ALLOWED_HOSTS": "localhost,127.0.0.1",
                "CSRF_TRUSTED_ORIGINS": "",
                "SITE_URL": "http://localhost:8000",
                "SECURE_SSL_REDIRECT": "False",
                "SESSION_COOKIE_SECURE": "False",
                "CSRF_COOKIE_SECURE": "False",
            }
        )

        self.assertEqual(process.returncode, 0, process.stderr)

    def test_production_requires_database_url_without_falling_back_to_sqlite(self):
        process = run_settings_process({"DATABASE_URL": ""})
        output = f"{process.stdout}\n{process.stderr}"

        self.assertNotEqual(process.returncode, 0)
        self.assertIn("DATABASE_URL is required when DEBUG=False", output)
        self.assertNotIn("phase14-subprocess-test-secret", output)

    def test_production_rejects_invalid_or_sqlite_database_urls(self):
        invalid_process = run_settings_process({"DATABASE_URL": "not-a-database-url"})
        invalid_output = f"{invalid_process.stdout}\n{invalid_process.stderr}"

        sqlite_process = run_settings_process(
            {"DATABASE_URL": "sqlite:///production.sqlite3"}
        )
        sqlite_output = f"{sqlite_process.stdout}\n{sqlite_process.stderr}"

        self.assertNotEqual(invalid_process.returncode, 0)
        self.assertIn("DATABASE_URL must be a valid PostgreSQL URL", invalid_output)
        self.assertNotIn("not-a-database-url", invalid_output)
        self.assertNotEqual(sqlite_process.returncode, 0)
        self.assertIn("DATABASE_URL must be a valid PostgreSQL URL", sqlite_output)


class DeploymentConfigurationTests(TestCase):
    def test_wsgi_static_and_render_build_contract_are_explicit(self):
        from config.wsgi import application

        self.assertIsNotNone(application)
        self.assertEqual(settings.WSGI_APPLICATION, "config.wsgi.application")
        self.assertEqual(settings.STATIC_URL, "/static/")
        self.assertEqual(settings.STATIC_ROOT, settings.BASE_DIR / "staticfiles")
        self.assertIn(
            "whitenoise.middleware.WhiteNoiseMiddleware",
            settings.MIDDLEWARE,
        )

        build_script = (settings.BASE_DIR / "build.sh").read_text(encoding="utf-8")
        procfile = (settings.BASE_DIR / "Procfile").read_text(encoding="utf-8")

        self.assertIn("collectstatic --noinput", build_script)
        self.assertNotIn("migrate --noinput", build_script)
        self.assertEqual(procfile.strip(), "web: gunicorn config.wsgi:application")
