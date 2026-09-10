from django.urls import path

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
    path("privacy/", views.privacy_policy, name="privacy_policy"),
    path("terms/", views.terms, name="terms"),
    path("refund-policy/", views.refund_policy, name="refund_policy"),
    path("cookies/", views.cookies, name="cookies"),
]
