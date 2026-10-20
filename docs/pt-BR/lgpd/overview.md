# LGPD - visão geral

> Documentação de engenharia, não parecer jurídico. Prazos, bases legais e o conteúdo dos avisos
> são configurações e dados que você deve confirmar com o encarregado (DPO) ou o jurídico. Itens
> marcados como **validar** são interpretações, não fatos.

## O que já vem pronto

| Dever | Onde |
|---|---|
| Saber o que se guarda (art. 37, RoPA) | `<app>/privacy.py` classifica **todo** model; um teste falha até você fazê-lo. `manage.py privacy_ropa` exporta o registro das operações; [catálogo](../reference/data-catalog.md) |
| Finalidades e bases legais (arts. 6-7) | `ProcessingPurpose` com base legal, categorias de dados, dias de retenção; semeado por `manage.py privacy_seed` |
| Consentimento (art. 8) | `ConsentRecord`: cadeia de hash por pessoa, digests congelados do aviso e da finalidade, evidência (hash de IP e de UA). **A retirada é sempre possível** e nunca sofre rate limit |
| Transparência (arts. 9, 41) | Endpoints públicos: aviso ativo, controlador e encarregado (`DPO_*`, `PRIVACY_CONTROLLER_*`), finalidades, suboperadores e transferências, categorias de cookies |
| Direitos do titular (art. 18) | `DataSubjectRequest` para os 11 tipos, entrada para quem não tem conta (verificação de e-mail), máquina de estados com transições protegidas, lembretes de SLA |
| Eliminação, anonimização, bloqueio, exportação | Executores guiados pelo catálogo; a exportação é um pacote selado atrás de link com validade (`PRIVACY_EXPORT_TTL_DAYS`) |
| Retenção (arts. 15-16) | `manage.py retention_sweep [--dry-run]`; `LegalHold` congela as linhas de uma pessoa |
| Incidentes (art. 48) | `PersonalDataIncident` com o prazo de comunicação à ANPD em dias úteis (`PRIVACY_INCIDENT_BUSINESS_DAYS`, `PRIVACY_HOLIDAYS`) e lembretes |
| Segurança (art. 46) | Veja [hardening](../security/hardening.md): criptografia de campos sensíveis, cadeia de auditoria, MFA, validadores estritos de produção |
| Crianças (art. 14) | A categoria `child` no catálogo marca campos de tratamento específico; a evidência de consentimento sustenta registros de responsável |

## Requisições

`access`, `confirmation`, `correction`, `anonymization`, `blocking`, `deletion`, `portability`,
`consent_withdrawal`, `sharing_information`, `automated_review`, `opposition`.

Caminho de status: `received → verifying → in_progress → (legal_review) → completed | denied |
cancelled`. Não existe outra transição; as ilegais levantam erro. O prazo-alvo de resposta é
`PRIVACY_REQUEST_TARGET_DAYS` (15) - **validar** contra a norma em vigor. Tipos **destrutivos**
(eliminação, anonimização, bloqueio) exigem que o solicitante confirme por link enviado por
e-mail antes de qualquer execução.

## Em operação

O processamento de DSAR é um fluxo (workflow Temporal ou motor local), com lembretes em D-5 e D-1
e um estado de atraso. Jobs: `privacy.dsar_sweep`, `privacy.dsar_sla`,
`privacy.incident_deadlines`, `privacy.retention_sweep`.

## Checklist de configuração

1. Defina `PRIVACY_CONTROLLER_NAME`, `PRIVACY_CONTROLLER_ID` (CNPJ), `DPO_NAME`, `DPO_EMAIL`,
   `DPO_CONTACT_URL`.
2. `python manage.py privacy_seed` e revise cada finalidade (base, retenção) com o jurídico.
3. Publique um `PrivacyNotice` (imutável depois de ativo; publique nova versão para mudar).
4. Liste os feriados em `PRIVACY_HOLIDAYS` para o cálculo dos prazos.
5. Registre seus models em `<app>/privacy.py` e rode `scripts/gen_docs.py`.
6. Leia a [matriz de conformidade](compliance-matrix.md) para ver o que a plataforma não cobre.
