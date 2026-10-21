# Cartilha do framework

O que uma pessoa desenvolvedora (ou um agente de IA) precisa saber de Django e das bibliotecas ao redor
para programar certo nesta plataforma. Cada seção diz como a coisa funciona e depois a regra que este
projeto acrescenta. Documentação oficial das versões do `pyproject.toml`: Django 6.1
(<https://docs.djangoproject.com/en/6.1/>), DRF (<https://www.django-rest-framework.org/>),
django-allauth (<https://docs.allauth.org/>), SDK Python do Temporal
(<https://docs.temporal.io/develop/python>), FastMCP (<https://gofastmcp.com/>).

## Ciclo da requisição e middleware

Uma requisição entra no app ASGI, passa pela lista de middleware **de cima para baixo**, chega à view, e
a resposta volta **de baixo para cima**. Um middleware que responde cedo (uma recusa) pula tudo o que
está abaixo. A ordem é, portanto, uma decisão de segurança, e `settings.MIDDLEWARE` é o único lugar onde
ela é definida. Chame a ferramenta `middleware_stack` para a ordem real, com uma nota em cada item.

Regras aqui:

- `SecurityMiddleware` e `SecurityHeadersMiddleware` vêm primeiro, para toda resposta, inclusive as
  recusas, levar os cabeçalhos.
- `RequestContextMiddleware` roda antes de qualquer coisa que registre log, para toda linha ter um id de
  requisição.
- A autenticação (`AuthenticationMiddleware`) precede o `OrganizationContextMiddleware`, que lê
  `request.user` para resolver o tenant a partir de `X-Organization-ID`.
- Um middleware novo entra onde suas dependências já estão preenchidas e antes de quem precisa do seu
  resultado. Escreva o motivo num comentário acima da entrada.
- O `/mcp` é montado ao lado do Django no app ASGI e **não** passa por esta lista; tem o próprio pré-voo
  (`apps.actions.mcp.preflight`). Um controle adicionado ao middleware precisa ser adicionado lá também,
  ou não cobre o MCP.

## ORM, models e migrations

- Models de tenant herdam de `OrganizationScopedModel` e são lidos por `ctx.scoped(Model)` / `ctx.get`.
  Nunca `Model.objects` para linhas de tenant em actions.
- Todo model é classificado em `<app>/privacy.py` (LGPD); a suíte de testes falha até ser.
- Comece de `UUIDTimeStampedModel` (chave primária UUID, `created_at`, `updated_at`); datas e horas têm
  fuso (`USE_TZ`).
- `makemigrations` após toda mudança de model; nunca edite uma migration que já foi publicada; mantenha
  migrations de dados idempotentes. As migrations rodam como dono do schema, o processo web roda com um
  papel que não altera schema (veja o ADR de auditoria).
- Evite consultas N+1: `select_related` para chaves estrangeiras, `prefetch_related` para conjuntos
  reversos. Não filtre por um `EncryptedTextField`; use `blind_index()` para igualdade.

## Transações e sinais

- Uma action roda em uma transação (`ATOMIC_REQUESTS` não é usado); o evento de auditoria é gravado
  dentro dela, então não existe sem a mudança.
- Efeitos que saem do banco (e-mail, webhook, tarefa) passam por `transaction.on_commit` ou pelo outbox
  de webhooks, nunca direto dentro da transação.
- Sinais servem para reações entre apps que já existem no código (auditoria, limpeza de uploads). Regra
  de negócio não vai em sinal: vai em `services.py`, onde REST, MCP, CLI e Temporal a compartilham.

## Django REST Framework

- Operações são actions; CRUD clássico pode usar `OrganizationScopedViewSet` em `api.py`.
- Permissões: `IsAuthenticated`, `HasOrganizationContext`, `RoleCanWrite` e `ApiKeyScopePermission` para
  chaves. Um viewset sem elas é um bug que os testes pegam.
- Chaves estrangeiras graváveis usam `OrgScopedPrimaryKeyRelatedField`, para um id de outro tenant ser
  recusado.
- Os erros usam um só envelope em toda superfície; levante subclasses de `DomainError` (`NotFound`,
  `Forbidden`, `Invalid`, `Conflict`), nunca vaze texto de `ValidationError` do Django.

## Contas, sessões e MFA

- Login, verificação de e-mail e MFA são do django-allauth (headless). O bloqueio é do django-axes.
- Staff precisa de MFA para o `/admin/`; owners e admins precisam em produção
  (`ORG_PRIVILEGED_MFA_REQUIRED`), imposto na permissão do DRF e no runtime das actions.
- Chaves de API e tokens OAuth agem só dentro dos seus escopos; o papel é lido do vínculo a cada
  chamada. Criar uma chave exige login recente.

## Configurações

Quatro módulos: `base`, `local`, `test`, `production`. Adicione configuração com
`env_str/env_int/env_bool/env_list` e um comentário acima; a referência de ambiente é gerada dessas
chamadas. Restrições só de produção ficam em `config/settings/validators.py`; nunca afrouxe uma.

## Templates e CSP

As poucas páginas renderizadas no servidor (login, MFA, consentimento, OAuth) são limpas para a CSP:
sem script ou estilo inline, sem origem de terceiros. Comentários `{# #}` valem só para uma linha; use
`{% comment %}` para mais.

## Temporal (flows e jobs)

- Um **workflow** é código determinístico que é reexecutado a partir do histórico: sem ORM do Django,
  sem rede, sem `datetime.now()`, sem aleatório. Chame actions por `apps.flows.sdk.call_action`.
- Uma **activity** é uma função síncrona comum que faz o trabalho; os payloads são selados (cifrados) e
  levam ids, não documentos.
- Um **job** é uma função numa agenda cron (Schedule do Temporal, ou `run_scheduler` quando o Temporal
  está desligado). `manage.py flows_sync` cria ou atualiza os Schedules após um deploy.
- Mudar um workflow que pode estar em execução exige `workflow.patched`; mantenha históricos de replay
  nos testes.
- Com o Temporal desligado o motor local roda os mesmos flows; nem todo flow é portável, e a matriz de
  capacidades diz quais.

## Tarefas em segundo plano (`django.tasks`)

O `TemporalTaskBackend` roda tarefas declaradas no Temporal, o backend imediato as roda na hora. Só
tarefas sob `FLOWS_TASK_MODULE_PREFIXES` são permitidas. Passe ids, não instâncias de model.

## Testes

`pytest` com `pytest-django`. Use as fixtures de `tests/conftest.py` (`org_client`, `other_org_client`).
Uma action nova precisa de teste para o escopo, um papel somente leitura e uma tentativa entre tenants; a
suíte de conformidade já passa toda action registrada pelas checagens padrão.

## MCP (FastMCP)

Dois servidores, dois trabalhos: `/mcp` opera um produto em execução; `python -m devtools.mcp` o
constrói. Ferramentas são actions; resources e prompts ficam em `agent.py`. A descrição de uma
ferramenta é um prompt: escreva-a para o modelo que vai lê-la.
