# Hardening e gestão de chaves

## A produção se recusa a iniciar quando

- a secret key ou a chave HMAC é placeholder, curta ou de baixa entropia, ou dois segredos são
  iguais;
- o chaveiro de criptografia de campos está malformado ou não tem a chave ativa;
- o banco não é acessado por TLS (e `DB_ALLOW_INSECURE_TRANSPORT` não foi definido de propósito);
- o Redis não tem auth/TLS (e `REDIS_ALLOW_INSECURE` não foi definido);
- hosts são curinga ou origens não são https; nenhum proxy foi declarado (`TRUSTED_PROXY_IPS`,
  `TRUSTED_PROXY_COUNT` ou `TRUSTED_PROXY_DIRECT`); uma entrada de proxy não é CIDR;
- o admin está ligado sem `ADMIN_ALLOWED_IPS`; `NETGUARD_ALLOW_PRIVATE` está ligado;
  `LOG_LEVEL=DEBUG`.

## Sempre ligado

Redirect para HTTPS (probes isentos), HSTS, cookies secure/HTTP-only/SameSite, CSP (padrão
`'self'`), `X-Frame-Options: DENY`, no-store nas respostas da API, limite de corpo no ASGI,
resolução de IP do cliente por proxies confiáveis, senha de no mínimo 12 caracteres com checagem
de senhas comuns.

## Rotação de chaves

```bash
python scripts/generate_production_secrets.py --key-id v2 --existing-ring '{"v1":"..."}'
# defina FIELD_ENCRYPTION_ACTIVE_KEY_ID=v2 e o novo chaveiro, faça deploy
python manage.py reencrypt_fields          # recifra toda coluna cifrada
# quando não restar nada em v1, remova v1 do chaveiro
```

Nunca regenere o chaveiro sem `--existing-ring`: o texto cifrado existente ficaria ilegível.
Rotacionar `DJANGO_SECRET_KEY` desloga todo mundo; rotacionar `PRIVACY_HMAC_KEY` quebra a busca de
evidências com hash, então só com plano de migração.

## Rotação das demais credenciais

Chaves de API: `rotate` (24 h de sobreposição). Segredos de webhook: `rotate-secret` (as duas
assinaturas são enviadas durante a sobreposição). Clientes OAuth: revogue tokens, emita novo
cliente. Senhas de banco/Redis: troque na plataforma, atualize o segredo, reinicie os pods; o
readiness fica não-pronto até reconectar.
