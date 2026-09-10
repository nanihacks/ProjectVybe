import logging

from django.shortcuts import redirect, render

from catalog.models import Project, Service

from .forms import LeadForm
from .utils import build_enquiry_message, send_enquiry_email, whatsapp_enquiry_url


logger = logging.getLogger(__name__)


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
            lead = form.save()
            project_wizard = request.POST.get("project_wizard") == "1"

            if project_wizard:
                whatsapp_url = whatsapp_enquiry_url(
                    build_enquiry_message(form.cleaned_data)
                )
                if whatsapp_url:
                    return redirect(whatsapp_url)

                return render(
                    request,
                    "pages/enquiry.html",
                    {
                        "enquiry_submitted": True,
                        "email_sent": False,
                        "project_whatsapp_only": True,
                        "whatsapp_url": "",
                        "selected_project": selected_project,
                        "selected_service": None,
                        "selected_addon": None,
                        "project_enquiry": False,
                        "breadcrumbs": [{"label": "Enquiry"}],
                    },
                )

            try:
                email_sent = send_enquiry_email(form.cleaned_data)
            except Exception:
                logger.exception("Unable to send enquiry email for lead %s", lead.pk)
                email_sent = False
            return render(
                request,
                "pages/enquiry.html",
                {
                    "enquiry_submitted": True,
                    "email_sent": email_sent,
                    "whatsapp_url": "",
                    "selected_project": selected_project,
                    "selected_service": None,
                    "selected_addon": None,
                    "project_enquiry": False,
                    "breadcrumbs": [{"label": "Enquiry"}],
                },
            )
    else:
        initial = {}
        if selected_project:
            initial["project"] = selected_project.pk
        if selected_service:
            initial["selected_services"] = [selected_service.pk]
        if selected_addon:
            initial["selected_addons"] = [selected_addon.pk]
        form = LeadForm(initial=initial, project=selected_project)

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
    )


def enquiry_success(request):
    success_data = request.session.pop("enquiry_success", None)
    if success_data is None:
        return redirect("leads:enquiry")

    return render(
        request,
        "pages/enquiry_success.html",
        {
            "whatsapp_url": success_data.get("whatsapp_url", ""),
            "breadcrumbs": [{"label": "Enquiry received"}],
        },
    )
