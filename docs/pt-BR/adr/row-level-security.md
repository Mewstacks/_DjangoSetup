# ADR 14: Row-level security é um desenho opcional, não o padrão

**Status:** aceito como opção documentada. **Não implementado.**

## Contexto

O isolamento de tenants hoje é por construção: ações leem só por `ctx.scoped`/`ctx.get`, a base de
viewsets filtra por organização, chaves estrangeiras graváveis são validadas contra a organização, e
testes varrem o código e exercitam acesso entre tenants. Isso é convenção, imposta por testes. Um bug
que a contorne (uma consulta crua, um filtro esquecido em código fora de `actions.py`) vaza entre
tenants. O row-level security (RLS) do PostgreSQL faria o banco recusar essa leitura.

## Opções

1. **Convenção mais testes** (hoje). Barata, portátil (SQLite nos testes), o modo de falha é um bug.
2. **RLS nas tabelas de tenant.** Uma política `USING (organization_id = current_setting('app.org')::uuid)`,
   com a configuração feita por `SET LOCAL` no início de cada transação.

## Decisão

Manter a opção 1 como padrão e documentar a 2 para que um time que precise dela possa adotá-la sem
redesenho. Motivos para não ser o padrão:

- Toda requisição e tarefa em segundo plano precisa definir a organização na sua conexão, dentro de uma
  transação, ou o PgBouncer em modo transaction-pooling a vaza para o próximo cliente.
- Migrações, o admin, jobs de sistema e a cadeia de auditoria (organização nula) precisam de um papel
  de bypass, que é mais um caminho privilegiado para proteger.
- Dois caminhos de código a testar (SQLite sem RLS, PostgreSQL com), e um custo mensurável no planner.

## Se você adotar

1. Rode a aplicação como um papel sem `BYPASSRLS` (o papel de runtime já difere do dono; veja o
   ADR 13).
2. `ALTER TABLE <t> ENABLE ROW LEVEL SECURITY; ALTER TABLE <t> FORCE ROW LEVEL SECURITY;` e uma
   política por tabela sobre `organization_id`, com `WITH CHECK` para escritas.
3. Defina `app.org` com `SET LOCAL` onde o `ActionContext` é construído e no
   `OrganizationContextMiddleware`; uma requisição sem organização define o UUID nulo para que nada
   case.
4. Dê aos jobs de sistema um papel separado com uma política explícita para linhas de organização
   nula.
5. Rode `tests/test_tenant_isolation.py` e a suíte de conformidade contra o PostgreSQL com RLS
   ligado.

Comece pelas tabelas com os dados mais sensíveis (uploads, webhooks, chaves de API).
