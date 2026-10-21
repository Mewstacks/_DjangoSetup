# Atualizando a partir do upstream

Seu produto começou como uma cópia deste template. O template continua melhorando (correções de
segurança acima de tudo), e você quer isso sem perder o seu trabalho.

## Mantenha a costura limpa

- Seu código fica nos **seus apps** (`src/apps/<seus>/`), adicionados a `LOCAL_APPS`. Evite editar os
  apps da plataforma (`actions`, `accounts`, `audit`, `privacy`, `organizations`, ...): estenda pelos
  arquivos de descoberta (`actions.py`, `events.py`, `privacy.py`, ...) e pelas configurações.
- Quando precisar mudar um arquivo da plataforma, mantenha a mudança pequena e comente o motivo; é
  onde os conflitos de merge vão acontecer.
- Não renomeie os pacotes Python. O `scripts/init_project.py` renomeia o produto, não os imports,
  exatamente por isso.

## A rotina

```bash
git remote add template <url do template>   # uma vez
git fetch template
git merge template/main                      # ou: git rebase template/main
python scripts/verify.py                     # o gate completo
```

1. Leia antes as novas entradas do `CHANGELOG.md`, sobretudo **Security** e **Breaking**.
2. Os conflitos se agrupam em `README`, configurações, docs e `pyproject.toml`. Mantenha a identidade
   do seu produto, pegue o comportamento do template.
3. Regenere: `python manage.py actions_catalog`, `python scripts/check_openapi.py --write`,
   `python scripts/gen_docs.py`.
4. `python manage.py makemigrations --check` precisa sair limpo; aplique migrações novas primeiro em
   staging.
5. Releia `SECURITY.md` e `docs/pt-BR/security/review.md`: controles novos às vezes pedem uma
   configuração.

## Migrações e formatos de dados

As migrações do template são aditivas dentro de uma versão menor. Uma versão que muda um formato de
dados diz isso em **Breaking** e traz o comando (por exemplo `reencrypt_fields` depois de uma troca de
chave ou esquema). Reverta a imagem, nunca o banco.

## Releases e a imagem

Crie a tag `vX.Y.Z` no **seu** repositório. O workflow de release roda o gate completo, escaneia e
assina a imagem e anexa proveniência e um SBOM. Implante pelo digest que ele imprime, não pela tag.
Para verificar uma assinatura: `cosign verify <imagem>@<digest> --certificate-identity-regexp '...'
--certificate-oidc-issuer https://token.actions.githubusercontent.com`.

## Quando trazer uma correção na hora

Uma entrada `Security` no changelog do template, ou um aviso numa dependência (o `pip-audit` roda
toda semana no CI). Faça o merge, rode o gate, publique.
