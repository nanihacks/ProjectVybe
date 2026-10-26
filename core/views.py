import logging

from django.conf import settings
from django.contrib.staticfiles import finders
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseServerError, JsonResponse
from django.shortcuts import redirect, render
from django.templatetags.static import static
from django.template.loader import render_to_string
from django.urls import reverse

from .images import cloudinary_url


logger = logging.getLogger(__name__)

# Shown if even the standalone template cannot be rendered.
LAST_RESORT_HTML = (
    "<!doctype html><html lang='en'><meta charset='utf-8'><title>Something went wrong</title>"
    "<body style='font-family:sans-serif;padding:2rem'><h1>Something went wrong.</h1>"
    "<p>Please try again in a few minutes.</p></body></html>"
)


def health_check(request):
    return JsonResponse({"status": "ok"})


def _standalone(template_name, response_class, context=None):
    """Render a page that needs no database, session or context processors."""
    page_context = {"contact_email": settings.PUBLIC_CONTACT_EMAIL.strip(), **(context or {})}
    try:
        return response_class(render_to_string(template_name, page_context))
    except Exception:
        logger.exception("Could not render %s", template_name)
        return response_class(LAST_RESORT_HTML)


def favicon(request):
    """Browsers ask for /favicon.ico at the site root whatever the page says.

    The icon is sent straight back, so there is no redirect hop on every first visit.
    """
    path = finders.find("images/brand/favicon.ico")
    if not path:
        return redirect(static("images/brand/favicon.ico"))
    with open(path, "rb") as icon_file:
        response = HttpResponse(icon_file.read(), content_type="image/x-icon")
    response["Cache-Control"] = "public, max-age=86400"
    return response


def error_404(request, exception):
    from catalog.models import Project

    projects = list(
        Project.objects.filter(is_published=True, category__is_active=True)
        .select_related("category")
        .order_by("-featured", "-created_at")[:3]
    )
    for project in projects:
        project.render_thumbnail_url = cloudinary_url(project.thumbnail, width=640)
        if not project.render_thumbnail_url:
            # The card falls back to project.thumbnail.url, which raises if Cloudinary
            # is misconfigured. An error page must never fail, so show the placeholder.
            project.thumbnail = None
        project.page_url = reverse("pages:project_detail", kwargs={"slug": project.slug})

    return render(
        request,
        "404.html",
        {
            "popular_projects": projects,
            "robots_directive": "noindex, follow",
        },
        status=404,
    )


def error_500(request):
    # Deliberately independent of the database and of base.html: errors often
    # happen because the database is unavailable.
    return _standalone("500.html", HttpResponseServerError)


def error_400(request, exception):
    return _standalone("400.html", HttpResponseBadRequest)


def error_403(request, exception):
    return render(request, "403.html", {"robots_directive": "noindex, follow"}, status=403)


def csrf_failure(request, reason=""):
    """Friendly page when a form was submitted with an expired or missing CSRF token."""
    return render(request, "403_csrf.html", {"robots_directive": "noindex, follow"}, status=403)


def maintenance_page(message="", return_time=None):
    response = _standalone(
        "503.html",
        lambda body: HttpResponse(body, status=503),
        {"message": message, "return_time": return_time},
    )
    response["Cache-Control"] = "no-store"
    return response
