"""Strict phone and email checks shared by every public form.

The browser gets matching hints (see `PHONE_PATTERN`), but these functions are the real rules: they run on
the server and return the cleaned value that gets stored.
"""

import re

from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import validate_email


# ---- Phone ------------------------------------------------------------------------------------------

# An Indian mobile: optional +91 / 91 / 0, then 10 digits starting 6-9.
_INDIAN_MOBILE = re.compile(r"^(?:\+?91|0)?([6-9]\d{9})$")
# Any other country: must start with + and a country code, 8-15 digits in all (E.164).
_INTERNATIONAL = re.compile(r"^\+([1-9]\d{7,14})$")
_ALLOWED_CHARS = re.compile(r"^[0-9+\s().\-]+$")

# Shown to the browser as the `pattern` attribute. It is a hint only; the server decides.
PHONE_PATTERN = r"(?:(?:\+91|91|0)?[\s\-]?[6-9][0-9]{4}[\s\-]?[0-9]{5})|(?:\+(?!91)[1-9][0-9\s\-]{7,18})"
PHONE_HELP = "Enter a 10-digit Indian mobile number (starting 6-9), or an international number starting with +."

_OBVIOUS_FAKES = {"1234567890", "0123456789"}


def clean_phone(value, *, label="phone number"):
    """Return the number as `+91XXXXXXXXXX` (India) or `+<digits>` (elsewhere), or raise ValidationError."""
    raw = (value or "").strip()
    if not raw:
        raise ValidationError(f"Enter your {label}.")
    if not _ALLOWED_CHARS.fullmatch(raw):
        raise ValidationError(f"Use digits only for your {label}. A leading + is fine.")

    # Spaces, dashes, dots and brackets are only for readability; what is left must be digits, with at
    # most one + at the very start.
    compact = re.sub(r"[\s().\-]", "", raw)
    if not re.fullmatch(r"\+?\d+", compact):
        raise ValidationError(f"Use digits only for your {label}. A leading + is fine.")

    indian = _INDIAN_MOBILE.fullmatch(compact)
    if indian and not (compact.startswith("+") and not compact.startswith("+91")):
        national = indian.group(1)
        if len(set(national)) == 1 or national in _OBVIOUS_FAKES:
            raise ValidationError(f"That {label} does not look real. Please check it.")
        return f"+91{national}"

    if compact.startswith("+"):
        international = _INTERNATIONAL.fullmatch(compact)
        if international and not compact.startswith("+91"):
            return compact

    raise ValidationError(
        f"Enter a valid {label}: 10 digits starting with 6, 7, 8 or 9, or an international number starting with +."
    )


# ---- Email ------------------------------------------------------------------------------------------

_LOCAL_PART = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9._%+\-]*[A-Za-z0-9])?$")
_DOMAIN_LABEL = re.compile(r"^(?!-)[a-z0-9-]{1,63}(?<!-)$")
_TLD = re.compile(r"^(?:[a-z]{2,24}|xn--[a-z0-9-]{2,59})$")


def clean_email(value):
    """Return the address trimmed and lower-cased, or raise ValidationError for anything odd."""
    address = (value or "").strip().lower()
    message = "Enter a valid email address, like name@example.com."
    if not address or len(address) > 254 or any(ch.isspace() for ch in address):
        raise ValidationError(message)
    try:
        validate_email(address)
    except ValidationError:
        raise ValidationError(message) from None

    local, _, domain = address.rpartition("@")
    if not local or not domain or len(local) > 64:
        raise ValidationError(message)
    if ".." in local or not _LOCAL_PART.fullmatch(local):
        raise ValidationError(message)

    labels = domain.split(".")
    if len(labels) < 2 or not all(_DOMAIN_LABEL.fullmatch(label) for label in labels):
        raise ValidationError(message)
    if not _TLD.fullmatch(labels[-1]):
        raise ValidationError(message)
    return address


# ---- Form fields ------------------------------------------------------------------------------------


class StrictEmailField(forms.EmailField):
    """An email field that applies `clean_email` and stores the lower-cased address."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("max_length", 254)
        kwargs.setdefault(
            "widget",
            forms.EmailInput(
                attrs={
                    "autocomplete": "email",
                    "inputmode": "email",
                    "autocapitalize": "off",
                    "spellcheck": "false",
                    "placeholder": "you@example.com",
                }
            ),
        )
        super().__init__(*args, **kwargs)

    def clean(self, value):
        value = super().clean(value)
        return clean_email(value) if value else value


class StrictPhoneField(forms.CharField):
    """A phone field that applies `clean_phone`. Set required=False to allow it to be left blank."""

    def __init__(self, *args, label_text="phone number", **kwargs):
        self.label_text = label_text
        kwargs.setdefault("max_length", 20)
        kwargs.setdefault(
            "widget",
            forms.TextInput(
                attrs={
                    "autocomplete": "tel",
                    "inputmode": "tel",
                    "placeholder": "WhatsApp or mobile number",
                    "pattern": PHONE_PATTERN,
                    "title": PHONE_HELP,
                    "maxlength": "20",
                }
            ),
        )
        super().__init__(*args, **kwargs)

    def clean(self, value):
        value = super().clean(value)
        if not value:
            return ""
        return clean_phone(value, label=self.label_text)
