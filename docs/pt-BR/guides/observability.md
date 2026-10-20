# Observabilidade

## Logs

structlog sobre a biblioteca padrão: um único pipeline JSON para a aplicação e os loggers de
terceiros. Toda linha leva `request_id` (gerado no servidor; um id enviado pelo cliente fica em
campo separado), `organization_id`, `actor_id`, canal e, dentro do Temporal, ids de workflow e
activity. A redação (e-mail, CPF/CNPJ, telefone, IP, tokens, chaves de API, cookies, URLs com
senha, texto de exceção) roda no **fim** do pipeline. Um teste de log dourado falha se dados
pessoais sintéticos chegam à saída. Nível: `LOG_LEVEL` (DEBUG é recusado em produção).

## Traces e métricas

`OTEL_ENABLED=true` com o extra `otel` exporta OTLP para Django, psycopg, httpx e Temporal.
Local: `docker compose --profile observability up` e abra o Grafana na porta 3000. O Sentry
continua opcional (`SENTRY_ENABLED`), com scrubbing aplicado.

## Health e `doctor`

`/api/v1/health/live/` só olha o processo. `/api/v1/health/ready/` checa banco e cache e informa
o estado do worker de modo informativo. `python manage.py doctor [--strict]` também checa
criptografia, declaração de proxy, postura HTTPS, e-mail e alcance do Temporal; rode no CD.
`python manage.py audit_verify` confere as cadeias de auditoria.
