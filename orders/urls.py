from django.urls import path

from . import views


app_name = "orders"

urlpatterns = [
    path("checkout/verify/", views.verify, name="verify"),
    path("checkout/<slug:slug>/", views.checkout, name="checkout"),
    path("orders/refund-request/", views.refund_request, name="refund_request"),
    path("orders/refund-request/received/", views.refund_request_received, name="refund_request_received"),
    path("orders/<uuid:token>/", views.detail, name="detail"),
    path("orders/<uuid:token>/pay/", views.pay, name="pay"),
    path("orders/<uuid:token>/failed/", views.failed, name="failed"),
    path("orders/<uuid:token>/retry/", views.retry, name="retry"),
    path("orders/<uuid:token>/receipt/", views.receipt, name="receipt"),
    path("payments/razorpay/webhook/", views.webhook, name="webhook"),
]
