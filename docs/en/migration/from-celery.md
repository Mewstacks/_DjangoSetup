# Upgrading from the Celery-era template

Applies to projects copied from earlier versions of this template (CRMew, IdeaLead and
siblings). Move one project at a time; keep sibling projects on their tag until you do.

1. **Dependencies**: Django 6.1.2, DRF 3.18.x; remove `celery`; add the new requirements.
2. **Settings**: replace `CELERY_*` with `TEMPORAL_*` (see [env vars](../reference/env-vars.md));
   `FLY_*` variables are gone. Declare your proxy: `TRUSTED_PROXY_COUNT` or `TRUSTED_PROXY_IPS`.
3. **Tasks**: `@shared_task` functions become `@job` (scheduled/manual) or `django.tasks` tasks;
   `.delay()` becomes `task.enqueue()`; beat schedules become the `schedule=` of the job.
4. **Workers**: run `entrypoint worker` (Temporal) or `entrypoint scheduler` (no Temporal).
5. **Migrations**: new apps (`actions`, `apikeys`, `flows`, `webhooks`, `flags`, `uploads`,
   allauth, usersessions) are additive. Run `migrate`, then `manage.py privacy_seed`.
6. **Models**: add `<app>/privacy.py` classifications; the test suite will list what is missing.
7. **Encryption**: values written by v1 keep decrypting; run `reencrypt_fields` once to move
   them to the v2 format.
8. **Accounts**: existing users get no verified address; with mandatory verification they
   verify on their next sign-in. To skip it for a trusted user base, create verified
   `EmailAddress` rows before cutover. `/api/v1/auth/login/` is deprecated.
9. **Audit**: the trigger and chain migrations run on PostgreSQL; run `audit_verify --all`
   afterwards.
10. **Deploy**: switch to the new Dockerfile entrypoint roles or compose/k8s manifests.
