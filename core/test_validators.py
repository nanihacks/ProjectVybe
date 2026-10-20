from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from courses.forms import WaitlistForm
from leads.forms import LeadForm, PrivacyRequestForm
from orders.forms import CheckoutForm, RefundRequestForm

from .validators import clean_email, clean_phone


class PhoneRuleTests(SimpleTestCase):
    def test_indian_mobiles_are_accepted_and_normalised(self):
        cases = {
            "9876543210": "+919876543210",
            "98765 43210": "+919876543210",
            "98765-43210": "+919876543210",
            "+91 98765 43210": "+919876543210",
            "+91-98765-43210": "+919876543210",
            "919876543210": "+919876543210",
            "09876543210": "+919876543210",
            "(+91) 6123 456 789": "+916123456789",
            " 7012345678 ": "+917012345678",
        }
        for typed, stored in cases.items():
            self.assertEqual(clean_phone(typed), stored, typed)

    def test_international_numbers_need_a_plus_and_a_country_code(self):
        self.assertEqual(clean_phone("+1 415 555 2671"), "+14155552671")
        self.assertEqual(clean_phone("+44 7911 123456"), "+447911123456")
        self.assertEqual(clean_phone("+971 50 123 4567"), "+971501234567")

    def test_bad_numbers_are_rejected(self):
        bad = [
            "",
            "12",
            "123456",
            "5876543210",  # Indian mobiles start with 6-9
            "987654321",  # 9 digits
            "98765432101",  # 11 digits, no country code
            "+91 12345 67890",
            "9999999999",  # one repeated digit
            "1234567890",
            "abcdefghij",
            "98765 4321a",
            "98765++43210",
            "98765+43210",
            "+0 1234567890",
            "+1 23",
            "+9198765432101234",
            "<script>alert(1)</script>",
            "9876543210; DROP TABLE",
        ]
        for value in bad:
            with self.assertRaises(ValidationError, msg=repr(value)):
                clean_phone(value)


class EmailRuleTests(SimpleTestCase):
    def test_good_addresses_are_accepted_and_lower_cased(self):
        cases = {
            "Name@Example.com": "name@example.com",
            "  first.last+tag@sub.example.co.in ": "first.last+tag@sub.example.co.in",
            "a_b-c@my-domain.org": "a_b-c@my-domain.org",
            "x@xn--bcher-kva.example": "x@xn--bcher-kva.example",
        }
        for typed, stored in cases.items():
            self.assertEqual(clean_email(typed), stored, typed)

    def test_bad_addresses_are_rejected(self):
        bad = [
            "",
            "plain",
            "no-at-sign.com",
            "@example.com",
            "name@",
            "name@example",  # no dot
            "name@example.c",  # one-letter TLD
            "name@example.123",  # numeric TLD
            "name@-example.com",
            "name@example-.com",
            "name@exa mple.com",
            "na me@example.com",
            "name..dots@example.com",
            ".name@example.com",
            "name.@example.com",
            "name@example..com",
            "name@[127.0.0.1]",
            "name@127.0.0.1",
            "a" * 65 + "@example.com",
            "a@" + "b" * 250 + ".com",
            "name@example.com,other@example.com",
            "name@example.com\nBcc: x@example.com",
            '"quoted"@example.com',
            "name(comment)@example.com",
        ]
        for value in bad:
            with self.assertRaises(ValidationError, msg=repr(value)):
                clean_email(value)


class FormIntegrationTests(SimpleTestCase):
    def test_every_public_form_rejects_a_bad_phone_and_email(self):
        checkout = CheckoutForm(
            {"name": "A B", "email": "bad@", "phone": "12345", "delivery_channel": "email"}
        )
        self.assertFalse(checkout.is_valid())
        self.assertIn("email", checkout.errors)
        self.assertIn("phone", checkout.errors)

        waitlist = WaitlistForm({"name": "A B", "email": "bad@example", "phone": "55555"})
        self.assertFalse(waitlist.is_valid())
        self.assertIn("email", waitlist.errors)
        self.assertIn("phone", waitlist.errors)

        refund = RefundRequestForm({"reference": "PVO-1001", "email": "x@y", "reason": "I want a refund."})
        self.assertFalse(refund.is_valid())
        self.assertIn("email", refund.errors)

        privacy = PrivacyRequestForm({"kind": "access", "email": "nope"})
        self.assertFalse(privacy.is_valid())
        self.assertIn("email", privacy.errors)

    def test_lead_form_stores_the_clean_values(self):
        form = LeadForm(
            {
                "name": "A B",
                "email": "  Visitor@Example.COM ",
                "phone": "98765 11111",
                "message": "Tell me more about this.",
                "consent_contact": "on",
                "consent_age": "on",
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["email"], "visitor@example.com")
        self.assertEqual(form.cleaned_data["phone"], "+919876511111")

    def test_optional_phone_may_be_blank_but_not_junk(self):
        base = {
            "name": "A B",
            "email": "v@example.com",
            "message": "Tell me more about this.",
            "consent_contact": "on",
            "consent_age": "on",
        }
        self.assertTrue(LeadForm({**base, "phone": ""}).is_valid())
        junk = LeadForm({**base, "phone": "hello"})
        self.assertFalse(junk.is_valid())
        self.assertIn("phone", junk.errors)

    def test_browser_hints_are_present(self):
        form = LeadForm()
        phone_attrs = form.fields["phone"].widget.attrs
        self.assertEqual(phone_attrs["inputmode"], "tel")
        self.assertIn("pattern", phone_attrs)
        email_attrs = form.fields["email"].widget.attrs
        self.assertEqual(email_attrs["inputmode"], "email")
        self.assertEqual(email_attrs["autocapitalize"], "off")
