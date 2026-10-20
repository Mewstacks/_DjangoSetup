# Middlewares e segurança

[English version](../../en/fundamentals/middleware-and-security.md) ·
[Voltar ao resumo](../tecnologias-e-middlewares.md)

## O que é middleware?

Middleware é código executado ao redor de quase toda requisição:

```text
Requisição → M1 → M2 → View
Resposta   ← M1 ← M2 ← View
```

Ele serve para regras transversais. Uma regra específica de faturas deve ficar na aplicação, não
em middleware.

## Por que a ordem importa?

Sessão precisa ser lida antes de identificar o usuário. O usuário precisa ser identificado antes
de validar sua organização. Na resposta, a ordem é invertida.

## Middlewares deste projeto

| Middleware | Responsabilidade | Proteção ou uso real |
| --- | --- | --- |
| `SecurityMiddleware` | HTTPS e headers | HSTS, `nosniff` e políticas do navegador |
| `WhiteNoise` | Estáticos em produção | CSS/JS do Admin, nunca uploads privados |
| `CorsMiddleware` | Origens permitidas | Autoriza um frontend conhecido no navegador |
| `RequestContextMiddleware` | Request ID | Correlaciona resposta, logs e Sentry |
| `SessionMiddleware` | Cookie de sessão | Mantém login entre requisições |
| `CommonMiddleware` | HTTP comum | Normalização de URLs |
| `CsrfViewMiddleware` | Token CSRF | Bloqueia ações forjadas usando cookies |
| `AuthenticationMiddleware` | `request.user` | Identifica o usuário da sessão |
| `OrganizationContextMiddleware` | Tenant atual | Confirma membership antes de selecionar empresa |
| `MessageMiddleware` | Mensagens HTML | Feedback no Django Admin |
| `XFrameOptionsMiddleware` | Bloquear iframe | Reduz clickjacking |
| `ContentSecurityPolicyMiddleware` | Limitar conteúdo | Reduz impacto de conteúdo injetado |
| `AxesMiddleware` | Falhas de login | Bloqueia tentativas repetidas |

## Proteções que costumam ser confundidas

### CORS

Diz a um navegador quais sites podem ler respostas da API. Não autentica usuários e não afeta
scripts Python.

### CSRF

Evita que outro site use automaticamente o cookie de uma pessoa logada para executar uma ação.
Não corrige XSS.

### CSP

Limita de onde scripts, imagens e outros recursos podem ser carregados. É defesa adicional;
escaping e validação continuam necessários.

### Throttling e Axes

Throttle limita frequência da API. Axes acompanha falhas de login. Eles reduzem abuso, mas um
ataque volumétrico ainda exige proteção no edge/WAF.

### Cookies

- `HttpOnly`: JavaScript não lê o cookie.
- `Secure`: envio somente por HTTPS.
- `SameSite`: controla envio entre sites.

Roubar um cookie de sessão ainda pode permitir agir como o usuário, então HTTPS, expiração e
proteção contra XSS continuam importantes.

## Quando criar um middleware?

Crie apenas se a regra:

- vale para muitas rotas;
- precisa acontecer antes/depois das views;
- possui ordem e comportamento de falha bem definidos;
- não adiciona consultas caras sem necessidade.

Nunca registre bodies, senhas, tokens ou dados pessoais indiscriminadamente.

## Segurança em camadas

Middleware não substitui serializers, permissions, escopo de tenant, constraints do banco ou
regras do produto. Uma requisição segura precisa atravessar todas essas barreiras.

Para configurações exatas de produção, leia o [modelo de segurança](../seguranca.md).
