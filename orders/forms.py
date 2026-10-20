import re

from django import forms

from core.validators import StrictEmailField, StrictPhoneField

from .models import Order, RefundRequest


CONSENT_REQUIRED_ERROR = "Please tick this box to continue."
CONSENT_TERMS_LABEL = "I have read and agree to the Terms and Conditions and the Refund Policy."
CONSENT_CONTACT_LABEL = (
    "I agree to the Privacy Policy and to ProjectVybe contacting me by email, phone or "
    "WhatsApp about this order."
)
CONSENT_AGE_LABEL = "I am 18 or older, or my parent or guardian agrees to me sharing these details."
CONSENT_MARKETING_LABEL = "Send me occasional updates about new projects and courses."

HONEYPOT = forms.TextInput(
    attrs={
        "class": "form-honeypot__input",
        "tabindex": "-1",
        "autocomplete": "off",
        "aria-hidden": "true",
    }
)


def _mark_invalid_fields(form):
    for field_name in form.errors:
        if field_name not in form.fields or field_name == "website":
            continue
        described_by = []
        if form.fields[field_name].help_text:
            described_by.append(f"id_{field_name}_help")
        described_by.append(f"id_{field_name}_error")
        form.fields[field_name].widget.attrs["aria-invalid"] = "true"
        form.fields[field_name].widget.attrs["aria-describedby"] = " ".join(described_by)


class AddonIdsField(forms.MultipleChoiceField):
    """Accepts any list of ids; services.build_cart checks them against the database."""

    def valid_value(self, value):
        return True


class CheckoutForm(forms.Form):
    name = forms.CharField(max_length=120, widget=forms.TextInput(attrs={"autocomplete": "name"}))
    email = StrictEmailField(help_text="Your receipt and delivery details are sent here.")
    phone = StrictPhoneField()
    delivery_channel = forms.ChoiceField(
        choices=Order.Channel.choices,
        initial=Order.Channel.EMAIL,
        widget=forms.RadioSelect,
        label="How should we deliver it?",
    )
    addons = AddonIdsField(required=False, widget=forms.CheckboxSelectMultiple)
    # Consent boxes are never pre-ticked.
    consent_terms = forms.BooleanField(
        label=CONSENT_TERMS_LABEL, error_messages={"required": CONSENT_REQUIRED_ERROR}
    )
    consent_contact = forms.BooleanField(
        label=CONSENT_CONTACT_LABEL, error_messages={"required": CONSENT_REQUIRED_ERROR}
    )
    consent_age = forms.BooleanField(
        label=CONSENT_AGE_LABEL, error_messages={"required": CONSENT_REQUIRED_ERROR}
    )
    consent_marketing = forms.BooleanField(required=False, label=CONSENT_MARKETING_LABEL)
    website = forms.CharField(required=False, label="", widget=HONEYPOT)

    def clean_name(self):
        return " ".join(self.cleaned_data["name"].split())

    def clean(self):
        cleaned = super().clean()
        _mark_invalid_fields(self)
        if cleaned.get("website"):
            raise forms.ValidationError("This order could not be submitted.")
        return cleaned

    def consent_text(self):
        return "\n".join(
            [
                f"[required] {CONSENT_TERMS_LABEL}",
                f"[required] {CONSENT_CONTACT_LABEL}",
                f"[required] {CONSENT_AGE_LABEL}",
                f"[optional] {CONSENT_MARKETING_LABEL}",
            ]
        )


class RefundRequestForm(forms.ModelForm):
    reference = forms.CharField(
        max_length=20,
        label="Order reference",
        help_text="For example PVO-1042, from your payment email.",
    )
    email = StrictEmailField(label="Email used for the order")
    website = forms.CharField(required=False, label="", widget=HONEYPOT)

    class Meta:
        model = RefundRequest
        fields = ("reference", "email", "reason")
        labels = {"reason": "Why are you asking for a refund?"}
        widgets = {
            "reason": forms.Textarea(attrs={"rows": 5}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name != "website" and field.help_text:
                field.widget.attrs["aria-describedby"] = f"id_{name}_help"

    def clean_reference(self):
        reference = self.cleaned_data["reference"].strip().upper()
        if not re.fullmatch(r"PVO-\d{4,10}", reference):
            raise forms.ValidationError("Enter a reference like PVO-1042.")
        return reference

    def clean_reason(self):
        reason = self.cleaned_data["reason"].strip()
        if len(reason) < 10:
            raise forms.ValidationError("Please give at least 10 characters so we can review it.")
        return reason

    def clean(self):
        cleaned = super().clean()
        _mark_invalid_fields(self)
        if cleaned.get("website"):
            raise forms.ValidationError("This request could not be submitted.")
        return cleaned
