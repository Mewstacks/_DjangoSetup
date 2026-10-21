# Data Processing Agreement (operator)

> **A template, not legal advice.** Use it when the **customer** is the controller and you are the
> operator (LGPD arts. 5, 37, 39 and 42). Have a lawyer review it. Version {{version}}.

**Controller (Customer):** {{legal name, tax id}}. **Operator ({{Company}}):** {{legal name, tax id}}.
**Operator's DPO:** {{name, contact}}.

## 1. Subject matter and instructions

The Operator processes personal data **only** to provide the contracted service and on the
Controller's documented instructions (this agreement, the contract and the product settings). If an
instruction would break the law, the Operator will say so.

## 2. Data and data subjects

| Data subjects | Categories of data | Nature and purpose | Duration |
|---|---|---|---|
| {{customer's users}} | {{identification, contact, content}} | {{store and process}} | contract term + {{period}} |

Sensitive personal data: {{not processed / which}}. Data of children and teenagers: {{no / under art. 14 rules}}.

## 3. Operator's obligations

1. Confidentiality: authorized people are bound to secrecy.
2. Security (art. 46): the measures in Annex I.
3. Sub-processors: listed in Annex II; {{period}} notice of changes, with a right to object.
4. Data subject rights: the Operator forwards requests it receives to the Controller within
   {{3}} business days and provides the tools to answer them (access, export, deletion, blocking).
5. Incidents: the Operator tells the Controller without undue delay, within {{48}} hours of
   becoming aware, with what it knows (nature, data, people, measures), so the Controller can meet
   art. 48 and Resolution CD/ANPD 15/2024.
6. Audit: the Operator provides information to show compliance and allows reasonable audits on
   notice and under confidentiality.
7. International transfer: only under an art. 33 mechanism (Resolution CD/ANPD 19/2024).

## 4. Termination

On termination the Operator returns the data in a structured format and deletes it within
{{period}}, except where the law requires retention, and confirms deletion in writing. Backups
expire within {{period}}.

## 5. Liability

{{As per the contract; LGPD art. 42 on the joint liability of an operator that breaks the law or
the controller's lawful instructions.}}

## Annex I — Security measures

Encryption in transit and at rest (sensitive fields); two-factor authentication; logical isolation
per organization; an audit log with a hash chain; separation of database roles; backups; restore
tests {{frequency}}; vulnerability and dependency management; incident response (runbooks).

## Annex II — Sub-processors

{{Generate from the active `SubProcessor` rows: name, purpose, country, transfer mechanism.}}
