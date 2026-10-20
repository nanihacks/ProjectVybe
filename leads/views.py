from django.conf import settings
from django.db import transaction
from django.shortcuts import redirect, render

from catalog.models import Project, Service
from core.mail import run_in_background
from core.ratelimit import is_rate_limited
from core.site import get_site_settings
from core.turnstile import FAILURE_MESSAGE, request_passes

from legal.services import current_privacy_version

from .forms import LeadForm, PrivacyRequestForm
from .models import ConsentRecord, Lead, PrivacyRequest
from .utils import (
    build_enquiry_message,
    queue_lead_emails,
    send_privacy_request_emails,
    whatsapp_enquiry_url,
)


def _full_lead(lead_id):
    if not lead_id:
        return None
    return (
        Lead.objects.select_related("project")
        .prefetch_related("selected_services", "selected_addons")
        .filter(pk=lead_id)
        .first()
    )


def _render_enquiry(request, form, selected_project, selected_service, selected_addon, status=200):
    return render(
        request,
        "pages/enquiry.html",
        {
            "form": form,
            "selected_project": selected_project,
            "selected_service": selected_service,
            "selected_addon": selected_addon,
            "project_enquiry": selected_project is not None,
            "breadcrumbs": [{"label": "Enquiry"}],
        },
        status=status,
    )


def enquiry(request):
    project_slug = request.GET.get("project", "").strip()
    service_slug = request.GET.get("service", "").strip()
    addon_slug = request.GET.get("addon", "").strip()

    public_projects = Project.objects.filter(
        is_published=True,
        category__is_active=True,
    )
    selected_project = public_projects.filter(slug=project_slug).first()
    selected_service = Service.objects.filter(
        is_active=True,
        slug=service_slug,
    ).first()
    selected_addon = (
        selected_project.addons.filter(is_active=True, slug=addon_slug).first()
        if selected_project and addon_slug
        else None
    )

    if request.method == "POST":
        posted_project_id = request.POST.get("project", "").strip()
        selected_project = (
            public_projects.filter(pk=posted_project_id).first()
            if posted_project_id
            else None
        )
        form = LeadForm(request.POST, project=selected_project)
        if form.is_valid():
            if not request_passes(request):
                form.add_error(None, FAILURE_MESSAGE)
                return _render_enquiry(
                    request, form, selected_project, selected_service, selected_addon
                )
            if is_rate_limited(
                request,
                "enquiry",
                settings.ENQUIRY_RATE_LIMIT,
                settings.ENQUIRY_RATE_WINDOW,
            ):
                form.add_error(
                    None,
                    "Too many enquiries were sent from your network. "
                    "Please wait a few minutes and try again.",
                )
                return _render_enquiry(
                    request, form, selected_project, selected_service, selected_addon, status=429
                )

            privacy_version = current_privacy_version()
            with transaction.atomic():
                lead = form.save()
                ConsentRecord.objects.create(
                    lead=lead,
                    contact_consent=form.cleaned_data["consent_contact"],
                    age_confirmed=form.cleaned_data["consent_age"],
                    marketing_opt_in=form.cleaned_data["consent_marketing"],
                    privacy_policy=privacy_version,
                    privacy_policy_version=privacy_version.label if privacy_version else "",
                    consent_text=form.consent_text(),
                )
            queue_lead_emails(lead)

            request.session["enquiry_success"] = {"lead_id": lead.pk}
            if request.POST.get("project_wizard") == "1":
                whatsapp_url = whatsapp_enquiry_url(build_enquiry_message(_full_lead(lead.pk)))
                if whatsapp_url:
                    return redirect(whatsapp_url)
            return redirect("leads:success")
    else:
        initial = {}
        if selected_project:
            initial["project"] = selected_project.pk
        if selected_service:
            initial["selected_services"] = [selected_service.pk]
        if selected_addon:
            initial["selected_addons"] = [selected_addon.pk]
        form = LeadForm(initial=initial, project=selected_project)

    return _render_enquiry(request, form, selected_project, selected_service, selected_addon)


def enquiry_success(request):
    success_data = request.session.get("enquiry_success")
    lead = _full_lead(success_data.get("lead_id")) if success_data else None
    if lead is None:
        return redirect("leads:enquiry")

    return render(
        request,
        "pages/enquiry_success.html",
        {
            "reference": lead.reference,
            "project": lead.project,
            "whatsapp_url": (
                whatsapp_enquiry_url(build_enquiry_message(lead))
                if get_site_settings(request).show_whatsapp_button
                else ""
            ),
            "breadcrumbs": [{"label": "Enquiry received"}],
        },
    )


def privacy_request(request):
    """Public form to ask us to show, correct, delete or stop using your information."""
    if request.method == "POST":
        form = PrivacyRequestForm(request.POST)
        if form.is_valid():
            if not request_passes(request):
                form.add_error(None, FAILURE_MESSAGE)
            elif is_rate_limited(
                request,
                "privacy",
                settings.ENQUIRY_RATE_LIMIT,
                settings.ENQUIRY_RATE_WINDOW,
            ):
                form.add_error(
                    None,
                    "Too many requests were sent from your network. "
                    "Please wait a few minutes and try again.",
                )
                return render(
                    request,
                    "leads/privacy_request.html",
                    {"form": form, "breadcrumbs": [{"label": "Privacy request"}]},
                    status=429,
                )
            else:
                privacy_request_obj = form.save()
                run_in_background(send_privacy_request_emails, privacy_request_obj.pk)
                request.session["privacy_request"] = {"id": privacy_request_obj.pk}
                return redirect("pages:privacy_request_received")
    else:
        form = PrivacyRequestForm()

    return render(
        request,
        "leads/privacy_request.html",
        {"form": form, "breadcrumbs": [{"label": "Privacy request"}]},
    )


def privacy_request_received(request):
    stored = request.session.get("privacy_request")
    privacy_request_obj = (
        PrivacyRequest.objects.filter(pk=stored.get("id")).first() if stored else None
    )
    if privacy_request_obj is None:
        return redirect("pages:privacy_request")

    return render(
        request,
        "leads/privacy_request_received.html",
        {
            "request_number": privacy_request_obj.request_number,
            "breadcrumbs": [{"label": "Privacy request received"}],
        },
    )
