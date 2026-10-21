# Webhooks

Eventos de saída com outbox transacional: o evento é gravado na mesma transação da mudança que
ele anuncia, então um rollback nunca o envia e um commit nunca o perde.

```python
# <app>/events.py
register_event("order.paid", "Um pedido foi pago. Dados: order_id.")
# dentro da transação que altera o pedido
emit("order.paid", ctx.organization, {"order_id": str(order.id)})
```

Eventos são **finos**: ids, não documentos. Quem recebe busca os dados com as próprias
credenciais.

## Recebendo

Cabeçalhos: `X-Webhook-Id` (estável entre tentativas: deduplique por ele), `X-Webhook-Timestamp`,
`X-Webhook-Signature: v1=<hex>`, onde o valor é o HMAC-SHA256 de `"<timestamp>.<corpo>"` com o
segredo do endpoint. Rejeite timestamps com mais de poucos minutos. Durante a rotação do segredo
duas assinaturas são enviadas (separadas por espaço); aceite qualquer uma.

## Gerenciando

`/api/v1/webhooks/endpoints/` (owners/admins): criar (segredo devolvido uma vez), atualizar,
rotacionar (`rotate-secret`), enviar teste (`test`). `/api/v1/webhooks/deliveries/` lista o
histórico e faz `redeliver`. Endpoints precisam ser https e resolver para endereços públicos.

## Entrega

Workflow com backoff de 1m, 5m, 30m, 2h, 6h, 24h (ou o job `webhooks.dispatch_due` sem
Temporal). Um lock de claim evita envio duplo. Após `WEBHOOK_DISABLE_AFTER` falhas seguidas o
endpoint é desligado e um evento de auditoria é gravado.

## Proteção SSRF

`apps.common.netguard` é usado em toda chamada de saída: só https, todo endereço resolvido deve
ser globalmente roteável (faixas privadas, NAT de operadora, metadados de nuvem e formas em túnel,
como NAT64 ou 6to4 embrulhando um IPv4 privado, são recusados), a conexão vai ao IP validado (sem
DNS rebinding), redirecionamentos nunca são seguidos, nenhum proxy do ambiente é usado, a chamada
tem um prazo total, e respostas têm tamanho limitado e nunca são descomprimidas. Uma cota por
organização limita o número de endpoints (`QUOTA_WEBHOOK_ENDPOINTS_PER_ORG`).
