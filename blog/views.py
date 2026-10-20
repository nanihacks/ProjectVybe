from django.conf import settings
from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import get_object_or_404, render
from django.templatetags.static import static
from django.urls import reverse

from core.images import cloudinary_url
from core.seo import absolute_url, json_ld_string

from .models import BlogCategory, Post, Tag


POSTS_PER_PAGE = 10


def _can_preview(request):
    user = request.user
    return bool(
        user.is_authenticated
        and user.is_staff
        and getattr(user, "is_verified", lambda: False)()
        and (user.has_perm("blog.view_post") or user.has_perm("blog.change_post"))
    )


def _listing(request, queryset, *, heading, intro, canonical_path, breadcrumbs, noindex=False, category=None, tag=None):
    queryset = queryset.select_related("author", "category").prefetch_related("tags")
    page_obj = Paginator(queryset, POSTS_PER_PAGE).get_page(request.GET.get("page"))
    for post in page_obj:
        post.render_cover_url = cloudinary_url(post.cover, width=640)
    canonical = absolute_url(canonical_path)
    if page_obj.number > 1:
        canonical = f"{canonical}?page={page_obj.number}"
    return render(
        request,
        "blog/list.html",
        {
            "page_obj": page_obj,
            "heading": heading,
            "intro": intro,
            "category": category,
            "tag": tag,
            "categories": BlogCategory.objects.all(),
            "canonical_url": canonical,
            "robots_directive": "noindex, follow" if noindex else "index, follow",
            "breadcrumbs": breadcrumbs,
        },
    )


def post_list(request):
    return _listing(
        request,
        Post.objects.live(),
        heading="Blog",
        intro="Practical writing on projects, learning and building software.",
        canonical_path=reverse("blog:list"),
        breadcrumbs=[{"label": "Blog"}],
    )


def category_posts(request, slug):
    category = get_object_or_404(BlogCategory, slug=slug)
    return _listing(
        request,
        Post.objects.live().filter(category=category),
        heading=category.name,
        intro=category.description,
        canonical_path=category.get_absolute_url(),
        breadcrumbs=[{"label": "Blog", "url": reverse("blog:list")}, {"label": category.name}],
        category=category,
    )


def tag_posts(request, slug):
    tag = get_object_or_404(Tag, slug=slug)
    return _listing(
        request,
        Post.objects.live().filter(tags=tag),
        heading=f"Tagged “{tag.name}”",
        intro="",
        canonical_path=tag.get_absolute_url(),
        breadcrumbs=[{"label": "Blog", "url": reverse("blog:list")}, {"label": tag.name}],
        noindex=True,
        tag=tag,
    )


def post_detail(request, slug):
    queryset = Post.objects.select_related("author", "category").prefetch_related("tags", "related_projects__category")
    post = get_object_or_404(queryset, slug=slug)
    previewing = False
    if not post.is_live:
        if request.GET.get("preview") and _can_preview(request):
            previewing = True
        else:
            raise Http404("Post not found.")

    canonical = absolute_url(post.get_absolute_url())
    cover_url = cloudinary_url(post.cover, width=1200)
    logo = absolute_url(static("images/brand/projectvybe-logo-email.png"))
    article = {
        "@type": "BlogPosting",
        "headline": post.title,
        "description": post.page_description,
        "datePublished": post.publish_at.isoformat(),
        "dateModified": post.updated_at.isoformat(),
        "mainEntityOfPage": canonical,
        "author": {"@type": "Person", "name": post.author.name},
        "publisher": {
            "@type": "Organization",
            "name": settings.SITE_NAME,
            "logo": {"@type": "ImageObject", "url": logo},
        },
    }
    if cover_url:
        article["image"] = cover_url
    structured = {
        "@context": "https://schema.org",
        "@graph": [
            article,
            {
                "@type": "BreadcrumbList",
                "itemListElement": [
                    {"@type": "ListItem", "position": 1, "name": "Home", "item": absolute_url(reverse("pages:home"))},
                    {"@type": "ListItem", "position": 2, "name": "Blog", "item": absolute_url(reverse("blog:list"))},
                    {"@type": "ListItem", "position": 3, "name": post.category.name, "item": absolute_url(post.category.get_absolute_url())},
                    {"@type": "ListItem", "position": 4, "name": post.title, "item": canonical},
                ],
            },
        ],
    }
    related_projects = [project for project in post.related_projects.all() if project.is_published and project.category.is_active]
    for project in related_projects:
        project.render_thumbnail_url = cloudinary_url(project.thumbnail, width=640)
    return render(
        request,
        "blog/detail.html",
        {
            "post": post,
            "cover_url": cover_url,
            "related_projects": related_projects,
            "previewing": previewing,
            "canonical_url": canonical,
            "og_type": "article",
            "og_image_url": cover_url,
            "robots_directive": "noindex, nofollow" if previewing else "index, follow",
            "structured_data_json": json_ld_string(structured),
            "breadcrumbs": [
                {"label": "Blog", "url": reverse("blog:list")},
                {"label": post.category.name, "url": post.category.get_absolute_url()},
                {"label": post.title},
            ],
        },
    )
