# Solução de problemas

As configurações de produção se recusam a iniciar com configuração insegura ou ausente e dizem qual
variável corrigir. Esta página liga cada recusa à causa.

## O ambiente mínimo de produção

| Variável | Por quê |
|---|---|
| `DJANGO_SECRET_KEY`, `PRIVACY_HMAC_KEY`, `AUDIT_HMAC_KEY` | Três segredos aleatórios diferentes: `python scripts/generate_production_secrets.py` |
| `FIELD_ENCRYPTION_ACTIVE_KEY_ID`, `FIELD_ENCRYPTION_KEYS` | O chaveiro (mesmo script) |
| `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS`, `DJANGO_CORS_ALLOWED_ORIGINS` | Seus hosts; origens são `https://` |
| `PUBLIC_URL` | `https://app.exemplo.com`: base de todo link que enviamos por e-mail |
| `DATABASE_URL` ou `DB_*` | PostgreSQL, TLS com verificação de certificado (`sslmode=verify-full`) |
| `REDIS_URL` | `rediss://`; carrega sessões, bloqueios e limites |
| `TRUSTED_PROXY_COUNT` ou `TRUSTED_PROXY_IPS` | Como o app é alcançado; sem isso todo cliente parece o proxy |
| `S3_BUCKET` | Uploads e exportações (ou `OBJECT_STORAGE_REQUIRED=false` com volume persistente) |
| `SENTRY_DSN` ou `SENTRY_ENABLED=false` | Relato de erros, ou um não explícito |
| `EMAIL_HOST` ... | Um backend de e-mail de verdade |
| `PRIVACY_CONTROLLER_NAME`, `DPO_EMAIL` ou `DPO_CONTACT_URL` | Quem é responsável e o canal até essa pessoa |

## "ImproperlyConfigured: ..." na partida

| A mensagem começa com | Causa e correção |
|---|---|
| `... looks like a placeholder` / `has too little variety` | Um segredo copiado de um exemplo. Gere segredos de verdade |
| `... must differ from ...` | Dois segredos são iguais |
| `Production database must use TLS` / `sslmode=require ... never checks` | Use `sslmode=verify-full`; numa rede privada que você controla defina `DB_ALLOW_INSECURE_TRANSPORT=true` (ou `DB_ALLOW_UNVERIFIED_TLS=true` para manter `require`) |
| `REDIS_URL must use rediss://` | Use TLS, ou `REDIS_ALLOW_INSECURE=true` numa rede privada |
| `Declare how the app is reached` | Defina `TRUSTED_PROXY_COUNT`/`TRUSTED_PROXY_IPS`, ou `TRUSTED_PROXY_DIRECT=true` |
| `Production object storage is required` | Defina `S3_BUCKET` |
| `SENTRY_DSN is required` | Informe um DSN ou `SENTRY_ENABLED=false` |
| `PUBLIC_URL must be the https origin` | `https://host`, sem caminho |
| `Set PRIVACY_CONTROLLER_NAME` / `Set DPO_EMAIL or DPO_CONTACT_URL` | Publique quem responde pelos dados pessoais |
| `Production Temporal needs sealed payloads` / `must use TLS` | Mantenha `TEMPORAL_PAYLOAD_ENCRYPTION=true`; TLS ou chave de API, ou `TEMPORAL_ALLOW_INSECURE=true` numa rede privada |
| `ADMIN_ENABLED in production requires ADMIN_ALLOWED_IPS` | Informe as redes que podem alcançar `/admin/` |

## Sintomas

| Você vê | Olhe |
|---|---|
| O login funciona mas `/admin/` responde 403 `mfa_required` | Staff precisa antes de um autenticador (`/accounts/2fa/`) |
| `403 mfa_required` ou "must enable two-factor" nos endpoints da organização | `ORG_PRIVILEGED_MFA_REQUIRED` em produção: cadastre um autenticador |
| `403 reauthentication_required` ao criar chave | Entre de novo; a janela é `APIKEY_REQUIRE_RECENT_AUTH_SECONDS` |
| Todos os usuários dividem um limite de taxa ou bloqueio | O proxy não está declarado direito (`doctor` -> client ip) |
| `429` do `/mcp` | `MCP_RATE_PER_MINUTE_IP`; muitos agentes atrás de um endereço |
| Endpoint de webhook recusado com `blocked_address` | A URL resolve para endereço não público (a proteção SSRF) |
| Uploads falham com `scanner_unavailable` | `UPLOAD_CLAMAV_ADDR` está definido e inacessível; conserte ou defina `UPLOAD_CLAMAV_REQUIRED=false` sabendo o que faz |
| `audit_verify` aponta quebra | Veja o runbook de auditoria em [Runbooks](../deploy/runbooks.md) |
| `doctor` avisa "the runtime role can rewrite the audit trail" | Conecte com um papel que não seja dono do schema ([Hardening](../security/hardening.md)) |
| Cliente OAuth não consegue se registrar | `OAUTH_DCR_ANONYMOUS`, ou o redirect URI não é `https` nem loopback |
| A imagem diz que falta o OpenTelemetry | Construa com `--build-arg EXTRAS="--extra otel"` |

Qualquer outra coisa: `python manage.py doctor --strict` e depois os logs (JSON, uma linha por
evento, com `request_id`).
