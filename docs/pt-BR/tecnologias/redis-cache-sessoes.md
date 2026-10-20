# Redis, cache e sessões

[English version](../../en/technologies/redis-cache-sessions.md) ·
[Voltar à trilha](../trilha-aprendizado.md)

## O que é Redis?

Redis é um armazenamento muito rápido, normalmente em memória. Ele é ótimo para dados temporários
ou reconstruíveis, não para ser a única cópia de um registro importante.

Neste projeto ele atende:

- cache;
- aceleração de sessões;
- contadores de throttle e django-axes;
- broker e resultados do Celery.

## Cache

Cache guarda temporariamente um resultado caro:

```text
Primeira leitura → PostgreSQL → coloca no Redis
Próxima leitura → Redis → resposta mais rápida
```

Defina tempo de expiração e invalidação. Cache antigo pode mostrar dado incorreto ou de outro
tenant. Inclua o ID da organização na chave e evite cachear dados sensíveis sem necessidade.

## Sessões

O backend usa `cached_db`: PostgreSQL mantém a sessão persistente e Redis acelera a leitura. O
navegador guarda apenas um identificador em cookie, não todos os dados da sessão.

Cookies `HttpOnly`, `Secure` e `SameSite` reduzem riscos, mas uma sessão roubada ainda é perigosa.

## Rate limit e login

DRF guarda contadores de throttling no cache; Axes guarda falhas de login. Um Redis compartilhado
faz todas as Machines enxergarem os mesmos contadores. Cache local permitiria ao atacante ganhar
um novo limite em cada instância.

## Falhas e escala

`IGNORE_EXCEPTIONS=False` faz a falha aparecer em vez de fingir que o cache funcionou. Readiness
devolve erro quando Redis não está pronto. Essa escolha evita degradação silenciosa de controles
de segurança.

Use `CACHE_KEY_PREFIX` diferente por produto e ambiente. Monitore memória, latência, conexões,
evictions e persistência adequada ao broker.

## Regra prática

Pergunte: “se este valor desaparecer agora, consigo reconstruí-lo?” Se não, ele provavelmente
pertence ao PostgreSQL. Redis melhora desempenho e coordenação; não corrige uma query ruim nem
substitui modelagem de dados.
