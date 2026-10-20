# Security policy / Política de segurança

## English

Do not open public issues for vulnerabilities, credentials, personal data or production details.
Report privately through GitHub's "Report a vulnerability" (Security tab) on the repository that
hosts your fork, or to the contact you publish in your own deployment. **Before launching a
product built on this template, set that contact and your response times here**, and publish
them at `/.well-known/security.txt` behind your proxy.

Supported versions: the latest release and the previous minor.

Treat exposed credentials (Django secret, database, Redis, object storage, Sentry, e-mail, OAuth,
field-encryption key ring) as compromised: revoke and rotate them, preserve evidence, assess the
personal-data impact, and follow the [runbooks](docs/en/deploy/runbooks.md) and
[hardening guide](docs/en/security/hardening.md). The threat model is in
[docs/en/security/threat-model.md](docs/en/security/threat-model.md) and the review status in
[docs/en/security/review.md](docs/en/security/review.md).

## Português

Não abra issues públicas com vulnerabilidades, credenciais, dados pessoais ou detalhes de
produção. Reporte em privado pelo "Report a vulnerability" do GitHub (aba Security) no
repositório do seu fork, ou pelo contato que você publicar na sua implantação. **Antes de
lançar um produto baseado neste template, defina aqui esse contato e os prazos de resposta** e
publique-os em `/.well-known/security.txt` no seu proxy.

Versões suportadas: a última versão e a menor anterior.

Trate credenciais expostas (segredo do Django, banco, Redis, object storage, Sentry, e-mail,
OAuth, chaveiro de criptografia de campos) como comprometidas: revogue e rotacione, preserve
evidências, avalie o impacto sobre dados pessoais e siga os
[runbooks](docs/pt-BR/deploy/runbooks.md) e o [guia de hardening](docs/pt-BR/security/hardening.md).
O modelo de ameaças está em [docs/pt-BR/security/threat-model.md](docs/pt-BR/security/threat-model.md)
e o estado da revisão em [docs/pt-BR/security/review.md](docs/pt-BR/security/review.md).
