# Privacy Notice — {{Product name}}

> **A template, not legal advice.** Adapt it to your real processing and have a lawyer with LGPD
> experience review it before you publish. Delete this note and the items that do not apply.
> Version {{version}}, effective {{date}}.

## 1. Who is responsible

**Controller:** {{Legal name}}, CNPJ {{tax id}}, {{address}}.
**Data protection officer (DPO):** {{name}}, {{e-mail}} / {{contact URL}}.

When we process data of members of a customer organization we act as the **operator** and the
organization is the controller; requests about that data should go to them. {{Adjust to the contract.}}

## 2. What we process, why, and on what legal basis

| Purpose | Data | Legal basis (LGPD art. 7) | How long |
|---|---|---|---|
| Create and secure the account | e-mail, name, credentials, sessions, keys | contract | while the account exists + {{period}} |
| Provide the service | content you create in the product | contract | until deleted by the person or the contract ends |
| Security and audit trail | access records, address (hash only), actions | legal obligation / legitimate interest | {{AUDIT_RETENTION_DAYS}} days |
| Proof of compliance | consent and request records | legal obligation | {{period}} |
| {{Other}} | {{data}} | {{basis}} | {{period}} |

*Generate this table from `python manage.py privacy_ropa` and the registered purposes.*

## 3. Who we share it with

{{List of active processors and sub-processors: name, purpose, country, transfer mechanism.}}

**International transfer:** happens to {{countries}} under {{ANPD standard clauses / adequacy
decision / another art. 33 mechanism}} (Resolution CD/ANPD 19/2024).

## 4. Your rights (art. 18)

You may ask for: confirmation of processing; access; correction; anonymization, blocking or
deletion of unnecessary data or data processed unlawfully; portability; deletion of data processed
on consent; information on who we share data with; information on the possibility of refusing
consent and its consequences; withdrawal of consent.

How: {{form URL or endpoint}} or {{DPO e-mail}}. We answer within {{15}} days. Destructive requests
are confirmed by e-mail first.

## 5. Consent and cookies

We ask for consent only for purposes that need it, specifically and prominently. You can withdraw
it at any time as easily as you gave it. If you refuse: {{consequence of refusing, per purpose}}.
Cookie categories: {{necessary, preferences, analytics, marketing}}.

## 6. Children and teenagers

{{The product is not meant for people under 18 / We process the data of minors only with the
specific consent of a parent or guardian and with adequate age assurance (LGPD art. 14; Law
15,211/2025).}}

## 7. Security

Encryption in transit and, for sensitive fields, at rest; two-factor authentication; access
control per organization; a tamper-evident audit trail; backups kept for {{period}}. After an
incident with relevant risk we notify the ANPD and the people affected within the period set by
Resolution CD/ANPD 15/2024.

## 8. Changes and contact

We will tell you about relevant changes by {{means}}. Questions or complaints: {{DPO}}. You may
also complain to the ANPD (gov.br/anpd).
