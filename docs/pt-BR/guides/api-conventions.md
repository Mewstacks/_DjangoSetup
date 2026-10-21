# Convenções da API

Um só conjunto de regras para todo endpoint, para que um cliente escrito para um funcione no próximo.

## Erros

Todo erro, de qualquer superfície (REST, MCP, middleware, bloqueio), tem um envelope:

```json
{"error": {"status": 422, "code": "invalid", "detail": "Invalid input.", "request_id": "..."}}
```

`detail` é texto escrito para quem chama; na validação é uma lista de `{field, message}` e **nunca
repete a entrada** (pode ser dado pessoal). `code` é estável e feito para programas. Erros internos
são `500 server_error` só com o `request_id` (também o cabeçalho `X-Request-ID`): cite-o a quem opera.

| Status | Códigos que você vai encontrar |
|---|---|
| 400 | Validação de campos do DRF em viewsets clássicos |
| 401 | `authentication_required`; chave ou token ruim é um 401 genérico com `WWW-Authenticate` |
| 403 | `forbidden`, `missing_scope`, `read_only_role`, `role_forbidden`, `quota_exceeded`, `reauthentication_required`, `mfa_required` |
| 404 | `not_found` (também para linha de outro tenant e para ação num canal em que ela não está listada) |
| 409 | `conflict`, `idempotency_key_reused`, recusas de domínio como `note_archived` |
| 413 | `payload_too_large` |
| 408 | `request_timeout` (corpo de requisição que nunca terminou) |
| 422 | `invalid` (entrada de ação), `blocked_address` |
| 429 | `rate_limited`, `authentication_locked`; respeite o `Retry-After` |

## Idempotência

Envie `Idempotency-Key` (1-128 caracteres de `A-Za-z0-9._:-`) em qualquer ação que possa ser repetida.
A mesma chave com o mesmo corpo repete a resposta guardada e define `Idempotent-Replayed: true`; a
mesma chave com corpo diferente é `409 idempotency_key_reused`. As chaves são escopadas por
organização e pessoa e guardadas por 24 horas. As respostas guardadas são cifradas.

## Paginação

Listas clássicas usam número de página: `?page=2&page_size=50` (padrão 50, máximo 200) e respondem
`count`, `next`, `previous`, `results`. Ações que listam usam `limit` e `offset` e respondem `total`,
`returned` e `next_offset` (nulo na última página).

## Versionamento e descontinuação

A URL leva a versão maior (`/api/v1/`). Dentro de uma versão maior as mudanças são aditivas: campos
novos, ações novas, parâmetros opcionais novos. O que está sendo aposentado responde com
`Deprecation: true` e um cabeçalho `Link: <sucessor>; rel="successor-version"` por pelo menos uma
versão, e o CHANGELOG diz quando sai. O login JSON só com senha (`/api/v1/auth/login/`) vem
desligado (`LEGACY_LOGIN_ENABLED`); use os endpoints do allauth.

## Limites de taxa

Por endereço do cliente (anônimo e autenticado), por credencial e minuto para ações
(`ACTIONS_RATE_*`), por endereço para o MCP. `429` traz `Retry-After`. Falhas de autenticação são
contadas por id de chave e endereço, e por endereço no total, então um remetente não consegue
bloquear um dono, e espalhar muitos ids a partir de um só lugar é contido.

## Tenancy

Sessões escolhem a organização com `X-Organization-ID`; chaves e tokens são fixos a uma. Uma linha de
outro tenant é `404`, nunca `403`: a API não confirma que ela existe.

## Tempo e ids

Timestamps são ISO 8601 em UTC. Ids são UUIDs. Dinheiro e quantidades são strings ou inteiros, como
o recurso documentar; nunca floats.
