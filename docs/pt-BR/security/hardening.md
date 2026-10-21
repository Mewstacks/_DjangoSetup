# Hardening e gestão de chaves

## A produção se recusa a iniciar quando

- a chave secreta, a chave HMAC de privacidade ou a chave HMAC de auditoria é um marcador, curta ou de
  baixa entropia, ou dois segredos são iguais; uma entrada de `DJANGO_SECRET_KEY_FALLBACKS` /
  `PRIVACY_HMAC_KEYS_PREVIOUS` é fraca;
- o chaveiro de criptografia de campos está malformado ou não tem a chave ativa;
- o banco não é alcançado por TLS **com verificação de certificado** (`sslmode=verify-ca` ou
  `verify-full`); `require` cifra sem checar quem respondeu e exige o explícito
  `DB_ALLOW_UNVERIFIED_TLS`, um enlace sem cifra exige `DB_ALLOW_INSECURE_TRANSPORT`;
- o Redis não é `rediss://` (uma senha em texto simples não protege contra quem escuta) a menos que
  `REDIS_ALLOW_INSECURE` registre a decisão;
- hosts têm curinga ou origens não são https; `PUBLIC_URL` não é uma origem https; nenhum proxy é
  declarado (`TRUSTED_PROXY_IPS`, `TRUSTED_PROXY_COUNT` ou `TRUSTED_PROXY_DIRECT`); uma entrada de
  proxy não é CIDR;
- o Temporal está ligado sem payloads selados, ou sem TLS / chave de API / `TEMPORAL_ALLOW_INSECURE`;
- nenhum controlador ou canal do DPO é declarado (`PRIVACY_CONTROLLER_NAME`, `DPO_EMAIL` ou
  `DPO_CONTACT_URL`);
- o admin está ligado sem `ADMIN_ALLOWED_IPS`; `NETGUARD_ALLOW_PRIVATE` está ligado;
  `LOG_LEVEL=DEBUG`.

`python scripts/verify.py` roda `manage.py check --deploy --fail-level WARNING` com as configurações de
produção: um aviso é uma falha. As duas opções de HSTS (subdomínios, preload) ficam silenciadas até
você ligá-las, porque são compromissos sobre o domínio pai inteiro.

## Sempre ligado

Redirecionamento HTTPS (probes isentos), HSTS, cookies secure/HTTP-only/SameSite, uma CSP só `'self'`
com coletor de violações, `X-Frame-Options: DENY`, `Cross-Origin-Opener-Policy` e
`Cross-Origin-Resource-Policy` `same-origin`, `Permissions-Policy` (câmera, microfone, localização,
pagamento ... desligados), `nosniff`, política de referrer estrita, no-store nas respostas da API,
limite de tamanho e de tempo de leitura do corpo no ASGI (408), resolução de IP do cliente por proxy
confiável, hash de senha Argon2, mínimo de 12 caracteres com checagem de senhas comuns, CORS limitado a
`/api/`.

## Proteção de contas

Staff precisa de um autenticador para o admin; owners e admins para os endpoints da organização
(produção); criar ou rotacionar uma chave de API exige um login recente; uma redefinição de senha ou do
segundo fator revoga as chaves da pessoa; staff que não é superusuário não toca em superusuários;
tokens OAuth são guardados como checksum. Veja [contas](../guides/auth.md).

## Requisições de saída

Tudo que um usuário pode apontar para o servidor (webhooks, metadados de cliente OAuth) passa pela
guarda de rede: só `https`, só endereços **globais** (uma lista de permissão: NAT de operadora,
endereços de metadados da Alibaba e das nuvens, formas de túnel IPv6 e embrulhos NAT64 de IPv4 privado
são recusados), o endereço validado é o conectado, sem redirecionamentos, sem proxy do ambiente, prazo
total, limite de tamanho e sem descompressão. A NetworkPolicy do Kubernetes repete isso na camada de
rede: a saída para a internet pública exclui toda faixa privada e o endpoint de metadados.

## Papéis de banco

O runtime conecta com um papel que não é dono de nada; as migrações rodam como dono. Veja
[Implante](../deploy/overview.md#duas-identidades-de-banco) e [Integridade da auditoria](audit-integrity.md).

## Rotação de chaves

```bash
python scripts/generate_production_secrets.py --key-id v2 --existing-ring '{"v1":"..."}'
# defina FIELD_ENCRYPTION_ACTIVE_KEY_ID=v2 e o novo chaveiro, publique
python manage.py reencrypt_fields          # recifra toda coluna cifrada e os segredos de MFA
# depois que relatar zero linhas ilegíveis, remova v1 do chaveiro
```

Nunca regenere o chaveiro sem `--existing-ring`: o texto cifrado existente ficaria ilegível.

| Segredo | Rotação |
|---|---|
| `DJANGO_SECRET_KEY` | Valor antigo para `DJANGO_SECRET_KEY_FALLBACKS`; ninguém é deslogado; remova depois da vida das sessões |
| `PRIVACY_HMAC_KEY` | Valor antigo para `PRIVACY_HMAC_KEYS_PREVIOUS`; chaves de API e titulares são regravados sob a nova chave no primeiro uso |
| `AUDIT_HMAC_KEY` | Começa uma nova época (linhas antigas deixam de verificar sob a chave nova): exporte a cadeia antes |

## Rotacionando outras credenciais

Chaves de API: `rotate` (24 h de sobreposição). Segredos de webhook: `rotate-secret` (as duas
assinaturas são enviadas durante a sobreposição). Clientes OAuth: revogue tokens, emita um cliente
novo. Senhas de banco/Redis: rotacione na plataforma, atualize o secret, reinicie os pods; o
`readiness` fica indisponível até conectar.

## O que isto não cobre

Um host ou pipeline de build comprometido; um superusuário malicioso que também tenha as chaves
(mitigado por auditoria e pela allowlist do admin, não impedido); SSO/SCIM. Veja o
[modelo de ameaças](threat-model.md).
