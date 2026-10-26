import re
from urllib.parse import parse_qs, urlencode, urlsplit

from django.conf import settings
from django.core.paginator import Paginator
from django.db.models import Count, Prefetch, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from catalog.models import Category, Project, ProjectAddon, ProjectImage, Review, Service
from core.images import cloudinary_url as _safe_cloudinary_url
from core.ratelimit import is_rate_limited
from core.seo import absolute_url, json_ld_string
from core.site import get_site_settings
from leads.forms import LeadForm
from orders import services as orders_services


YOUTUBE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{11}$")


def _youtube_embed_url(value):
    """Return a safe privacy-enhanced YouTube embed URL for a validated link."""
    if not value:
        return ""

    parsed = urlsplit(str(value).strip())
    hostname = (parsed.hostname or "").lower().rstrip(".")
    video_id = ""

    if hostname in {"youtu.be", "www.youtu.be"}:
        video_id = parsed.path.strip("/").split("/", 1)[0]
    elif hostname in {"youtube.com", "www.youtube.com"}:
        video_id = parse_qs(parsed.query).get("v", [""])[0]
        if not video_id:
            path_parts = [part for part in parsed.path.split("/") if part]
            if len(path_parts) >= 2 and path_parts[0] in {"embed", "shorts", "live"}:
                video_id = path_parts[1]

    if not YOUTUBE_ID_PATTERN.fullmatch(video_id):
        return ""

    return f"https://www.youtube-nocookie.com/embed/{video_id}?rel=0"


def home(request):
    home_url = reverse("pages:home")
    services_url = reverse("pages:services")

    featured_projects = list(
        Project.objects.filter(
            is_published=True,
            featured=True,
            category__is_active=True,
        )
        .select_related("category")
        .order_by("-created_at")[:3]
    )
    services = list(Service.objects.filter(is_active=True).order_by("ordering", "name")[:6])
    reviews = list(
        Review.objects.filter(is_published=True)
        .order_by("ordering", "-created_at")
    )

    for project in featured_projects:
        project.render_thumbnail_url = _safe_cloudinary_url(project.thumbnail, width=640)
    for service in services:
        service.render_image_url = _safe_cloudinary_url(service.image, width=640)

    return render(
        request,
        "pages/home.html",
        {
            "featured_projects": featured_projects,
            "services": services,
            "reviews": reviews,
            # The #projects anchor only exists while the categories section is shown.
            "projects_anchor": (
                f"{home_url}#projects"
                if get_site_settings(request).show_categories_section
                else reverse("pages:project_catalogue")
            ),
            "services_url": services_url,
            "contact_anchor": f"{home_url}#contact",
            "canonical_url": absolute_url(home_url),
            "structured_data_json": json_ld_string(
                {
                    "@context": "https://schema.org",
                    "@type": "WebSite",
                    "name": settings.SITE_NAME,
                    "url": absolute_url(home_url),
                }
            ),
        },
    )


def services(request):
    service_cards = []
    for service in Service.objects.filter(is_active=True).order_by("ordering", "name"):
        service_cards.append(
            {
                "service": service,
                "image_url": _safe_cloudinary_url(service.image, width=640),
                "detail_url": reverse("pages:service_detail", kwargs={"slug": service.slug}),
            }
        )

    return render(
        request,
        "pages/services.html",
        {
            "service_cards": service_cards,
            "breadcrumbs": [{"label": "Services"}],
        },
    )


def service_detail(request, slug):
    service = get_object_or_404(Service, slug=slug, is_active=True)
    others = list(
        Service.objects.filter(is_active=True).exclude(pk=service.pk).order_by("ordering", "name")[:3]
    )
    image_url = _safe_cloudinary_url(service.image, width=1200)
    canonical_url = absolute_url(reverse("pages:service_detail", kwargs={"slug": service.slug}))
    structured_data = {
        "@context": "https://schema.org",
        "@type": "Service",
        "name": service.name,
        "description": service.short_description,
        "url": canonical_url,
        "provider": {"@type": "Organization", "name": settings.SITE_NAME, "url": absolute_url("/")},
    }
    if image_url:
        structured_data["image"] = image_url
    return render(
        request,
        "pages/service_detail.html",
        {
            "service": service,
            "image_url": image_url,
            "other_services": others,
            "enquiry_url": f"{reverse('leads:enquiry')}?{urlencode({'service': service.slug})}",
            "canonical_url": canonical_url,
            "og_image_url": image_url,
            "structured_data_json": json_ld_string(structured_data),
            "breadcrumbs": [
                {"label": "Services", "url": reverse("pages:services")},
                {"label": service.name},
            ],
        },
    )


