# Snowcubes customer-opportunity authoring contract

This is a separate private decision aid, not a section of Leo's chief-of-staff
letter and not a CRM, queue, campaign, or mailbox draft. Rank only the exact
customer opportunities present in the supplied evidence. If Superhuman or
Shopify is unavailable, incomplete, ambiguous, or conflicting, return an empty
`UNKNOWN` result with the exact wake. Never infer a customer, order, delivery,
first-order status, waiting direction, inventory level, or permission to
contact from a subject line or from one provider alone.

Each ranked item contains only four reader-facing parts:

- why the opportunity matters now;
- exact Shopify customer, Shopify order, and Superhuman thread provenance;
- one recommended review step;
- short factual context that could later support a draft.

The factual context is not email copy. Do not write a subject, greeting,
message body, sign-off, coupon, promise, delivery assurance, or product claim.
Do not create or save a draft, send a message, open a provider, place an order,
change fulfillment, issue a refund, or mutate Shopify. A next step may ask Leo
to review or confirm an action, but must not instruct the system to perform a
protected action.

Every statement cites only exact `source_refs` belonging to the same customer
opportunity. Provenance must reproduce the exact provider IDs in the evidence:
one `shopify_customer`, one `shopify_order`, and one `superhuman_thread`. Never
merge facts across customers. Preserve evidence ordering only after making a
genuine model judgment about urgency and relationship value; do not sort by a
provider ID.

If complete evidence contains no eligible opportunities, return `CLEAR` with
no rows and no wake. If complete evidence contains eligible opportunities,
return `READY`, rank at least one row, and leave `exact_wake` null. If evidence
status is not complete, return `UNKNOWN`, no rows, and a concise exact wake that
names the missing read. Return only schema-valid JSON.
