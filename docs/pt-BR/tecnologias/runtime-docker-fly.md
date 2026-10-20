# Runtime, Docker e Fly.io

[English version](../../en/technologies/runtime-docker-fly.md) ·
[Voltar à trilha](../trilha-aprendizado.md)

## ASGI, Uvicorn e Gunicorn

**ASGI** é o contrato entre servidor e aplicação Python. **Uvicorn** executa a aplicação ASGI.
**Gunicorn** gerencia vários workers Uvicorn:

```text
Fly Proxy → Gunicorn → worker Uvicorn → Django
                         worker Uvicorn → Django
```

Se um worker travar, os outros podem continuar. Reciclagem por número de requests ajuda a conter
crescimento de memória. Mais workers aumentam concorrência, mas também memória e conexões ao
banco.

## Docker

Docker cria uma imagem com Python, dependências e aplicação. A mesma imagem pode rodar em CI,
staging e produção, reduzindo diferenças de ambiente.

O container roda como usuário não-root. Isso limita parte do dano de uma invasão, mas o processo
ainda acessa tudo que suas credenciais autorizam. Use imagem pequena, dependências fixadas e não
grave segredos em camadas.

## Fly.io

Fly executa a imagem em Machines e fornece proxy, TLS, rede privada e health checks. O projeto usa
`fly.toml` para declarar processos, região, portas e verificações.

Fluxo de deploy:

```text
build da imagem → release_command/migrations → iniciar Machines → health checks → tráfego
```

Se a migration falhar, a versão não deve receber tráfego.

## Escala

Web e worker escalam separadamente. Antes de aumentar Machines, meça:

- latência p95;
- CPU e memória;
- conexões/queries PostgreSQL;
- latência e memória Redis;
- tamanho e idade da fila;
- taxa de erros.

Escala horizontal exige estado fora da Machine: PostgreSQL, Redis e object storage.

## Segurança operacional

Use secrets do Fly, MFA/SSO na organização, tokens de deploy restritos e ambientes separados.
Mantenha serviços na região adequada, avalie transferência internacional e restrinja Admin/docs
em produção.

Docker facilita empacotamento; Fly facilita operação. Nenhum dos dois corrige falhas de
autorização ou substitui backups, monitoramento e resposta a incidentes.
