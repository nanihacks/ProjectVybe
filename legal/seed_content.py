"""Text the legal pages are created with (see legal/migrations/0002)."""

POLICIES = [
    {
        "slug": 'privacy-policy',
        "title": 'Privacy Policy',
        "hero_copy": 'This policy explains how the current ProjectVybe website may collect and use information when you browse the site or send an enquiry.',
        "seo_description": 'Read the ProjectVybe privacy policy and how enquiry information is handled.',
        "footer_label": 'Privacy policy',
        "footer_order": 10,
        "effective_date": '2026-10-18',
        "body_markdown": """ProjectVybe is designed as a public project catalogue and enquiry platform. This policy describes the current implementation and may be updated as the website develops.

## Information you may submit

When you use the enquiry form, the website may collect the information you choose to provide:

- Your name and email address
- Your phone number, if you provide one
- A selected published project, if applicable
- Selected active services, if applicable
- The message and project or service context you submit

We ask for these details only to respond to your enquiry. Please do not include sensitive personal information in your message.

## Your consent

Before you send an enquiry we ask you to agree to this Privacy Policy and to being contacted by WhatsApp, phone or email about that enquiry, and to confirm that you are 18 or older (or that a parent or guardian agrees). Updates about new projects and courses are optional, and we only send them if you tick that separate box. None of the boxes are ticked for you.

We keep a record of what you agreed to, the wording shown, the version of this policy and the date and time, so we can show that consent was given. Each enquiry is given a reference number (for example PV-1042) that you can quote when you contact us.

If you are under 18, please ask a parent or guardian to send the enquiry or to agree to it.

## Necessary technical processing

Django may process information needed to serve pages, protect forms against cross-site request forgery, and complete the enquiry confirmation flow. To prevent spam and abuse, your IP address is used briefly in the server's memory to limit how many enquiries and searches can be sent in a short time; it is not stored with your enquiry. The current website does not include analytics, advertising pixels, or marketing tracking systems.

## How information may be used

Information submitted through an enquiry is used to respond to you, understand the requested project or service, keep a record of the enquiry, send you a confirmation email, and continue the conversation by WhatsApp, phone or email. We send you updates about new projects and courses only if you opted in. We do not sell your information.

## Storage and retention

Enquiries are stored as records in the ProjectVybe database, which is accessible only to authorised ProjectVybe staff. We keep an enquiry for up to 24 months after it is received, unless you become a customer or the law requires us to keep it longer. After that we delete the record or remove your personal details from it.

## Third-party services

We use the following service providers (processors) to run the website. They process information only as needed to provide their service, under their own terms and privacy policies:

- **Render**: website hosting
- **Neon**: database where enquiries are stored
- **Resend**: delivery of enquiry notification and confirmation emails
- **Cloudinary**: public website and project images (your browser requests these when you view a page)
- **Cloudflare**: a security check (Turnstile) on forms, which helps us tell people from automated spam; it receives your IP address and browser details when the check runs
- **Meta (WhatsApp)**: if you choose to continue your enquiry on WhatsApp, your message is handled under WhatsApp's terms

Some of these providers may store or process data outside India. Project demonstration links may take you to YouTube, which has its own policies once you follow the link.

## Security

We use reasonable security practices, including encrypted connections, access controls on our admin area, and protections against automated form abuse. No online system can promise absolute security. If we become aware of a breach that affects your information, we will notify you and the authorities as the law requires.

## Your choices and rights

You can ask us at any time to show you the information we hold about you, correct it, delete it, or withdraw your consent, including consent to updates. The easiest way is the [privacy request form](/privacy/request/). You can also email [{contact_email}](mailto:{contact_email}), or reply STOP to any WhatsApp message from us. Withdrawing consent does not affect what we did before you withdrew it.

If you have a complaint about how your information is handled, see our [Grievance Redressal](/grievance-redressal/) page. We acknowledge complaints within 48 hours.

## Changes to this policy

This policy may be revised when the website, services, or information practices change. The updated version will be published on this page.""",
    },
    {
        "slug": 'terms-and-conditions',
        "title": 'Terms & Conditions',
        "hero_copy": 'These terms describe the current rules for using the ProjectVybe website and starting a project or service conversation.',
        "seo_description": 'Read the current ProjectVybe website terms and conditions for projects, services, and enquiries.',
        "footer_label": 'Terms & conditions',
        "footer_order": 20,
        "effective_date": '2026-09-09',
        "body_markdown": """By using this website, you agree to use it responsibly and to treat the information here as a starting point for discussion. These terms are written for the current enquiry-led website and do not create an online purchase or checkout process.

## Using the website

You may browse the catalogue, read project information, review active services, and submit genuine enquiries for lawful purposes. Do not interfere with the website, attempt unauthorised access, submit malicious content, or use the enquiry flow to abuse or mislead others.

## Project and service information

Project descriptions, demonstrations, technologies, requirements, and service descriptions are provided to help you understand what is available for discussion. Information may change, may be incomplete, and is not a promise that a particular project, service, feature, result, or timeline will be available.

## Enquiries and communication

An enquiry submitted through the website is a request to begin a conversation. It is not an order, purchase, contract, or confirmation of delivery. Project or service requirements, scope, availability, commercial terms, and any next steps are discussed separately through the available communication channels, including email and WhatsApp where applicable.

By submitting an enquiry, you acknowledge that ProjectVybe may use the contact information you provide to respond to your enquiry and send enquiry-related communications.

Documentation, PPT preparation, 1:1 mentorship, training, software development, and related support are subject to the details agreed for the particular engagement.

## Academic integrity

ProjectVybe may provide project development, technical guidance, training, documentation support, mentorship, and related educational services. Users are responsible for complying with the academic integrity, submission, authorship, and project-use policies of their educational institution. ProjectVybe does not guarantee acceptance, approval, grading, publication, or academic outcomes for any project or material.

## Intellectual property and materials

ProjectVybe content, including website text, design, and media, should not be copied, republished, or used without appropriate permission. You remain responsible for the materials and information you provide during a discussion and should have the right to share them. Ownership, licensing, and permitted use for any future deliverable should be addressed in the terms agreed for that engagement.

## Third-party links and services

The website may use or link to services such as Cloudinary for public media and YouTube for project demonstrations. Email delivery may also involve a third-party email service or email provider used by ProjectVybe. External services are governed by their own terms and policies. ProjectVybe is not responsible for changes to external websites or services.

## Accuracy and availability

Reasonable care is taken to maintain useful information, but the website is provided as available and information may contain omissions or become out of date. ProjectVybe may change, pause, or remove pages, projects, or services as the catalogue develops.

## Changes and contact

These terms may be updated when the website or business process changes. Questions about these terms can be sent to [{contact_email}](mailto:{contact_email}).""",
    },
    {
        "slug": 'refund-policy',
        "title": 'Refund / Cancellation Policy',
        "hero_copy": 'This policy explains how refund and cancellation questions relate to the current ProjectVybe enquiry and engagement process.',
        "seo_description": 'Read the ProjectVybe refund and cancellation policy for its current enquiry-led website model.',
        "footer_label": 'Refund / cancellation policy',
        "footer_order": 30,
        "effective_date": '2026-09-09',
        "body_markdown": """The current ProjectVybe website functions primarily as a project and service enquiry platform. It does not currently provide an online payment gateway, checkout, subscription billing, or automatic refund process.

## Enquiries are not online transactions

Submitting an enquiry does not itself create a payment transaction, purchase, contract, or confirmed paid engagement. Project and service requirements, availability, scope, and commercial terms are discussed and agreed separately before an engagement begins.

## Agreed engagement terms

If a project or service engagement is agreed, any applicable payment, cancellation, refund, rescheduling, revision, or service-specific terms should be clearly communicated and recorded in the agreement or other written communication for that engagement.

Those agreed terms will govern the particular engagement.

## Questions about an engagement

For questions about an agreed project or service engagement, contact [{contact_email}](mailto:{contact_email}) with enough context to identify the relevant conversation or engagement.

No fixed refund percentage, cancellation period, or universal refund outcome is stated here because the current website does not have one universal commercial policy.

## Future changes

If ProjectVybe introduces online payments or changes its commercial process, this policy will be reviewed and updated to reflect the actual process.""",
    },
    {
        "slug": 'cookie-policy',
        "title": 'Cookie Policy',
        "hero_copy": 'The current ProjectVybe website uses cookies and similar browser storage only where needed for core website functionality.',
        "seo_description": 'Learn about the necessary cookies used by the current ProjectVybe website.',
        "footer_label": 'Cookie policy',
        "footer_order": 40,
        "effective_date": '2026-09-09',
        "body_markdown": """A cookie is a small piece of information stored by your browser. ProjectVybe does not currently use analytics, advertising, marketing, or social tracking cookies.

## Necessary cookies

Django may use a session cookie when the website needs to maintain information between requests, including during the enquiry and confirmation flow.

The website may also use a CSRF cookie to help protect form submissions against cross-site request forgery.

These cookies support core website functionality and are not used to build an advertising or analytics profile.

## Third-party content and services

Public website and project images may be delivered through Cloudinary. Project demonstration links may take you to YouTube.

When your browser loads or interacts with third-party content or follows an external link, those services may use their own cookies or similar technologies. Their respective privacy and cookie policies apply to their services.

## Your browser controls

You can manage, block, or delete cookies through your browser settings.

Blocking necessary cookies may prevent some website functionality, including enquiry forms or confirmation steps, from working correctly.

## Questions

Questions about this Cookie Policy can be sent to [{contact_email}](mailto:{contact_email}).""",
    },
    {
        "slug": "grievance-redressal",
        "title": "Grievance Redressal",
        "hero_copy": "If something is wrong, tell us. This page explains how to raise a complaint and what you can expect from us.",
        "seo_description": "How to raise a complaint with ProjectVybe, who handles it, and how quickly we respond.",
        "footer_label": "Grievance redressal",
        "footer_order": 50,
        "effective_date": "2026-10-19",
        "body_markdown": """We want to hear about it when something goes wrong, whether it is about an enquiry, a project or service discussion, the website, or how your personal information is handled. This page explains how to reach us and what happens next.

## Who to contact

Please write to our Grievance Officer:

- Name: {grievance_officer_name}
- Email: [{grievance_officer_email}](mailto:{grievance_officer_email})
- Business name: {legal_name}
- Address: {registered_address}

## How to raise a complaint

Send an email to the address above with "Complaint" in the subject line, and include:

- Your name and the email address or phone number you used with us
- Your reference number (for example PV-1042), if you have one
- A clear description of the problem and what you would like us to do

Please do not send passwords, card numbers or other sensitive details.

## What happens next

- We will acknowledge your complaint within 48 hours.
- We aim to resolve it, or tell you what we are doing about it, within one month of receiving it.
- If it will take longer, we will tell you why and when to expect an answer.
- The reply will come from the Grievance Officer or someone acting on their behalf.

## Complaints about your personal information

To ask us to see, correct, delete or stop using your information, or to withdraw consent, use the [privacy request form](/privacy/request/). You can also email us at [{grievance_officer_email}](mailto:{grievance_officer_email}).

## If you are not satisfied

If you are not happy with our response, you may contact the National Consumer Helpline at consumerhelpline.gov.in, or any other authority that is competent to hear your complaint under the law.""",
    },
    {
        "slug": "shipping-delivery-policy",
        "title": "Shipping & Delivery Policy",
        "hero_copy": "ProjectVybe provides digital services. This page explains how and when work is delivered.",
        "seo_description": "How ProjectVybe delivers projects, documentation and mentorship, and how delivery time is agreed.",
        "footer_label": "Shipping & delivery policy",
        "footer_order": 60,
        "effective_date": "2026-10-19",
        "body_markdown": """ProjectVybe provides digital projects, documentation, training, mentorship and software services. Nothing is shipped physically, so there are no courier charges or delivery addresses.

## How work is delivered

Delivery is arranged for each engagement and confirmed with you in writing (by email or WhatsApp) before work begins. Depending on what you ask for, delivery may be:

- By email, as attachments or download links
- Through WhatsApp
- Through a shared online folder or a secure download link
- In live sessions, for training and mentorship

## Delivery time

The time needed depends on the scope of the work, how quickly you provide the information we need, and the current workload. We agree an expected delivery date with you before work starts. A delivery date is an estimate unless we have confirmed it in writing as a commitment.

The website is currently enquiry-led and does not take online payments. If online payment is introduced, this policy will be updated with the delivery times that apply to it.

## If something is missing or late

If you have not received what was agreed, or something you received does not open or is incomplete, email [{contact_email}](mailto:{contact_email}) with your reference number. We will look into it and tell you what we will do.

## Keeping your files safe

Delivery links may expire after a period we tell you about. Please download your files promptly and keep your own copy.

## Changes to this policy

We may update this policy when our services change. The date at the top shows when it last changed.""",
    },
    {
        "slug": "academic-integrity-policy",
        "title": "Academic Integrity Policy",
        "hero_copy": "ProjectVybe helps people learn. This page explains how our work may and may not be used.",
        "seo_description": "How ProjectVybe projects and services should be used responsibly for learning and reference.",
        "footer_label": "Academic integrity policy",
        "footer_order": 70,
        "effective_date": "2026-10-19",
        "body_markdown": """ProjectVybe exists to help people build skills. Our projects, documentation and mentorship are meant to be learned from, studied and used as a reference. This policy explains what that means in practice.

## How our projects should be used

- Use projects to understand how a system is built, to practise, and to prepare your own work.
- Read the code and documentation, run it, change it, and make it your own.
- Treat a project as a starting point for learning, not as a finished piece of work to hand in as yours.

## Your responsibility

You are responsible for following the academic integrity, submission and authorship rules of your school, college, university or employer. If your institution requires work to be entirely your own, you must not submit ProjectVybe material as your own work, and you must credit any help you are allowed to use.

## What we will not do

- Write theses, dissertations, assignments, papers or exam answers for you to submit as your own work.
- Take exams or assessments for you.
- Help hide or disguise where work came from.
- Promise grades, approval, acceptance for publication or any other academic result.

## What we are happy to do

- Explain concepts and how a project works.
- Guide you through building your own project and review your progress.
- Help you prepare documentation and presentations about work you have done.
- Mentor you through technical problems and career questions.

## Publication and documentation support

Where we help with documentation or publication material, the ideas, results and authorship must be yours, and you must follow the rules of the institution or publisher you are submitting to.

## Concerns

If you think our materials are being misused, or you have a question about what is acceptable, email [{contact_email}](mailto:{contact_email}). We may decline or stop any request that we believe goes against this policy.""",
    },
]