def about(request):
    category_cards = []
    categories = (
        Category.objects.filter(is_active=True)
        .annotate(project_count=Count("projects", filter=Q(projects__is_published=True)))
        .order_by("name")
    )
    for category in categories:
        category_cards.append(
            {
                "category": category,
                "category_url": (
                    f"{reverse('pages:project_catalogue')}?"
                    f"{urlencode({'category': category.slug})}#project-results-title"
                ),
            }
        )

    navigation_categories = [item["category"] for item in category_cards]

    return render(
        request,
        "pages/about.html",
        {
            "category_cards": category_cards,
            "navigation_categories": navigation_categories,
            "breadcrumbs": [{"label": "About"}],
        },
    )


def robots_txt(request):
    sitemap_url = absolute_url(reverse("sitemap"))
    content = "\n".join(
        (
            "User-agent: *",
            "Allow: /",
            "Disallow: /enquiry/success/",
            f"Sitemap: {sitemap_url}",
            "",
        )
    )
    return HttpResponse(content, content_type="text/plain")


def project_catalogue(request):
    query = request.GET.get("q", "").strip()
    category_slug = request.GET.get("category", "").strip()

    active_categories = Category.objects.filter(is_active=True).order_by("name")
    selected_category = (
        active_categories.filter(slug=category_slug).first()
        if category_slug
        else None
    )

    projects = (
        Project.objects.filter(
            is_published=True,
            category__is_active=True,
        )
        .select_related("category")
        .order_by("-created_at", "-pk")
    )

    if selected_category:
        projects = projects.filter(category=selected_category)

    if query:
        projects = projects.filter(
            Q(title__icontains=query)
            | Q(short_description__icontains=query)
            | Q(description__icontains=query)
            | Q(technology_stack__icontains=query)
            | Q(features__icontains=query)
        )

    paginator = Paginator(projects, 12)
    page_obj = paginator.get_page(request.GET.get("page"))
    for project in page_obj.object_list:
        project.render_thumbnail_url = _safe_cloudinary_url(project.thumbnail, width=640)

    filters = {}
    if query:
        filters["q"] = query
    if selected_category:
        filters["category"] = selected_category.slug

    has_filter = bool(query or category_slug)
    canonical_path = reverse("pages:project_catalogue")
    if not has_filter and page_obj.number > 1:
        canonical_path = f"{canonical_path}?page={page_obj.number}"

    return render(
        request,
        "pages/projects.html",
        {
            "page_obj": page_obj,
            "active_categories": active_categories,
            "navigation_categories": active_categories,
            "query": query,
            "selected_category": selected_category,
            "filter_query": urlencode(filters),
            "breadcrumbs": [{"label": "Projects"}],
            "canonical_url": absolute_url(canonical_path),
            "robots_directive": "noindex, follow" if has_filter else "index, follow",
        },
    )


def project_search(request):
    query = request.GET.get("q", "").strip()[:80]
    if not query:
        return JsonResponse({"query": "", "results": []})
    if is_rate_limited(request, "search", settings.SEARCH_RATE_LIMIT, 60):
        return JsonResponse(
            {"query": query, "results": [], "error": "rate_limited"},
            status=429,
        )

    projects = (
        Project.objects.filter(
            is_published=True,
            category__is_active=True,
        )
        .filter(
            Q(title__icontains=query)
            | Q(short_description__icontains=query)
            | Q(description__icontains=query)
            | Q(technology_stack__icontains=query)
            | Q(features__icontains=query)
            | Q(category__name__icontains=query)
        )
        .select_related("category")
        .order_by("-featured", "-created_at", "-pk")[:8]
    )
    results = []
    for project in projects:
        technologies = [
            line.strip()
            for line in project.technology_stack.splitlines()
            if line.strip()
        ][:4]
        results.append(
            {
                "title": project.title,
                "category": project.category.name,
                "description": project.short_description,
                "technology": " | ".join(technologies),
                "image_url": _safe_cloudinary_url(project.thumbnail, width=240),
                "url": reverse(
                    "pages:project_detail",
                    kwargs={"slug": project.slug},
                ),
            }
        )

    return JsonResponse({"query": query, "results": results})


