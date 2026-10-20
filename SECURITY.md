# Política de segurança / Security policy

## Português (pt-BR)

Não abra issues públicas contendo vulnerabilidades, credenciais, dados pessoais ou detalhes de
produção. Antes de lançar cada produto clonado, configure um canal privado de reporte e publique
os prazos esperados de resposta.

Considere credenciais expostas de Django, banco, Redis, Fly.io, object storage, Sentry, e-mail,
pagamentos, OAuth ou criptografia como comprometidas: revogue e rotacione, preserve evidências,
avalie o impacto sobre dados pessoais e siga o
[runbook de incidentes](docs/pt-BR/runbooks/resposta-incidentes.md).

O modelo técnico completo está em [docs/pt-BR/seguranca.md](docs/pt-BR/seguranca.md).

## English

Do not open public issues containing vulnerabilities, credentials, personal data, or production
details. Configure a private reporting channel for each cloned product before launch and
publish its expected response times.

Treat exposed Django, database, Redis, Fly.io, object-storage, Sentry, email, payment, OAuth, or
field-encryption credentials as compromised: revoke and rotate them, preserve evidence, assess
personal-data impact, and follow the
[incident runbook](docs/en/runbooks/incident-response.md).

The complete technical model is in [docs/en/security.md](docs/en/security.md).
