# Dados, jobs e observabilidade

[English version](../../en/fundamentals/data-jobs-observability.md) ·
[Voltar ao resumo](../tecnologias-e-middlewares.md)

## PostgreSQL: fonte principal

PostgreSQL guarda dados que precisam sobreviver: usuários, organizações, consentimentos,
auditoria e registros do produto.

- **Transaction:** salva tudo ou nada.
- **Constraint:** impede estados inválidos no próprio banco.
- **Index:** acelera leituras, com custo de espaço e escrita.
- **Migration:** altera o schema de forma reproduzível.

Backups, criptografia em repouso e testes de restauração continuam sendo responsabilidades
operacionais.

## Redis: rápido e temporário

Redis guarda cache, sessões aceleradas, contadores de throttle/Axes e a fila Celery. Ele é rápido
porque trabalha principalmente em memória.

Não armazene nele a única cópia de algo importante. Se Redis cair, a aplicação deve mostrar a
falha e se recuperar sem perder registros de negócio.

## Celery: trabalho em background

Use Celery quando algo não precisa terminar antes da resposta:

```text
Request → cria job → responde 202
Worker Celery → processa → salva resultado
```

Exemplos: e-mail, exportação LGPD, webhook e relatório. Passe IDs para a task, não um pacote de
dados pessoais.

Tasks podem executar mais de uma vez após falhas. Faça-as **idempotentes**, limite retries e
tempo de execução, e registre o estado no PostgreSQL.

## Object storage: arquivos

O filesystem de uma Machine Fly é efêmero. Uploads e exportações devem ficar em bucket privado,
como Tigris/S3.

- valide tipo e tamanho;
- use nomes imprevisíveis;
- confira autorização em upload e download;
- gere URLs assinadas com expiração;
- defina retenção e localização dos dados.

## Sentry e logs: observabilidade

**Observabilidade** é conseguir entender o sistema olhando erros, logs e métricas.

O request ID liga a resposta aos logs e ao evento do Sentry. O projeto remove cookies, tokens,
bodies e dados pessoais conhecidos antes do envio.

Ainda assim:

- evite registrar dado sensível na origem;
- mantenha scrubbers também no Sentry;
- use retenção mínima;
- restrinja acesso ao projeto;
- não use produção para depurar com dados completos.

Sentry avisa sobre o erro; auditoria registra uma ação de negócio. Um não substitui o outro.

## Health checks

- **Liveness:** o processo está respondendo?
- **Readiness:** PostgreSQL e Redis estão prontos para receber tráfego?

Fly usa essas respostas para decidir quando encaminhar requisições. Readiness não é monitoramento
completo: também acompanhe taxa de erros, latência, conexões do banco e tamanho da fila.

## Escolha rápida

| Necessidade | Ferramenta |
| --- | --- |
| Registro permanente | PostgreSQL |
| Valor temporário e rápido | Redis |
| Trabalho demorado | Celery |
| Upload ou exportação | Object storage |
| Erro técnico | Sentry/logs |
| Quem fez uma ação | Auditoria |

Não adicione infraestrutura por moda. Comece simples e escale a partir de métricas e riscos reais.