def project_detail(request, slug):
    project = get_object_or_404(
        Project.objects.select_related("category").prefetch_related(
            Prefetch(
                "gallery_images",
                queryset=ProjectImage.objects.order_by("ordering", "id"),
                to_attr="ordered_gallery_images",
            ),
            Prefetch(
                "addons",
                queryset=ProjectAddon.objects.filter(is_active=True).order_by(
                    "ordering", "name"
                ),
                to_attr="active_addons",
            ),
            "addon_prices",
        ),
        slug=slug,
        is_published=True,
        category__is_active=True,
    )

    related_projects = list(
        Project.objects.filter(
            is_published=True,
            category=project.category,
            category__is_active=True,
        )
        .exclude(pk=project.pk)
        .select_related("category")
        .order_by("-created_at", "-pk")[:3]
    )

    if len(related_projects) < 3:
        excluded_ids = [project.pk, *(related.pk for related in related_projects)]
        related_projects.extend(
            Project.objects.filter(
                is_published=True,
                category__is_active=True,
            )
            .exclude(pk__in=excluded_ids)
            .select_related("category")
            .order_by("-created_at", "-pk")[: 3 - len(related_projects)]
        )

    for related_project in related_projects:
        related_project.render_thumbnail_url = _safe_cloudinary_url(
            related_project.thumbnail,
            width=640,
        )

    # Online payment replaces the WhatsApp modal only when every condition holds.
    checkout_url = ""
    if orders_services.checkout_available(project, get_site_settings(request)) and orders_services.policies_ready():
        checkout_url = reverse("orders:checkout", kwargs={"slug": project.slug})

    addon_enquiries = []
    for addon in project.active_addons:
        amount, included = project.addon_pricing(addon)
        addon_enquiries.append({"addon": addon, "amount": amount, "included": included})

    gallery_media = [
        {
            "url": _safe_cloudinary_url(image.image, width=1200),
            "alt_text": image.alt_text,
        }
        for image in project.ordered_gallery_images
    ]

    thumbnail_url = _safe_cloudinary_url(project.thumbnail, width=1200)
    canonical_path = reverse(
        "pages:project_detail",
        kwargs={"slug": project.slug},
    )
    canonical_url = absolute_url(canonical_path)
    structured_data = {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "CreativeWork",
                "name": project.title,
                "description": project.short_description,
                "url": canonical_url,
                "about": {
                    "@type": "Thing",
                    "name": project.category.name,
                },
                # Only advertise a price when one is actually shown on the page.
                **(
                    {
                        "offers": {
                            "@type": "Offer",
                            "price": str(project.effective_price),
                            "priceCurrency": "INR",
                            "availability": "https://schema.org/InStock",
                            "url": canonical_url,
                        }
                    }
                    if project.is_purchasable
                    else {}
                ),
            },
            {
                "@type": "BreadcrumbList",
                "itemListElement": [
                    {
                        "@type": "ListItem",
                        "position": 1,
                        "name": "Home",
                        "item": absolute_url(reverse("pages:home")),
                    },
                    {
                        "@type": "ListItem",
                        "position": 2,
                        "name": "Projects",
                        "item": absolute_url(reverse("pages:project_catalogue")),
                    },
                    {
                        "@type": "ListItem",
                        "position": 3,
                        "name": project.title,
                        "item": canonical_url,
                    },
                ],
            },
        ],
    }
    if thumbnail_url:
        structured_data["@graph"][0]["image"] = thumbnail_url

    return render(
        request,
        "pages/project_detail.html",
        {
            "project": project,
            "gallery_images": project.ordered_gallery_images,
            "gallery_media": gallery_media,
            "thumbnail_url": thumbnail_url,
            "youtube_embed_url": _youtube_embed_url(project.youtube_demo_url),
            "features": [
                line.strip()
                for line in project.features.splitlines()
                if line.strip()
            ],
            "usage_points": [
                line.strip().lstrip("-*• ").strip()
                for line in project.usage.splitlines()
                if line.strip().lstrip("-*• ").strip()
            ],
            "technology_stack": [
                line.strip()
                for line in project.technology_stack.splitlines()
                if line.strip()
            ],
            "related_projects": related_projects,
            "canonical_url": canonical_url,
            "og_image_url": thumbnail_url,
            "og_type": "article",
            "structured_data_json": json_ld_string(structured_data),
            "addon_enquiries": addon_enquiries,
            "checkout_url": checkout_url,
            "delivery_promise": (
                f"Within {project.delivery_hours or get_site_settings(request).delivery_window_hours} hours, in business hours"
                if checkout_url
                else ""
            ),
            "enquiry_form": LeadForm(
                initial={"project": project.pk},
                project=project,
            ),
            "enquiry_url": (
                f"{reverse('leads:enquiry')}?"
                f"{urlencode({'project': project.slug})}"
            ),
            "breadcrumbs": [
                {"label": "Projects", "url": reverse("pages:project_catalogue")},
                {"label": project.title},
            ],
        },
    )
