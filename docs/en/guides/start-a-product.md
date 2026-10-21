# Start a product on this base

From a fresh clone to a deployed product, in the order that avoids rework.

## 1. Run it (10 minutes)

```bash
git clone <your copy of the template> my-product && cd my-product
uv sync --all-extras
python scripts/bootstrap.py
python manage.py runserver
```

`bootstrap.py` writes `.env` with fresh secrets, migrates, seeds the LGPD purposes, and creates a
**verified** administrator, an organization and an API key. The credentials are printed once, to
your terminal. Open `http://localhost:8000/api/docs/`.

## 2. Make it yours

```bash
python scripts/init_project.py --name "Acme Billing"            # preview
python scripts/init_project.py --name "Acme Billing" --apply
```

It renames the package metadata, the OpenAPI title, the admin header, the Compose projects and the
example image. It leaves the Python packages (`apps`, `config`) alone, so future merges from the
template stay clean.

## 3. Build your first resource

```bash
python manage.py scaffold resource invoices Invoice --fields 'title:str,notes:text,amount:decimal'
python manage.py makemigrations invoices
python manage.py actions_catalog && python scripts/check_openapi.py --write && python scripts/gen_docs.py
python scripts/verify.py --fast
```

The scaffold writes model, service, five actions, undo handlers, events, MCP resource and prompt,
LGPD entry and tests. Read `invoices/privacy.py`: its docstring lists the decisions that are
yours. Field types: `str`, `text` (encrypted), `int`, `bool`, `decimal`, `datetime`.

## 4. Retire the example

The `examples` app (Notes) is the reference the tests lean on. Once your resource exists:

```bash
python scripts/remove_example.py            # preview, including what still mentions Notes
python scripts/remove_example.py --apply
```

It deletes the app and unwires it, then lists the tests that still use Notes. Port those to your
own resource (the generated test file shows the shape) rather than deleting them.

## 5. Decide the product-level policy

| Decision | Setting | Default |
|---|---|---|
| Who can sign up | `SIGNUP_ENABLED` | closed |
| Staff need a second factor | `STAFF_MFA_REQUIRED` | on |
| Owners and administrators need a second factor | `ORG_PRIVILEGED_MFA_REQUIRED` | on in production |
| Per-organization ceilings | `QUOTA_*` | guard rails; replace `quotas.limit_for` to sell plans |
| Audit retention | `AUDIT_RETENTION_DAYS` | 365 |
| Who is the controller and the DPO | `PRIVACY_CONTROLLER_*`, `DPO_*` | **required in production** |

## 6. LGPD before launch

1. Set the controller and DPO variables, run `privacy_seed`, review each purpose with counsel.
2. Publish a privacy notice (`PrivacyNotice`; immutable once active). Templates are in
   [LGPD templates](../lgpd/templates.md).
3. Activate the sub-processors you really use (`privacy_seed` creates inactive stubs).
4. Write an impact assessment (`ImpactAssessment`) for any high-risk processing.
5. If the product may be used by anyone under 18, read the ECA Digital notes in the
   [LGPD overview](../lgpd/overview.md) and plug an age-assurance backend in.

## 7. Deploy

Follow [Deploy anywhere](../deploy/overview.md). Tag `vX.Y.Z`: the release workflow runs the full
gate, scans, signs and publishes the image, and prints its digest; deploy by digest.

## 8. Keep up with the template

```bash
git remote add template <template url>
git fetch template && git merge template/main
```

Conflicts concentrate in `README`, settings and docs. Read [Upgrading from upstream](upgrading.md)
first. `scripts/verify.py` after every merge.
