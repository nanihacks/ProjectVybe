from django.conf import settings
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path

from core import views as core_views
from pages.sitemaps import sitemaps


urlpatterns = [
    path(settings.ADMIN_URL, admin.site.urls),
    path("favicon.ico", core_views.favicon),
    path("sitemap.xml", sitemap, {"sitemaps": sitemaps}, name="sitemap"),
    path("", include("pages.urls")),
    path("enquiry/", include("leads.urls")),
    path("courses/", include("courses.urls")),
    path("blog/", include("blog.urls")),
    path("", include("orders.urls")),
    path("health/", include("core.urls")),
]


handler400 = "core.views.error_400"
handler403 = "core.views.error_403"
handler404 = "core.views.error_404"
handler500 = "core.views.error_500"
