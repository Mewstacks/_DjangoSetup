# Decisões

Registros curtos das escolhas que moldam o código. Cada um diz o motivo e o custo.

1. **Ações são a única entrada.** Um registro alimenta REST, MCP, Temporal e CLI. Custo: uma
   camada extra para CRUD trivial, que o `OrganizationScopedViewSet` ainda atende.
2. **pydantic é a única fonte de schema** das ações (docs REST, schema de entrada do MCP, tipos
   das activities). Sem serializers DRF paralelos para ações.
3. **Celery removido.** Trabalho em segundo plano é `django.tasks` com backend Temporal, ou o
   backend imediato quando o Temporal está desligado. Custo: sem o ecossistema do Celery.
4. **Temporal é opcional, o motor local é honesto.** Mesmo `flows.start()`, com matriz de
   capacidades publicada; fluxos não portáveis dizem isso. Custo: duas implementações a testar.
5. **Activities síncronas num pool de threads.** O ORM do Django é síncrono; as conexões são
   fechadas em volta de cada activity.
6. **Workflows não importam Django.** O sandbox proíbe; as activities fazem o trabalho.
7. **Payloads do Temporal são cifrados** por um codec, e os argumentos são ids.
8. **Cadeia de auditoria por organização** com advisory lock no insert, mais um trigger. Custo:
   contenção de escrita em organizações muito quentes; selagem em lote é a saída.
9. **Todo model é classificado para LGPD** por um teste que falha.
10. **allauth para contas**, DOT para OAuth. Custo: duas bibliotecas; benefício: fluxos auditados
    de MFA, verificação e consentimento.
11. **Cadastro fechado por padrão.** Sistemas abertos são uma escolha explícita.
12. **Uma imagem, vários papéis; sem amarra a plataforma.** O Fly é um destino entre outros.
