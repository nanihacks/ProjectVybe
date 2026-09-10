from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path

from pages.sitemaps import sitemaps


urlpatterns = [
    path("admin/", admin.site.urls),
    path("sitemap.xml", sitemap, {"sitemaps": sitemaps}, name="sitemap"),
    path("", include("pages.urls")),
    path("enquiry/", include("leads.urls")),
    path("health/", include("core.urls")),
]


handler404 = "core.views.error_404"
handler500 = "core.views.error_500"
