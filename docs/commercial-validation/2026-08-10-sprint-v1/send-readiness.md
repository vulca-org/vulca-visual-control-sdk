# Send Readiness

Overall status: `ACTIVE_LIMITED_UK_CORPORATE_PILOT`

Updated: 2026-08-11

The sender-domain gate has passed and a six-company UK corporate-email pilot
has been sent. The active scope is limited to the public team or new-business
routes recorded in `outreach-tracker.csv`. Named-person cold outreach, non-UK
routes, official forms, LinkedIn messages, calendar bookings, and any second
cohort remain blocked until their separate route and jurisdiction checks pass.

## 1. Sender-Domain Gate

Status: `PASSED_2026-08-11`

- Namecheap Private Email Launch trial is active for
  `founder@vulcaart.art`; auto-renew is off.
- MX points to `mx1.privateemail.com` and `mx2.privateemail.com`.
- SPF authorises `spf.privateemail.com`.
- DKIM is published for the VULCA domain.
- DMARC is published with monitoring policy `p=none`, strict SPF/DKIM
  alignment, and aggregate reports to the founder mailbox.
- an external Mail-Tester check scored 8.9/10 and reported SPF, DKIM, and DMARC
  passes: <https://www.mail-tester.com/test-ms84shwp4>.
- the same test raised a SpamCop rule against one Namecheap shared relay IP.
  This is a provider-reputation warning, not evidence that VULCA's domain
  authentication failed.
- external inbound delivery to the founder mailbox and forwarding to the owned
  Gmail inbox were verified.
- Gmail Send As uses Namecheap SMTP, and the default compose identity is
  `Haorui | VULCA <founder@vulcaart.art>`.

Required evidence:

- [x] choose and document the outbound mail provider;
- [x] publish provider-authorised SPF;
- [x] publish and verify DKIM;
- [x] publish a DMARC policy and reporting address;
- [x] send an authorised external authentication test;
- [x] inspect SPF, DKIM, and DMARC results;
- [x] confirm external inbound mail reaches the founder mailbox and forwarding
      inbox;
- [x] confirm Gmail composes and sends from the intended founder identity.

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

- [x] first live cohort limited to six UK corporate team routes;
- [x] every live draft and route reviewed before sending;
- [x] explicit user approval records the required founder identity and send
      authority;
- [x] tracker updated after each send;
- [ ] stop the cohort on any unexpected bounce cluster or sender warning;
- [ ] do not start cohort two until cohort one has been reviewed.

## 5. Direct-Marketing And Suppression Gate

Status: `LIMITED_UK_CORPORATE_ROUTE_REVIEWED__OTHER_ROUTES_PENDING`

The full pool spans more than one jurisdiction. A public business route does
not by itself establish permission to send. The current UK ICO guidance notes
that corporate and individual subscribers are treated differently, that UK
GDPR can still apply when a named business contact's personal data is used,
and that the sender must identify itself and provide a valid opt-out route:
<https://ico.org.uk/for-organisations/direct-marketing-and-privacy-and-electronic-communications/business-to-business-marketing/>.

The first live cohort was therefore narrowed to public corporate routes for
six UK limited companies: Disrupt Marketing, Spin Brands, The Social Shepherd,
Coolr, We Are Social, and Nonsensical (operated by Updates Media Limited). Each
message used a company-team salutation, did not include a named employee or
inferred personal address, identified VULCA and its founder address, and
offered a reply-based opt-out. No attachment or tracking link was used.

The current VULCA privacy notice does not yet cover proactive named-contact
prospecting. Named-person outreach therefore remains blocked even when a role
is publicly listed. US, Australian, EEA, German, Nordic, and form-based routes
also remain pending jurisdiction-specific review.

- [x] identify the six first-cohort legal entities and UK routes;
- [x] limit the first cohort to corporate team or new-business subscribers;
- [x] avoid named-contact personal data in the live messages;
- [x] include a valid reply-based opt-out method;
- [x] screen the first cohort against the prior-outreach exclusion list;
- [ ] add proactive prospecting coverage before any named-person outreach;
- [ ] complete country- or state-specific review before any non-UK send;
- [ ] maintain and screen a durable opt-out suppression list before cohort two;
- [ ] never promote an opted-out, bounced, or disputed route back into a batch.

This checklist is an operational guardrail, not legal advice. External sending
outside the recorded six-company UK pilot remains blocked until the relevant
jurisdiction and route records exist.

## 6. Provider-Limit Gate

Status: `PILOT_ONLY`

- Namecheap's current Private Email trial limit is 20 messages per mailbox per
  hour: <https://www.namecheap.com/support/knowledgebase/article.aspx/10811/2306/new-email-sending-and-usage-limits-for-private-email/>.
- Namecheap's restrictions prohibit spam and require double opt-in for mass
  mailings: <https://www.namecheap.com/support/knowledgebase/article.aspx/133/22/do-you-have-any-restrictions-on-sending-out-emails/>.
- six individually reviewed company messages were sent in the first hour;
- a 90-recipient blast is not permitted on the current trial and is outside the
  approved one-to-one pilot path;
- stop on a provider warning, unexpected bounce cluster, or opt-out complaint.

## 7. Evidence And Pilot-Privacy Gate

- [ ] demo/sample is visibly marked fictional or public-case;
- [ ] customer/design-partner status is not inferred from a reply;
- [ ] no sensitive asset enters a pilot without explicit handling permission;
- [ ] AI-assisted decisions remain draft until human confirmation is recorded;
- [ ] second-batch reuse is called workflow memory, not proven continual
      learning;
- [ ] any public case-study permission is separate from pilot participation.
