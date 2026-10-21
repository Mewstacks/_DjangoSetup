# Modelos de documentos da LGPD

Pontos de partida para os documentos que a LGPD pede que você tenha. **São modelos, não
aconselhamento jurídico.** O texto depende do seu tratamento, dos seus contratos e do seu setor; peça a
um advogado com experiência em LGPD que adapte e aprove cada um antes de publicar ou assinar. Os
marcadores são `{{assim}}`.

| Documento | Modelo | Usado com |
|---|---|---|
| Aviso de privacidade (arts. 6º, 9º, 18) | [English](../../templates/privacy-policy.en.md) - [Português](../../templates/privacy-policy.pt-BR.md) | `PrivacyNotice`; o endpoint público de transparência |
| Termos de uso | [English](../../templates/terms-of-service.en.md) - [Português](../../templates/terms-of-service.pt-BR.md) | Fluxo de cadastro |
| Acordo de tratamento de dados (arts. 5º, 39, 42) | [English](../../templates/data-processing-agreement.en.md) - [Português](../../templates/data-processing-agreement.pt-BR.md) | Clientes para os quais você é operador |
| Relatório de impacto, RIPD (art. 38) | [English](../../templates/dpia-ripd.en.md) - [Português](../../templates/dpia-ripd.pt-BR.md) | Modelo `ImpactAssessment` |

## Preenchendo a partir da plataforma

- **Controlador e DPO**: `PRIVACY_CONTROLLER_NAME`, `PRIVACY_CONTROLLER_ID`, `DPO_NAME`,
  `DPO_EMAIL`, `DPO_CONTACT_URL` (também publicados por `GET /api/v1/privacy/transparency/`).
- **O que você coleta e por quê**: `python manage.py privacy_ropa` imprime o registro gerado a partir
  do catálogo de dados; finalidades, bases legais e retenção vêm de `ProcessingPurpose`.
- **Quem mais vê os dados**: as linhas ativas de `SubProcessor` (nome, país, mecanismo de
  transferência).
- **Por quanto tempo guarda**: `retention_days` de cada finalidade, mais `AUDIT_RETENTION_DAYS`.
- **Direitos e como usá-los**: o endpoint público de solicitações e a meta de resposta de 15 dias.
- **Cookies**: as categorias em `GET /api/v1/privacy/cookies/` e o registro de consentimento que você
  guarda.

## Publicando o aviso

Um `PrivacyNotice` publicado é imutável (consentimentos apontam para o checksum). Coloque o documento
numa URL estável, calcule o SHA-256 **do documento**, crie o aviso com os dois e ative-o. Para mudar,
publique uma nova versão.

## Ritmo de revisão

Releia o aviso e o registro quando adicionar uma finalidade, um suboperador, um país ou uma categoria
de dados; no mínimo uma vez por ano nos demais casos.
