# Billing and plans (extension guide)

The platform does not ship billing: it is the most product-specific part of a SaaS, and a wrong
default is expensive. What it ships are the seams to build it without fighting the base. This page
is the design, not a feature.

## The pieces you already have

| Need | Use |
|---|---|
| A customer is an organization | `Organization`, with `Membership.Role.BILLING` for the person who pays |
| Know what a plan allows | `apps.organizations.quotas.limit_for(organization, kind)`: replace its body with a lookup of the organization's plan and every call site follows |
| Switch a capability per customer | Feature flags with organization rules ([flags and settings](flags-and-settings.md)) |
| Receive the payment provider's events | A webhook **receiver** is your code; send your own state changes with the outbox ([webhooks](webhooks.md)) |
| Do work when a payment fails | A job or a flow ([add a flow](add-a-flow.md)), started from the receiver |
| Record who changed a plan | `record_event(action="billing.plan_changed", ...)`: the audit trail |

## A sound shape

1. **Model** (`billing` app, `OrganizationScopedModel`): `Subscription(plan, status, current_period_end,
   provider_customer_id)`. Classify it: the provider customer id is an identifier, the plan is not.
2. **Receiver**: one endpoint that verifies the provider's signature on the raw body *before*
   parsing, records the event id (so a retry is a no-op) and answers `2xx` fast. Do the work in a
   job. Outbound calls to the provider go through `apps.common.netguard` only if the URL is
   user-supplied; a fixed provider host does not need it but must still use TLS verification.
3. **Entitlements**: a single function `entitled(organization, capability) -> bool` reading the
   subscription, used by actions (raise `Forbidden(code="plan_required")`) and by
   `quotas.limit_for`. Never scatter plan names through the code.
4. **Grace and dunning**: status `past_due` keeps read access and blocks creation; a job
   downgrades after your grace period and emails the `billing` role.
5. **Taxes and invoices** (NF-e/NFS-e in Brazil) are a legal subject: use a provider that issues
   them and store only their ids.

## What not to do

- Do not store card data. Use the provider's hosted checkout; keep only ids and status.
- Do not trust a plan name sent by the client.
- Do not let a webhook payload decide an organization: resolve it from the provider customer id
  you stored.
- Do not make billing failures take the product down: entitlements fall back to the last known
  plan when the provider is unreachable.

## LGPD

Billing data is personal data of whoever pays (name, tax id, address). Classify the model, keep
what the tax law requires (`on_erase="keep"` with the legal duty as the reason) and anonymize the
rest on erasure. List the payment provider as a sub-processor with its country and transfer
mechanism.
