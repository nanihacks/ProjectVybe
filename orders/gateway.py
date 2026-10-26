"""Razorpay REST calls using only the standard library (same approach as core/turnstile.py)."""

import base64
import hashlib
import hmac
import json
import logging
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings


logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 10


class GatewayError(Exception):
    """The payment provider could not be reached or refused the request."""


def _hmac_hex(secret, message):
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


class RazorpayGateway:
    """Small provider interface: swap this class to move to another gateway later."""

    def __init__(self, key_id=None, key_secret=None, webhook_secret=None):
        self.key_id = settings.RAZORPAY_KEY_ID if key_id is None else key_id
        self.key_secret = settings.RAZORPAY_KEY_SECRET if key_secret is None else key_secret
        self.webhook_secret = settings.RAZORPAY_WEBHOOK_SECRET if webhook_secret is None else webhook_secret

    @property
    def is_configured(self):
        return bool(self.key_id and self.key_secret)

    @property
    def is_test_mode(self):
        return self.key_id.startswith("rzp_test_")

    def _request(self, method, path, payload=None):
        if not self.is_configured:
            raise GatewayError("Razorpay keys are not configured.")
        token = base64.b64encode(f"{self.key_id}:{self.key_secret}".encode()).decode()
        data = json.dumps(payload).encode() if payload is not None else None
        request = Request(
            f"{settings.RAZORPAY_API_BASE}{path}",
            data=data,
            method=method,
            headers={"Authorization": f"Basic {token}", "Content-Type": "application/json"},
        )
        try:
            with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                return json.load(response)
        except HTTPError as error:
            # The body explains the refusal but never contains our secret.
            logger.warning("Razorpay %s %s failed: %s %s", method, path, error.code, error.read()[:300])
            raise GatewayError(f"Razorpay returned {error.code}") from error
        except (URLError, OSError, ValueError) as error:
            logger.warning("Razorpay %s %s unreachable: %s", method, path, error)
            raise GatewayError("Razorpay could not be reached.") from error

    def create_order(self, amount_paise, receipt, notes=None):
        return self._request(
            "POST",
            "/orders",
            {"amount": amount_paise, "currency": "INR", "receipt": receipt, "notes": notes or {}},
        )

    def fetch_payment(self, payment_id):
        return self._request("GET", f"/payments/{payment_id}")

    def capture_payment(self, payment_id, amount_paise):
        return self._request(
            "POST", f"/payments/{payment_id}/capture", {"amount": amount_paise, "currency": "INR"}
        )

    def refund(self, payment_id, amount_paise, notes=None):
        return self._request(
            "POST", f"/payments/{payment_id}/refund", {"amount": amount_paise, "notes": notes or {}}
        )

    def verify_payment_signature(self, order_id, payment_id, signature):
        if not (self.key_secret and order_id and payment_id and signature):
            return False
        expected = _hmac_hex(self.key_secret, f"{order_id}|{payment_id}".encode())
        return hmac.compare_digest(expected, str(signature))

    def verify_webhook_signature(self, raw_body, signature):
        if not (self.webhook_secret and signature):
            return False
        return hmac.compare_digest(_hmac_hex(self.webhook_secret, raw_body), str(signature))


def get_gateway():
    return RazorpayGateway()
