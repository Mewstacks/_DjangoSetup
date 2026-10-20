# Guia de implementação da LGPD

[English version](../en/lgpd.md)

O código ajuda a produzir evidências de responsabilidade; as decisões legais continuam sendo
do controlador. Antes do lançamento, defina responsáveis e revise o produto com profissionais
de privacidade e direito.

## Inventário de dados

Para cada fluxo de dados pessoais, registre:

- papéis de controlador, operador e suboperadores;
- finalidade e base legal — consentimento não é padrão universal;
- titulares, categorias, origem, destinatários e transferências internacionais;
- campos mínimos, gatilho/período de retenção, eliminação e anonimização;
- controles, avaliação de alto risco e necessidade de RIPD.

Represente finalidades em `ProcessingPurpose`, publique um aviso versionado com checksum
SHA-256 e use `ConsentRecord` somente para bases de consentimento. A retirada cria um novo
evento e não apaga a evidência anterior.

## Direitos dos titulares

Usuários autenticados criam e acompanham solicitações sem dados pessoais nos logs. A operação
deve verificar identidade proporcionalmente, evitar documentos desnecessários, encaminhar aos
responsáveis e registrar o resultado.

O alvo operacional padrão é 15 dias corridos para resposta completa de acesso, mas a LGPD
também exige atendimento imediato quando possível e prazos variam. Cada produto deve
implementar exportação, correção, bloqueio, portabilidade e eliminação considerando retenção
legal, fraude, backups, operadores e anonimização.

## Retenção

- Defina período por finalidade; “para sempre” sem justificativa não é aceitável.
- Jobs devem processar lotes limitados, permitir dry-run e gerar evidência agregada sem dados
  pessoais em argumentos.
- Legal holds devem ser explícitos, aprovados, temporários e revisáveis.
- Registros de incidentes com dados pessoais possuem guarda mínima de cinco anos.

## Incidentes

Use `PersonalDataIncident` e o runbook. Confirme o envolvimento de dados pessoais, avalie risco
ou dano, preserve evidências e deixe controlador/DPO decidir a notificação. A Resolução
CD/ANPD 15/2024 geralmente determina três dias úteis quando houver risco ou dano relevante.
Prazos e feriados devem ser confirmados por responsáveis habilitados.

## Fornecedores e transferências internacionais

Faça due diligence e contratos adequados para Fly.io, Postgres, Upstash, Tigris, Sentry,
e-mail, pagamentos e demais fornecedores. Tigris é distribuído globalmente; não presuma
residência exclusiva no Brasil. Quando necessário, use object storage privado em região
brasileira e atualize o inventário e contratos.

## Evidências

Preserve avisos aprovados, inventário, avaliações de legítimo interesse/RIPD, contratos,
revisões de acesso, treinamentos, testes de restauração, rotações de chave, remediações,
resultados de solicitações e decisões de incidentes em repositório controlado.

Referências oficiais:

- [Texto consolidado da LGPD](https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709.htm)
- [Direitos dos titulares — ANPD](https://www.gov.br/anpd/pt-br/assuntos/titular-de-dados-1/direito-dos-titulares)
- [Comunicação de incidentes — ANPD](https://www.gov.br/anpd/pt-br/canais_atendimento/agente-de-tratamento/comunicado-de-incidente-de-seguranca-cis)
