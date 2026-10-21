# Checklist de quem constrói: segurança e LGPD a cada mudança

Percorra a seção que corresponde ao que você está adicionando. Cada linha diz o que fazer e o que
impõe, para você saber quais itens um gate verde já cobre.

## Um modelo novo

- [ ] Dados de tenant herdam de `OrganizationScopedModel` (teste: toda coluna de organização é
      escopada ou explicada).
- [ ] `<app>/privacy.py`: `personal(...)` com todo campo de cara pessoal listado, ou
      `not_personal(..., "por quê")` (testes: `test_lgpd`, `test_catalog_lint`).
- [ ] Texto livre que pode conter dado pessoal é `EncryptedTextField`; dados sensíveis e de crianças
      precisam ser.
- [ ] Você sabe a finalidade, a regra de eliminação e o relógio de retenção (o `lgpd_check` guia).
- [ ] Adicionou índice para o jeito de consultar (sempre `organization` primeiro).

## Uma ação ou endpoint novo

- [ ] Lê por `ctx.scoped` / `ctx.get`; nunca `Model.objects` (teste de AST).
- [ ] Docstring escrito para o modelo que o lê; escopo; `write` / `destructive` / `undoable`
      declarados (checagem em import); `roles=` se só alguns papéis podem.
- [ ] A entrada é um modelo pydantic com limites (`max_length`, `ge`, `le`); a saída nunca traz campo
      com nome de segredo (teste de conformidade).
- [ ] Recusas são `DomainError` com mensagem legível por quem chama.
- [ ] Um teste para o escopo, um papel somente leitura e outro tenant (a suíte de conformidade faz os
      dois primeiros por você).
- [ ] Se tenants podem criar o recurso sem limite, chama `organizations.quotas`.

## Qualquer coisa que alcance a rede

- [ ] Uma URL que outra pessoa escolheu passa por `apps.common.netguard` (só https, só endereços
      públicos, IP fixado, sem redirecionamentos, tempo e tamanho limitados).
- [ ] Uma URL fixa de provedor ainda verifica o TLS. Nunca `verify=False`.
- [ ] Credenciais vêm de configurações, não do código; segredos nunca vão para logs.

## Uma configuração ou segredo novo

- [ ] Helper `env_*` com um comentário acima (vira a documentação de referência).
- [ ] Se a produção deve restringir, adicione um validador em `config/settings/validators.py` e um
      teste; valor ausente ou fraco deve parar a partida com mensagem que nomeia a variável.
- [ ] Adicionada a `deploy/compose/prod.env.example` e aos exemplos `configmap`/`secret` do
      Kubernetes.

## Uma página ou template novo

- [ ] Sem script ou estilo inline e sem origem de terceiros (a CSP é `'self'`).
- [ ] Formulários protegidos por CSRF; links destrutivos são POST.
- [ ] O texto é um rótulo ou um verbo, não um parágrafo que explica a tela.

## Log, auditoria e erros

- [ ] Metadados de auditoria: chaves snake_case, ids e contagens, sem valores pessoais (validado na
      escrita).
- [ ] Sem corpos de requisição, tokens ou endereços em logs (a redação é a rede, não o plano).
- [ ] Erros internos chegam ao cliente como `server_error` mais `request_id`, nada além.

## Trabalho em segundo plano

- [ ] Workflows não importam Django; o trabalho é uma ação chamada por `call_action`.
- [ ] Um job estilo cron é `@job` com agenda; é idempotente.
- [ ] Um novo evento de webhook é `register_event` e seu payload leva só ids.

## Antes de enviar

- [ ] `python scripts/verify.py` (completo) está verde.
- [ ] Arquivos gerados atualizados: `actions_catalog`, `check_openapi.py --write`, `gen_docs.py`.
- [ ] Docs atualizados em `docs/en` **e** `docs/pt-BR`; `CHANGELOG.md` para o que o usuário vê.
- [ ] Nada foi enfraquecido para fazer um teste passar (validadores, CORS, `NETGUARD_ALLOW_PRIVATE`,
      `DEBUG`).
- [ ] Para qualquer coisa sobre a ANPD, crianças ou transferência internacional: uma pessoa com
      habilitação jurídica olhou.
