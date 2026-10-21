# Atualizando do template da era Celery

Vale para projetos copiados de versões anteriores deste template. Mova um projeto por vez; mantenha os
outros na tag deles até chegar a vez.

1. **Dependências**: Django 6.1.2, DRF 3.18.x; remova o `celery`; adicione os novos requisitos.
2. **Configurações**: troque `CELERY_*` por `TEMPORAL_*` (veja
   [variáveis de ambiente](../reference/env-vars.md)); as variáveis específicas de plataforma do template antigo acabaram. Declare seu proxy:
   `TRUSTED_PROXY_COUNT` ou `TRUSTED_PROXY_IPS`. Novas variáveis obrigatórias em produção:
   `AUDIT_HMAC_KEY`, `PUBLIC_URL`, `PRIVACY_CONTROLLER_NAME`, `DPO_EMAIL`/`DPO_CONTACT_URL`
   ([solução de problemas](../guides/troubleshooting.md)).
3. **Tarefas**: funções `@shared_task` viram `@job` (agendado/manual) ou tarefas `django.tasks`;
   `.delay()` vira `task.enqueue()`; agendas do beat viram o `schedule=` do job.
4. **Workers**: rode `entrypoint worker` (Temporal) ou `entrypoint scheduler` (sem Temporal).
5. **Migrações**: apps novos (`actions`, `apikeys`, `flows`, `webhooks`, `flags`, `uploads`, allauth,
   usersessions) são aditivos. Rode `migrate` **como dono do schema**, depois `manage.py privacy_seed`.
6. **Models**: adicione as classificações em `<app>/privacy.py`; a suíte de testes lista o que falta.
7. **Criptografia**: valores gravados pela v1 continuam decifrando; rode `reencrypt_fields` uma vez para
   levá-los ao formato v2.
8. **Contas**: usuários existentes não têm endereço verificado; com verificação obrigatória eles
   verificam no próximo login. Para pular isso numa base confiável, crie linhas `EmailAddress`
   verificadas antes da virada. O `/api/v1/auth/login/` vem desligado (`LEGACY_LOGIN_ENABLED`).
9. **Auditoria**: a cadeia é chaveada desde o início. Linhas gravadas por um template mais antigo usavam
   hash simples e não vão verificar sob a chave: arquive-as e comece a cadeia do zero.
10. **Deploy**: troque para os papéis de entrypoint do novo Dockerfile ou para os manifestos
    compose/k8s, que também criam os dois papéis de banco.
