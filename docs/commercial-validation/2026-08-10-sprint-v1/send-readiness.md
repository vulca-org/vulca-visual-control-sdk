# Send Readiness

Overall status: `BLOCKED_BEFORE_EXTERNAL_SEND`

Preparation may continue. No first-touch, follow-up, form submission, LinkedIn
message, calendar booking, or test email is authorised by this document.

## 1. Sender-Domain Gate

Read-only DNS observation on 2026-08-10:

- MX records point to Namecheap forwarding hosts
  (`eforward1`–`eforward5.registrar-servers.com`).
- the root SPF record is `v=spf1 include:spf.efwd.registrar-servers.com ~all`;
- no DMARC TXT record was returned for `_dmarc.vulcaart.art`;
- outbound DKIM and an authorised SMTP/send-as path were not verified;
- the previous commercial campaign was sent from `yuhaorui48@gmail.com`, and a
  read-only Gmail search found no sent messages from `founder@vulcaart.art`.

Interpretation: inbound forwarding may be configured, but the evidence does
not establish that `founder@vulcaart.art` can send authenticated mail or receive
and preserve replies correctly. Do not use the founder address for outreach
until an end-to-end test passes.

Required evidence:

- [ ] choose and document the outbound mail provider;
- [ ] publish provider-authorised SPF without breaking forwarding;
- [ ] publish and verify DKIM;
- [ ] publish a DMARC policy and reporting address;
- [ ] send one authorised test to an owned external inbox;
- [ ] inspect `From`, `Return-Path`, SPF, DKIM, and DMARC results;
- [ ] reply from the external inbox and confirm the founder mailbox receives
      the response;
- [ ] confirm Gmail or the selected client sends replies from the intended
      identity.

## 2. Prospect Gate

- [ ] company is not in `prior-outreach-exclusions.csv`;
- [ ] company is currently active;
- [ ] named person's current role is supported by a public source;
- [ ] role is close to creative operations, production, creative technology,
      AI innovation, or an accountable founder;
- [ ] route is public and current; no guessed personal email;
- [ ] form route explicitly permits a partnership or business enquiry and is
      not a customer-support-only channel;
- [ ] one company-specific workflow trigger is recorded;
- [ ] no bounced route is reused.

## 3. Message Gate

- [ ] under approximately 100 English words before signature;
- [ ] no attachment on first touch;
- [ ] one specific observation, one tested pain, one concrete pilot;
- [ ] no customer, outcome, approval, compliance, or model-learning claim;
- [ ] asks for the correct owner or one small workflow check;
- [ ] clearly identifies VULCA and gives a valid reply-based opt-out;
- [ ] includes the production website once, without an academic link stack;
- [ ] does not promise “I will not follow up” if one follow-up is planned;
- [ ] one follow-up maximum after 4–5 working days.

## 4. Batch Gate

- [ ] first cohort limited to 10 named people;
- [ ] every draft reviewed together before sending;
- [ ] explicit user approval records which drafts and routes may be used;
- [ ] tracker is updated immediately after each send;
- [ ] stop the cohort on any unexpected bounce cluster or sender warning;
- [ ] do not start cohort two until cohort one has been reviewed.

## 5. Direct-Marketing And Suppression Gate

Status: `NOT_REVIEWED_FOR_SEND`

The cohort spans more than one jurisdiction. A public business route does not
by itself establish permission to send. The current UK ICO guidance also notes
that corporate and individual subscribers are treated differently, that UK
GDPR can still apply when a named business contact's personal data is used,
and that the sender must identify itself and provide a valid opt-out route:
<https://ico.org.uk/for-organisations/direct-marketing-and-privacy-and-electronic-communications/business-to-business-marketing/>.

- [ ] identify the recipient legal entity and country before each send;
- [ ] verify whether it is a corporate subscriber, sole trader, partnership,
      or another protected recipient type;
- [ ] document the applicable lawful basis and a proportionate legitimate-
      interests assessment where relevant;
- [ ] verify any country- or state-specific electronic-marketing requirement;
- [ ] provide the required transparency/privacy information for named-contact
      data sourced from public pages;
- [ ] confirm that the public VULCA privacy notice used for outreach covers
      prospecting data; the local ChatGPT App privacy policy is not enough;
- [ ] include a valid opt-out method and honour it immediately;
- [ ] maintain a suppression list and screen every new batch against it;
- [ ] never promote an opted-out, bounced, or disputed route back into a batch.

This checklist is an operational guardrail, not legal advice. External sending
remains blocked until the user has reviewed the intended jurisdictions and the
required records exist.

## 6. Evidence And Pilot-Privacy Gate

- [ ] demo/sample is visibly marked fictional or public-case;
- [ ] customer/design-partner status is not inferred from a reply;
- [ ] no sensitive asset enters a pilot without explicit handling permission;
- [ ] AI-assisted decisions remain draft until human confirmation is recorded;
- [ ] second-batch reuse is called workflow memory, not proven continual
      learning;
- [ ] any public case-study permission is separate from pilot participation.
