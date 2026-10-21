# Upgrading from upstream

Your product started as a copy of this template. The template keeps improving (security fixes
above all), and you want those without losing your work.

## Keep the seam clean

- Your code lives in **your apps** (`src/apps/<yours>/`), added to `LOCAL_APPS`. Avoid editing the
  platform apps (`actions`, `accounts`, `audit`, `privacy`, `organizations`, ...): extend through
  the discovery files (`actions.py`, `events.py`, `privacy.py`, ...) and settings.
- When you must change a platform file, keep the change small and comment why; it is where merge
  conflicts will happen.
- Do not rename the Python packages. `scripts/init_project.py` renames the product, not the imports,
  for exactly this reason.

## The routine

```bash
git remote add template <template url>      # once
git fetch template
git merge template/main                      # or: git rebase template/main
python scripts/verify.py                     # the whole gate
```

1. Read the new `CHANGELOG.md` entries first, especially **Security** and **Breaking**.
2. Conflicts cluster in `README`, settings, docs and `pyproject.toml`. Keep your product's
   identity, take the template's behaviour.
3. Regenerate: `python manage.py actions_catalog`, `python scripts/check_openapi.py --write`,
   `python scripts/gen_docs.py`.
4. `python manage.py makemigrations --check` must be clean; apply new migrations in staging first.
5. Re-read `SECURITY.md` and `docs/en/security/review.md`: new controls sometimes need a setting.

## Migrations and data formats

Template migrations are additive within a minor release. A release that changes a data format says
so under **Breaking** and ships the command (for example `reencrypt_fields` after a key or scheme
change). Roll back the image, never the database.

## Releases and the image

Tag `vX.Y.Z` in **your** repository. The release workflow runs the full gate, scans and signs the
image and attaches provenance and an SBOM. Deploy by the digest it prints, not the tag. To verify a
signature: `cosign verify <image>@<digest> --certificate-identity-regexp '...' --certificate-oidc-issuer
https://token.actions.githubusercontent.com`.

## When to take a fix immediately

A `Security` entry in the template's changelog, or an advisory in a dependency (`pip-audit` runs
weekly in CI). Merge, run the gate, release.
