import logging
import math

from django.conf import settings
from django.utils import timezone

from .site import get_site_settings
from .views import maintenance_page


logger = logging.getLogger(__name__)

DEFAULT_RETRY_SECONDS = 3600


class MaintenanceModeMiddleware:
    """Show visitors a 503 page while maintenance mode is on (Site Settings).

    Staff, the admin, health checks, static files and the sitemap keep working,
    so you can always log in and switch it off.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not self._is_exempt(request.path):
            site_settings = self._site_settings(request)
            if site_settings is not None and site_settings.maintenance_enabled:
                if not self._is_staff(request):
                    return self._maintenance_response(site_settings)
        return self.get_response(request)

    @staticmethod
    def _is_exempt(path):
        exempt_prefixes = (
            "/static/",
            "/health/",
            f"/{settings.ADMIN_URL}",
            "/robots.txt",
            "/sitemap.xml",
        )
        return path.startswith(exempt_prefixes)

    @staticmethod
    def _site_settings(request):
        try:
            return get_site_settings(request)
        except Exception:
            # If the database is down, let the normal error handling deal with it.
            logger.exception("Could not read site settings for maintenance mode")
            return None

    @staticmethod
    def _is_staff(request):
        user = getattr(request, "user", None)
        return bool(user is not None and user.is_authenticated and user.is_staff)

    @staticmethod
    def _maintenance_response(site_settings):
        response = maintenance_page(
            message=site_settings.maintenance_message,
            return_time=site_settings.maintenance_return_time,
        )
        return_time = site_settings.maintenance_return_time
        retry_after = DEFAULT_RETRY_SECONDS
        if return_time and return_time > timezone.now():
            retry_after = max(60, math.ceil((return_time - timezone.now()).total_seconds()))
        response["Retry-After"] = str(retry_after)
        return response
