# Celery e jobs em background

[English version](../../en/technologies/celery-jobs.md) ·
[Voltar à trilha](../trilha-aprendizado.md)

## O que é Celery?

Celery executa funções Python fora do processo web. A API cria uma mensagem no **broker** Redis;
um **worker** retira a mensagem e executa a task.

```text
API → Redis/broker → worker Celery → PostgreSQL/object storage
```

## Por que usar?

Uma requisição deve responder rápido. E-mail, relatório, webhook, importação e exportação LGPD
podem levar segundos ou minutos:

```text
POST /exports → cria job → responde 202
worker → gera arquivo → atualiza status
```

## Idempotência

Neste projeto, `ACKS_LATE` confirma a mensagem depois da execução. Se o worker cair, a task pode
rodar novamente. **Idempotente** significa que repetir produz o mesmo estado seguro.

Para evitar duplicidade:

- use uma chave de idempotência;
- grave estado no PostgreSQL;
- imponha unicidade quando possível;
- confira o estado antes de cobrar, enviar ou criar;
- limite retries e use backoff.

Não existe garantia simples de “exatamente uma vez” em sistemas distribuídos.

## Dados e privacidade

Passe IDs como argumento:

```python
@shared_task
def generate_export(request_id: str) -> None: ...
```

Não envie um perfil inteiro com dados pessoais pelo broker. O worker busca o registro autorizado,
confere estado/retenção e salva o resultado em local privado.

## Limites configurados

O projeto possui soft/hard time limits, prefetch igual a 1, rejeição quando o worker morre e
reciclagem após várias tasks. Isso reduz travamentos e distribuição desigual, mas não substitui
monitoramento.

## Quando não usar?

Não use Celery para uma operação pequena que precisa terminar antes da resposta. Ele adiciona
Redis, workers, retries e observabilidade. Use quando o ganho de desacoplamento justificar essa
complexidade.
