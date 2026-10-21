# Comece um produto nesta base

De um clone novo a um produto publicado, na ordem que evita retrabalho.

## 1. Rode (10 minutos)

```bash
git clone <sua cópia do template> meu-produto && cd meu-produto
uv sync --all-extras
python scripts/bootstrap.py
python manage.py runserver
```

O `bootstrap.py` escreve o `.env` com segredos novos, migra, semeia as finalidades da LGPD e cria um
administrador **verificado**, uma organização e uma chave de API. As credenciais aparecem uma vez,
no seu terminal. Abra `http://localhost:8000/api/docs/`.

## 2. Faça seu

```bash
python scripts/init_project.py --name "Acme Billing"            # prévia
python scripts/init_project.py --name "Acme Billing" --apply
```

Renomeia os metadados do pacote, o título do OpenAPI, o cabeçalho do admin, os projetos do Compose e
a imagem de exemplo. Deixa os pacotes Python (`apps`, `config`) como estão, para que merges futuros
do template continuem limpos.

## 3. Construa seu primeiro recurso

```bash
python manage.py scaffold resource invoices Invoice --fields 'title:str,notes:text,amount:decimal'
python manage.py makemigrations invoices
python manage.py actions_catalog && python scripts/check_openapi.py --write && python scripts/gen_docs.py
python scripts/verify.py --fast
```

O scaffold escreve modelo, serviço, cinco ações, handlers de desfazer, eventos, recurso e prompt MCP,
entrada da LGPD e testes. Leia `invoices/privacy.py`: o docstring lista as decisões que são suas.
Tipos de campo: `str`, `text` (cifrado), `int`, `bool`, `decimal`, `datetime`.

## 4. Aposente o exemplo

O app `examples` (Notes) é a referência em que os testes se apoiam. Quando seu recurso existir:

```bash
python scripts/remove_example.py            # prévia, inclusive o que ainda menciona Notes
python scripts/remove_example.py --apply
```

Apaga o app e o desliga, depois lista os testes que ainda usam Notes. Porte-os para o seu recurso (o
arquivo de teste gerado mostra o formato) em vez de apagá-los.

## 5. Decida a política do produto

| Decisão | Configuração | Padrão |
|---|---|---|
| Quem pode se cadastrar | `SIGNUP_ENABLED` | fechado |
| Staff precisa de segundo fator | `STAFF_MFA_REQUIRED` | ligado |
| Owners e admins precisam de segundo fator | `ORG_PRIVILEGED_MFA_REQUIRED` | ligado em produção |
| Tetos por organização | `QUOTA_*` | proteções; troque `quotas.limit_for` para vender planos |
| Retenção da auditoria | `AUDIT_RETENTION_DAYS` | 365 |
| Quem é o controlador e o DPO | `PRIVACY_CONTROLLER_*`, `DPO_*` | **obrigatório em produção** |

## 6. LGPD antes do lançamento

1. Defina as variáveis de controlador e DPO, rode `privacy_seed`, revise cada finalidade com um
   advogado.
2. Publique um aviso de privacidade (`PrivacyNotice`; imutável depois de ativo). Modelos em
   [modelos de documentos da LGPD](../lgpd/templates.md).
3. Ative os suboperadores que você realmente usa (`privacy_seed` cria rascunhos inativos).
4. Escreva um relatório de impacto (`ImpactAssessment`) para tratamentos de alto risco.
5. Se o produto puder ser usado por menores de 18 anos, leia as notas do ECA Digital na
   [visão geral da LGPD](../lgpd/overview.md) e conecte um backend de verificação de idade.

## 7. Publique

Siga [Implante em qualquer lugar](../deploy/overview.md). Crie a tag `vX.Y.Z`: o workflow de release
roda o gate completo, escaneia, assina e publica a imagem, e imprime o digest; implante pelo digest.

## 8. Acompanhe o template

```bash
git remote add template <url do template>
git fetch template && git merge template/main
```

Os conflitos se concentram em `README`, configurações e docs. Leia
[Atualizando a partir do upstream](upgrading.md) antes. `scripts/verify.py` depois de cada merge.
