from django.urls import path

from . import views


app_name = "leads"

urlpatterns = [
    path("", views.enquiry, name="enquiry"),
    path("success/", views.enquiry_success, name="success"),
]
