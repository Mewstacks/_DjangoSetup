# Backend em 5 minutos

[English version](../en/technologies-and-middleware.md)

Este é o ponto de partida. Os links levam a guias mais detalhados.

## O que acontece aqui?

O **frontend** mostra a interface. O **backend** recebe pedidos, verifica regras e acessa dados.
A **API** é o conjunto de endereços, chamados endpoints, usados para conversar com o backend.

```text
Cliente Python → HTTPS → Django/DRF → regra do produto → banco → resposta JSON
```

Exemplo:

```text
GET  /api/v1/invoices/  → listar faturas
POST /api/v1/invoices/  → criar uma fatura
```

## Palavras essenciais

| Termo | Significado simples |
| --- | --- |
| Django | Framework Python que fornece a estrutura do backend |
| DRF | Django REST Framework, usado para criar APIs JSON |
| Serializer | Valida o JSON recebido e controla o JSON devolvido |
| Permission | Decide se o usuário pode executar uma ação |
| Middleware | Camada comum executada antes/depois das views |
| Tenant | Cada cliente ou empresa dentro do mesmo SaaS |
| PostgreSQL | Banco dos dados permanentes |
| Redis | Armazenamento rápido para cache, sessões e filas |
| Celery | Executa trabalhos demorados em background |
| Sentry | Avisa e ajuda a investigar erros |

## O que é tenant?

Um tenant é uma empresa usando o SaaS:

```text
Mesmo sistema e banco
├── Empresa A → enxerga somente seus dados
└── Empresa B → enxerga somente seus dados
```

Neste projeto, `Organization` representa o tenant. O backend valida o
`X-Organization-ID` e cria `request.organization`. Toda consulta de dados de clientes precisa
usar essa organização.

## Segurança em camadas

- HTTPS protege dados em trânsito.
- Sessão e autenticação identificam o usuário.
- Permissions controlam ações.
- Isolamento de tenant separa empresas.
- Serializers rejeitam entrada inválida.
- Argon2 protege hashes de senha.
- AES-GCM cifra campos especialmente sensíveis.
- Axes e throttling reduzem abuso.
- Logs e Sentry ajudam a investigar sem guardar dados pessoais.

Nenhuma camada resolve tudo. LGPD também exige decisões sobre finalidade, base legal, retenção,
fornecedores, direitos dos titulares e incidentes.

## Continue por assunto

Veja a [trilha completa de aprendizado](trilha-aprendizado.md), que cobre a maioria das
tecnologias instaladas. Para começar:

1. [API, Django e DRF](fundamentos/api-django-drf.md): endpoints, views, serializers,
   permissions e consumo com Python.
2. [Tenants e isolamento](fundamentos/tenants-e-isolamento.md): como impedir vazamento entre
   empresas.
3. [Middlewares e segurança](fundamentos/middlewares-e-seguranca.md): por que cada middleware
   existe.
4. [Dados, jobs e observabilidade](fundamentos/dados-jobs-observabilidade.md): PostgreSQL,
   Redis, Celery, arquivos e Sentry.
5. [Adicionar um recurso](adicionando-um-recurso.md): receita prática para implementar uma API.
6. [Modelo de segurança](seguranca.md) e [guia LGPD](lgpd.md): decisões para produção.

Comece pelo fluxo da requisição. Em cada camada, pergunte: **quem está pedindo, pode fazer isso e
quais dados pode enxergar?**
