# OpenAPI, drf-spectacular e Swagger

[English version](../../en/technologies/openapi-swagger.md) ·
[Voltar à trilha](../trilha-aprendizado.md)

## O que são?

**OpenAPI** é um formato que descreve uma API: rotas, métodos, parâmetros, autenticação, bodies e
respostas. **drf-spectacular** gera esse schema a partir do DRF. **Swagger UI** mostra uma tela
interativa baseada nele.

```text
Views + serializers → drf-spectacular → openapi-schema.yml → Swagger/clientes
```

## Por que importa?

Sem contrato, frontend e backend dependem de memória e mensagens. Com OpenAPI:

- pessoas descobrem como chamar endpoints;
- CI detecta schema inválido;
- clientes podem ser gerados;
- mudanças incompatíveis ficam mais visíveis;
- exemplos e códigos de erro ficam centralizados.

## Schema não é segurança

Documentar `401` não adiciona autenticação. Cada endpoint ainda precisa de authentication,
permission, serializer, throttle e escopo de tenant.

Não coloque tokens ou dados reais nos exemplos. Em produção, a interface interativa fica
desabilitada por padrão para reduzir superfície e exposição desnecessária.

## Boas práticas

- descreva request e response reais;
- documente headers como `X-Organization-ID`;
- registre todos os status importantes;
- use nomes e versões estáveis;
- valide o schema no CI;
- revise alterações do schema como alterações de código;
- prefira exemplos sintéticos.

O versionamento `/api/v1/` permite criar uma versão incompatível no futuro sem quebrar clientes
imediatamente. Mudanças aditivas ainda devem ser comunicadas e testadas.

## Quando consultar?

Use Swagger para explorar durante desenvolvimento e o arquivo OpenAPI como contrato automatizado.
Para aprender o fluxo interno, ainda leia view, serializer, permission e testes.
