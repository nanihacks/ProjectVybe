"""Draft wording for online payments (Phase 3). Drafts only: nothing here goes live until
the owner reviews it with a lawyer and presses Publish in Admin."""

REFUND_POLICY = """ProjectVybe sells digital projects and services. Please read this policy before you pay.

## Payments are generally non-refundable

Because projects and add-ons are digital and are delivered shortly after payment, payments are generally non-refundable once you have paid.

## You can still ask for a refund

If something went wrong, you can submit a [refund request](/orders/refund-request/). Tell us your order reference, the email address you used, and what happened. We review every request fairly and reply by email within 5 working days.

We look in particular at cases where:

- you were charged but the order was not delivered,
- what you received is not what was described on the project page, or
- you were charged more than once for the same order.

We may ask for more detail, and we decide each request on its facts. Nothing in this policy limits any right you have under applicable consumer law.

## If a refund is approved

Approved refunds are sent to the original payment method through Razorpay. Your bank usually takes 5 to 7 working days to show the money. We email you when the refund has been processed.

## Enquiries

Submitting an enquiry through the website is not a payment and does not create an order. Payments are made only through the online checkout, and each paid order gets an order reference and a payment receipt.

## Questions

For questions about an order or a refund, contact [{contact_email}](mailto:{contact_email}) and quote your order reference.

## Changes

If we change how payments or refunds work, we will update this policy and the date at the top."""

SHIPPING_POLICY = """ProjectVybe provides digital projects, documentation, training, mentorship and software services. Nothing is shipped physically, so there are no courier charges or delivery addresses.

## Delivery after online payment

When you pay online you choose how you want to receive your order: by email, on WhatsApp, or as a Google Drive link.

We aim to deliver **within 2 hours** of your payment during our business hours. If you pay outside business hours, or the time would run past closing, we deliver by 2 hours after we open on the next working day. Add-ons can extend this by the extra time shown next to them at checkout. We show the delivery time on your order page and in your payment email.

Our business hours and working days are shown on the website and may be changed from time to time. Delivery times are our commitment as shown on your order, but they depend on the details you provided being correct and on your inbox or WhatsApp being able to receive the files.

## Other work

For training, mentorship, software development and custom work, delivery is arranged for each engagement and confirmed with you in writing before work begins.

## If something is missing or late

If you have not received your order by the time we promised, or what you received does not open or is incomplete, email [{contact_email}](mailto:{contact_email}) with your order reference. We will look into it and tell you what we will do.

## Keeping your files safe

Delivery links may expire. Please download your files promptly and keep your own copy.

## Changes to this policy

We may update this policy when our services change. The date at the top shows when it last changed."""

TERMS_REPLACEMENTS = [
    (
        " These terms are written for the current enquiry-led website and do not create an online purchase or checkout process.",
        " Some projects can be bought online through checkout; the section on online purchases below applies when you do.",
    ),
]

TERMS_ADDITION = """

## Online purchases

Where a project shows a price and a checkout button, you can buy it online. Prices are in Indian rupees (INR) and are shown on the project page. The price you pay is the total shown at checkout for the project and any add-ons you choose. Full payment is taken upfront, through Razorpay, our payment provider. We do not store your card, UPI or bank details.

An order is confirmed when your payment succeeds. We then issue a payment receipt and deliver your order as described in our Shipping & Delivery Policy. Refunds are handled under our Refund Policy. Enquiries that do not go through checkout are not online purchases.

We may cancel an order and refund you if we cannot deliver it, for example because of an error in the price or the description."""

PRIVACY_ADDITION = """

## Online orders and payments

If you buy through checkout, we collect your name, email address and phone number, the items you ordered, your chosen delivery method, and the payment reference and status. Payment is processed by Razorpay, which receives the payment details you enter on its secure payment window. ProjectVybe does not see or store your full card, UPI or bank details.

We use this information to take payment, deliver your order, send your receipt and respond to refund requests. We keep order and payment records for 8 years, because tax and accounting rules require us to keep them. Order records are not removed by the 24-month enquiry retention period above."""

UPDATES = {
    "refund-policy": ("replace", REFUND_POLICY),
    "shipping-delivery-policy": ("replace", SHIPPING_POLICY),
    "terms-and-conditions": ("terms", TERMS_ADDITION),
    "privacy-policy": ("append", PRIVACY_ADDITION),
}


def updated_draft(slug, current_body):
    """The new draft text for `slug`, built from the current draft."""
    mode, text = UPDATES[slug]
    if mode == "replace":
        return text
    body = current_body
    if mode == "terms":
        for old, new in TERMS_REPLACEMENTS:
            body = body.replace(old, new)
    return body.rstrip() + text
