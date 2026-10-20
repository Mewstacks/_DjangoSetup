# Middleware and security

[Versão em português](../../pt-BR/fundamentos/middlewares-e-seguranca.md) ·
[Back to the summary](../technologies-and-middleware.md)

## What is middleware?

Middleware is code executed around almost every request:

```text
Request  → M1 → M2 → View
Response ← M1 ← M2 ← View
```

It is for cross-cutting rules. An invoice-specific rule belongs in application code, not
middleware.

## Why does order matter?

The session must be loaded before identifying the user. The user must be identified before
checking their organization. Response order is reversed.

## Middleware in this project

| Middleware | Responsibility | Protection or real use |
| --- | --- | --- |
| `SecurityMiddleware` | HTTPS and headers | HSTS, `nosniff`, and browser policies |
| `WhiteNoise` | Production static files | Admin CSS/JS, never private uploads |
| `CorsMiddleware` | Allowed origins | Authorizes a known browser frontend |
| `RequestContextMiddleware` | Request ID | Correlates response, logs, and Sentry |
| `SessionMiddleware` | Session cookie | Keeps login between requests |
| `CommonMiddleware` | Common HTTP behavior | URL normalization |
| `CsrfViewMiddleware` | CSRF token | Blocks forged cookie-based actions |
| `AuthenticationMiddleware` | `request.user` | Identifies the session user |
| `OrganizationContextMiddleware` | Current tenant | Confirms membership before selecting a company |
| `MessageMiddleware` | HTML messages | Feedback in Django Admin |
| `XFrameOptionsMiddleware` | Block frames | Reduces clickjacking |
| `ContentSecurityPolicyMiddleware` | Restrict content | Reduces impact of injected content |
| `AxesMiddleware` | Login failures | Blocks repeated attempts |

## Commonly confused protections

### CORS

Tells a browser which sites may read API responses. It does not authenticate users and does not
affect Python scripts.

### CSRF

Stops another website from automatically using a logged-in person's cookie to perform an action.
It does not fix XSS.

### CSP

Restricts where scripts, images, and other resources may load from. It is an additional defense;
escaping and validation remain necessary.

### Throttling and Axes

Throttling limits API frequency. Axes tracks login failures. They reduce abuse, but volumetric
attacks still require edge/WAF protection.

### Cookies

- `HttpOnly`: JavaScript cannot read the cookie.
- `Secure`: sent only over HTTPS.
- `SameSite`: controls cross-site sending.

A stolen session cookie may still let an attacker act as the user, so HTTPS, expiration, and XSS
protection remain important.

## When should I create middleware?

Only create it if the rule:

- applies to many routes;
- must happen before or after views;
- has a defined order and failure behavior;
- does not add unnecessary expensive queries.

Never log bodies, passwords, tokens, or personal data indiscriminately.

## Security in layers

Middleware does not replace serializers, permissions, tenant scoping, database constraints, or
product rules. A secure request must cross all these boundaries.

For exact production settings, read the [security model](../security.md).
