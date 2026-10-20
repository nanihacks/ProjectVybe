from django.urls import path

from leads.views import privacy_request, privacy_request_received
from legal.views import legal_page

from . import views


app_name = "pages"

urlpatterns = [
    path("", views.home, name="home"),
    path("projects/", views.project_catalogue, name="project_catalogue"),
    path("projects/search/", views.project_search, name="project_search"),
    path("projects/<slug:slug>/", views.project_detail, name="project_detail"),
    path("services/", views.services, name="services"),
    path("about/", views.about, name="about"),
    path("robots.txt", views.robots_txt, name="robots_txt"),
    # Policy pages live in the database (see the legal app). The original
    # addresses are kept so existing links and search results keep working.
    path("privacy/", legal_page, {"slug": "privacy-policy"}, name="privacy_policy"),
    path("terms/", legal_page, {"slug": "terms-and-conditions"}, name="terms"),
    path("refund-policy/", legal_page, {"slug": "refund-policy"}, name="refund_policy"),
    path("cookies/", legal_page, {"slug": "cookie-policy"}, name="cookies"),
    path("grievance-redressal/", legal_page, {"slug": "grievance-redressal"}, name="grievance_redressal"),
    path(
        "shipping-delivery-policy/",
        legal_page,
        {"slug": "shipping-delivery-policy"},
        name="shipping_delivery_policy",
    ),
    path(
        "academic-integrity/",
        legal_page,
        {"slug": "academic-integrity-policy"},
        name="academic_integrity_policy",
    ),
    path("privacy/request/", privacy_request, name="privacy_request"),
    path("privacy/request/received/", privacy_request_received, name="privacy_request_received"),
    path("legal/<slug:slug>/", legal_page, name="legal_page"),
]
