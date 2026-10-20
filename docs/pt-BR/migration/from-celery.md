# Migrando do template da era Celery

Vale para projetos copiados de versões anteriores deste template (CRMew, IdeaLead e irmãos).
Migre um projeto por vez; mantenha os irmãos no tag deles até lá.

1. **Dependências**: Django 6.1.2, DRF 3.18.x; remova `celery`; adicione os novos requisitos.
2. **Settings**: troque `CELERY_*` por `TEMPORAL_*` (veja as [variáveis](../reference/env-vars.md));
   as variáveis `FLY_*` acabaram. Declare o proxy: `TRUSTED_PROXY_COUNT` ou `TRUSTED_PROXY_IPS`.
3. **Tasks**: funções `@shared_task` viram `@job` (agendado/manual) ou tasks de `django.tasks`;
   `.delay()` vira `task.enqueue()`; agendas do beat viram o `schedule=` do job.
4. **Workers**: rode `entrypoint worker` (Temporal) ou `entrypoint scheduler` (sem Temporal).
5. **Migrations**: os novos apps (`actions`, `apikeys`, `flows`, `webhooks`, `flags`, `uploads`,
   allauth, usersessions) são aditivos. Rode `migrate`, depois `manage.py privacy_seed`.
6. **Models**: adicione as classificações em `<app>/privacy.py`; a suíte de testes lista o que
   falta.
7. **Criptografia**: valores gravados no formato v1 continuam decifrando; rode `reencrypt_fields`
   uma vez para movê-los ao formato v2.
8. **Contas**: usuários existentes não têm endereço verificado; com verificação obrigatória eles
   verificam no próximo login. Para pular isso numa base confiável, crie linhas `EmailAddress`
   verificadas antes da virada. `/api/v1/auth/login/` está descontinuado.
9. **Auditoria**: as migrations de trigger e cadeia rodam no PostgreSQL; rode
   `audit_verify --all` depois.
10. **Deploy**: passe para os papéis do entrypoint do novo Dockerfile ou para os manifestos de
    compose/k8s.
