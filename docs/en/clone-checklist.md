# New SaaS clone checklist

[Versão em português](../pt-BR/checklist-clonagem.md)

1. Rename the package/project metadata, API title, Fly app, cache prefix, Sentry project, and
   domains. Generate new secrets; never reuse keys between SaaS products or environments.
2. Decide whether the product is single-organization or multi-organization. Even for a
   single-organization product, keep explicit scoping until you intentionally remove it.
3. Add product models in separate apps. Tenant-owned records inherit
   `OrganizationScopedModel`; repository/service methods require an organization argument.
4. Define roles and permissions from product actions, not job titles. Add tests proving that
   users cannot read, infer, update, or delete another organization's records.
5. Complete the data inventory, purposes, lawful bases, notice, retention, vendor/transfer
   review, rights handlers, incident contacts, and RIPD decision.
6. Add customer onboarding, verified email/password reset, MFA/SSO, billing, and transactional
   email only after their threat/privacy flows are specified.
7. Establish staging with unrelated secrets and synthetic data. Never copy raw production
   personal data into local, CI, demos, or Sentry.
8. Run unit/integration/security tests, `check --deploy`, dependency/container scans, restore
   rehearsal, key-rotation rehearsal, load test, and an independent pre-launch review.
