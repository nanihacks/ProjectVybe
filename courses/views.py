from django.conf import settings
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from core.images import cloudinary_url
from core.ratelimit import is_rate_limited
from core.seo import absolute_url, json_ld_string
from core.turnstile import FAILURE_MESSAGE, request_passes
from leads.models import ConsentRecord
from legal.services import current_privacy_version

from .emails import queue_waitlist_emails
from .forms import WaitlistForm
from .models import Course, CourseWaitlistEntry


SESSION_KEY = "waitlist_joined"


def _consent_fields(form):
    return [form[name] for name in ("consent_contact", "consent_age", "consent_marketing")]


def _published():
    return Course.objects.filter(is_published=True).select_related("category")


def _join_waitlist(request, course):
    """Handle a waitlist POST. Returns (form, outcome): None (form has errors), "joined" or "limited".

    An address that is already on the list gets the same success page, so the form
    cannot be used to find out who has signed up.
    """
    form = WaitlistForm(request.POST)
    if not form.is_valid():
        return form, None
    if not request_passes(request):
        form.add_error(None, FAILURE_MESSAGE)
        return form, None
    if is_rate_limited(request, "waitlist", settings.ENQUIRY_RATE_LIMIT, settings.ENQUIRY_RATE_WINDOW):
        form.add_error(None, "Too many sign-ups from your network. Please wait a few minutes and try again.")
        return form, "limited"

    email = form.cleaned_data["email"]
    already = CourseWaitlistEntry.objects.filter(
        email__iexact=email, course=course, anonymised_at__isnull=True
    ).exists()
    if not already:
        privacy_version = current_privacy_version()
        with transaction.atomic():
            entry = CourseWaitlistEntry.objects.create(
                name=form.cleaned_data["name"],
                email=email,
                phone=form.cleaned_data["phone"],
                course=course,
            )
            ConsentRecord.objects.create(
                waitlist_entry=entry,
                contact_consent=form.cleaned_data["consent_contact"],
                age_confirmed=form.cleaned_data["consent_age"],
                marketing_opt_in=form.cleaned_data["consent_marketing"],
                privacy_policy=privacy_version,
                privacy_policy_version=privacy_version.label if privacy_version else "",
                consent_text=form.consent_text(),
            )
        queue_waitlist_emails(entry)
    request.session[SESSION_KEY] = course.pk if course else 0
    return form, "joined"


def course_list(request):
    status = 200
    if request.method == "POST":
        form, outcome = _join_waitlist(request, None)
        if outcome == "joined":
            return redirect(request.path)
        status = 429 if outcome == "limited" else 200
    else:
        form = WaitlistForm()
    courses = list(_published())
    for course in courses:
        course.render_cover_url = cloudinary_url(course.cover, width=640)
    joined = request.session.pop(SESSION_KEY, None) == 0
    return render(
        request,
        "courses/list.html",
        {
            "courses": courses,
            "form": form,
            "consent_fields": _consent_fields(form),
            "joined": joined,
            "breadcrumbs": [{"label": "Courses"}],
        },
        status=status,
    )


def course_detail(request, slug):
    course = get_object_or_404(_published(), slug=slug)
    status = 200
    if request.method == "POST":
        if not course.waitlist_open:
            raise Http404("This course is not taking sign-ups.")
        form, outcome = _join_waitlist(request, course)
        if outcome == "joined":
            return redirect(request.path)
        status = 429 if outcome == "limited" else 200
    else:
        form = WaitlistForm()

    canonical = absolute_url(reverse("courses:detail", kwargs={"slug": course.slug}))
    cover_url = cloudinary_url(course.cover, width=1200)
    structured = {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "Course",
                "name": course.title,
                "description": course.summary,
                "url": canonical,
                "provider": {"@type": "Organization", "name": settings.SITE_NAME, "sameAs": absolute_url("/")},
                **({"image": cover_url} if cover_url else {}),
            },
            {
                "@type": "BreadcrumbList",
                "itemListElement": [
                    {"@type": "ListItem", "position": 1, "name": "Home", "item": absolute_url(reverse("pages:home"))},
                    {"@type": "ListItem", "position": 2, "name": "Courses", "item": absolute_url(reverse("courses:list"))},
                    {"@type": "ListItem", "position": 3, "name": course.title, "item": canonical},
                ],
            },
        ],
    }
    joined = request.session.pop(SESSION_KEY, None) == course.pk
    return render(
        request,
        "courses/detail.html",
        {
            "course": course,
            "form": form,
            "consent_fields": _consent_fields(form),
            "joined": joined,
            "cover_url": cover_url,
            "canonical_url": canonical,
            "og_image_url": cover_url,
            "structured_data_json": json_ld_string(structured),
            "breadcrumbs": [
                {"label": "Courses", "url": reverse("courses:list")},
                {"label": course.title},
            ],
        },
        status=status,
    )
