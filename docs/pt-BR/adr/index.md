# Decisões

Registros curtos de escolhas que moldam o código. Cada um diz o motivo e o custo.

1. **Ações são a única porta de entrada.** Um registro alimenta REST, MCP, Temporal e a CLI. Custo: uma
   camada a mais para CRUD trivial, que o `OrganizationScopedViewSet` ainda atende.
2. **pydantic é a fonte única de schema** das ações (docs REST, schema de entrada do MCP, tipos de
   atividades). Sem serializers DRF paralelos para ações.
3. **Celery removido.** Trabalho em segundo plano é `django.tasks` com backend Temporal, ou o backend
   imediato quando o Temporal está desligado. Custo: sem o ecossistema do Celery.
4. **Temporal é opcional, o motor local é honesto.** O mesmo `flows.start()`, com uma matriz de
   capacidades publicada; flows não portáteis dizem isso. Custo: duas implementações para testar.
5. **Atividades síncronas num pool de threads.** O ORM do Django é síncrono; as conexões são fechadas
   em volta de cada atividade.
6. **Workflows não importam Django.** O sandbox proíbe; as atividades fazem o trabalho.
7. **Payloads do Temporal são cifrados** por um codec, os argumentos são ids, e um payload não selado é
   recusado.
8. **Cadeia de auditoria por organização** com advisory lock no insert, mais um trigger. Custo:
   contenção de escrita em organizações muito quentes; selagem em lote é a saída. Reforçada pela
   decisão 13.
9. **Todo modelo é classificado para a LGPD** por um teste que falha.
10. **allauth para contas**, DOT para OAuth. Custo: duas bibliotecas; benefício: fluxos auditados de
    MFA, verificação e consentimento.
11. **Cadastro fechado por padrão.** Sistemas abertos são uma escolha explícita.
12. **Uma imagem, vários papéis; sem lock-in de plataforma.** Qualquer plataforma de contêiner é alvo.

Registros mais longos:

13. [A trilha de auditoria é chaveada, e só o dono pode podá-la](audit-chain-and-role-split.md)
14. [Row-level security é um desenho opcional, não o padrão](row-level-security.md)
15. [Dois servidores MCP, com trabalhos diferentes](two-mcp-servers.md)
16. [Os arquivos para agentes são gerados de um só livro de regras](ai-context-generated.md)
17. [Quem é o controlador, e de quem é a solicitação](controller-and-operator.md)
