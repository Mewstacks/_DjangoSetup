# ADR 17: Who is the controller, and whose request is it

**Status:** accepted as guidance; the data model is **not** split by role yet.

## Context

LGPD distinguishes the **controller** (decides purposes and means) from the **operator** (processes
on the controller's behalf) (arts. 5, 37, 39, 42). In a multi-tenant product both appear:

- For its own customers' accounts, billing and security records, the **platform owner is the
  controller**.
- For the data a customer's members put into the product, the **customer organization is the
  controller** and the platform owner the **operator**.

The platform's `DataSubject` and `DataSubjectRequest` are global, not scoped to an organization:
one person, one record, one place to ask.

## Decision

- Document the split (this ADR, the offboarding guide, the data-processing-agreement template) and
  have the customer contract state it. Code does not decide it.
- Keep requests global for **platform-controller** data. For **operator** data, the platform owner
  forwards the request to the customer organization (the DPA fixes the time limit) and provides the
  executors (export, erase, block) the organization uses.
- Defer a per-organization privacy profile (controller name, DPO, notice URL per tenant) until a
  customer needs to publish its own: the transparency endpoint publishes the platform owner's.

## Consequences

- Erasure of a person reaches every organization they belong to, because the person is global. A
  product where one person can be a member of unrelated customers should decide, with counsel,
  whether a request from one customer's member may touch another customer's data. The default (it
  may not for operator data; it may for platform-controller data) needs a per-model flag in the
  catalog if you need that precision.
- This is the point most worth a lawyer's time before the first customer.
