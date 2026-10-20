# Runtime, Docker, and Fly.io

[Versão em português](../../pt-BR/tecnologias/runtime-docker-fly.md) ·
[Back to the learning path](../learning-path.md)

## ASGI, Uvicorn, and Gunicorn

**ASGI** is the contract between a Python server and application. **Uvicorn** runs the ASGI app.
**Gunicorn** manages multiple Uvicorn workers:

```text
Fly Proxy → Gunicorn → Uvicorn worker → Django
                         Uvicorn worker → Django
```

Other workers can continue if one hangs. Request-based recycling helps control memory growth.
More workers add concurrency but also memory and database connections.

## Docker

Docker builds an image containing Python, dependencies, and the app. The same image runs in CI,
staging, and production, reducing environment drift.

The container runs as non-root, limiting some intrusion impact. The process still accesses
everything its credentials allow. Keep images small, pin dependencies, and never store secrets in
layers.

## Fly.io

Fly runs the image as Machines and provides a proxy, TLS, private networking, and health checks.
`fly.toml` declares processes, region, ports, and checks.

```text
build image → release migrations → start Machines → health checks → traffic
```

A failed migration should prevent the version from receiving traffic.

## Scale and security

Scale web and workers independently. Measure p95 latency, CPU, memory, database connections,
Redis, queue age, and error rate first. Horizontal scale requires state outside the Machine.

Use Fly secrets, MFA/SSO, restricted deploy tokens, and separate environments. Docker packages the
app and Fly runs it; neither fixes authorization or replaces backups and incident response.
