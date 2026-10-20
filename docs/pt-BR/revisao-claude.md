# Mudanças incorporadas após a revisão do Claude

[English version](../en/claude-review.md)

Esta página registra as mudanças encontradas no código após a revisão externa. Ela descreve o
comportamento atual e os trade-offs que precisam ser conhecidos antes de um deploy.

## Autenticação e proteção contra abuso

- O login agora entrega o `HttpRequest` original ao django-axes. Isso permite que o middleware
  reconheça corretamente o estado de lockout e devolva `429` com `Retry-After`, em vez de deixar
  a tentativa cair em um `401` comum.
- `axes_username` normaliza o e-mail recebido como `email` ou `username`. As falhas passam a ser
  associadas à conta atacada, evitando que todas sejam registradas como usuário vazio.
- `AXES_LOCKOUT_BY_USERNAME=false` é configurável. Quando `true`, também bloqueia por conta e
  reduz brute force distribuído entre muitos IPs. O custo é permitir que terceiros provoquem
  lockout deliberado de uma conta; a ativação deve ser uma decisão de risco.
- Throttles anônimos e de login usam apenas o IP validado pelo backend. `X-Forwarded-For`
  controlado pelo cliente não cria novos buckets. No Fly.io, `Fly-Client-IP` é confiável somente
  quando `FLY_APP_NAME` existe; fora dele, usa-se `REMOTE_ADDR`.
- Throttles autenticados continuam prioritariamente por usuário, conforme o DRF, mas qualquer
  fallback por IP usa o identificador validado.

## Criptografia

`EncryptedTextField` agora usa o nome do model e da coluna como Associated Authenticated Data
(AAD) do AES-256-GCM. Um ciphertext copiado para outra coluna falha na autenticação em vez de
ser decriptado silenciosamente.

Limites e migração:

- O vínculo é por coluna, não por linha; trocar ciphertexts entre registros da mesma coluna
  ainda é possível para alguém com escrita direta no banco.
- Ciphertexts criados pela versão antiga do campo não possuem esse AAD e não serão decriptados
  automaticamente pela nova versão.
- Se já houver dados reais, crie e teste uma migração gradual que leia com o formato antigo e
  regrave com o novo AAD antes do deploy definitivo. Não remova chaves antigas até backups e
  registros antigos expirarem.

## Performance e disponibilidade

- A listagem de organizações usa subquery e annotation para obter o papel do usuário. Ela não
  carrega todos os membros de cada organização e evita `distinct()` desnecessário.
- Há teste garantindo que a quantidade de queries da listagem não cresce com o número de
  membros.
- O readiness check público mantém resultado em memória por worker durante
  `HEALTH_READINESS_CACHE_SECONDS` (padrão `5`). Isso reduz queries e escritas no Redis sem
  aplicar throttle dependente do próprio Redis. Use `0` para desabilitar o cache.
- Eventos de auditoria continuam validando campos e metadados, mas pulam validações ORM de
  unicidade/constraints no hot path. UUIDs são gerados na aplicação e o banco continua
  aplicando suas constraints.
- Gunicorn recicla workers após aproximadamente 1.000 requests, com jitter de 100, reduzindo
  crescimento prolongado de memória e evitando reinícios simultâneos.

## Cookies cross-site

`SESSION_COOKIE_SAMESITE` e `CSRF_COOKIE_SAMESITE` agora são configuráveis. O padrão continua
`Lax`. Use `None` somente quando o cliente web estiver em outro site e sempre com HTTPS/cookies
Secure. Produção rejeita valores diferentes de `Lax`, `Strict` ou `None`.

Clientes Python server-to-server não dependem de CORS ou SameSite, mas continuam usando sessão e
CSRF quando consomem estes endpoints de autenticação.

## Testes adicionados

- Lockout real após tentativas repetidas e resposta `429`.
- Isolamento do lockout por conta.
- Normalização do usuário para django-axes.
- Impossibilidade de forjar buckets variando `X-Forwarded-For`.
- Acesso ao IP pelo request DRF subjacente e fallback seguro para IP inválido.
- Rejeição de ciphertext movido entre colunas.
- Papel do usuário na criação/listagem de organizações e limite de queries.

Antes de publicar, execute toda a suíte, `mypy`, Ruff, `check --deploy` e teste a compatibilidade
de dados criptografados em staging.
