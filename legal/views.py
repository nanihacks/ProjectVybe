from django.http import Http404
from django.shortcuts import redirect, render

from core.seo import absolute_url

from .models import PAGE_URL_NAMES
from .rendering import fill_placeholders
from .services import get_public_page


def legal_page(request, slug):
    page, version = get_public_page(slug)
    if page is None:
        raise Http404("No such page.")

    # Pages with their own address are redirected there from /legal/<slug>/.
    if request.resolver_match.url_name == "legal_page" and slug in PAGE_URL_NAMES:
        return redirect(page.get_absolute_url(), permanent=True)

    return render(
        request,
        "legal/page.html",
        {
            "page": page,
            "version": version,
            "body_html": fill_placeholders(version.body_html),
            "canonical_url": absolute_url(page.get_absolute_url()),
            "breadcrumbs": [{"label": page.title}],
        },
    )
