# LGPD (proteção de dados no Brasil): visão geral

> Documentação de engenharia, não aconselhamento jurídico. Prazos, bases legais e o conteúdo dos
> avisos são configurações e dados que você deve confirmar com seu DPO ou advogado. Itens marcados
> **a validar** são interpretações, não fatos.

## O que já vem pronto

| Dever | Onde |
|---|---|
| Saber o que você guarda (art. 37, RoPA) | `<app>/privacy.py` classifica **todo** modelo; um teste falha até você fazer isso, outro quando um campo de cara pessoal não está listado. `manage.py privacy_ropa` exporta o registro das operações; [catálogo](../reference/data-catalog.md) |
| Finalidades e bases legais (arts. 6º-7º) | `ProcessingPurpose` com base legal, categorias de dados, dias de retenção e a consequência da recusa; semeado por `manage.py privacy_seed` |
| Consentimento (art. 8º) | `ConsentRecord`: encadeado por HMAC por pessoa, digests congelados do aviso e da finalidade, evidências (hash de IP, hash de UA). **A revogação é sempre possível** e nunca sofre limite de taxa. Escolhas de cookies de visitantes sem conta são registradas como prova (`POST /api/v1/privacy/cookies/consent/`) |
| Transparência (arts. 9º, 41) | Endpoints públicos: aviso ativo, controlador e DPO (`DPO_*`, `PRIVACY_CONTROLLER_*`, **obrigatórios em produção**), finalidades, suboperadores e transferências, categorias de cookies. Textos em português por padrão (`PRIVACY_MAIL_LANGUAGE`) |
| Direitos do titular (art. 18) | `DataSubjectRequest` para os 11 tipos de solicitação, entrada para quem não tem conta (verificação de e-mail), máquina de estados com transições protegidas, lembretes de prazo; a confirmação diz se há dados |
| Eliminação, anonimização, bloqueio, exportação | Executores guiados pelo catálogo; a exportação é um pacote selado atrás de um link que expira e tem uso limitado; arquivos guardados saem do bucket junto com as linhas |
| Retenção (arts. 15-16) | `manage.py retention_sweep [--dry-run]` cobre modelos com `retention_field`, inclusive uploads, chaves de API, consentimentos de cookies e **contas inativas** (anonimizadas depois da retenção da finalidade sem login; staff e pessoas sob bloqueio legal nunca são varridos) |
| Incidentes (art. 48) | `PersonalDataIncident`: prazo da ANPD em dias úteis (`PRIVACY_INCIDENT_BUSINESS_DAYS`, `PRIVACY_HOLIDAYS`, dobrado por `PRIVACY_SMALL_AGENT`), o mesmo prazo para os titulares afetados, janela de 20 dias úteis para complementar uma comunicação, lembretes, `privacy_incident_export` |
| Relatório de impacto (art. 38) | Modelo `ImpactAssessment` e um [modelo de documento](templates.md) |
| Segurança (art. 46) | Veja [hardening](../security/hardening.md): criptografia em repouso para campos sensíveis, cadeia de auditoria chaveada, MFA, validadores estritos de produção |
| Crianças (art. 14) e o ECA Digital | Veja abaixo |
| Suboperadores e transferências (art. 33) | `SubProcessor` com país e mecanismo de transferência; o `privacy_seed` cria rascunhos **inativos** para os fornecedores da própria plataforma (Sentry, armazenamento de objetos, e-mail, Temporal, hospedagem) que você ativa e completa |

## Crianças e o ECA Digital

O art. 14 da LGPD exige o consentimento específico de um dos pais ou do responsável para dados de
crianças. O ECA Digital (Lei 15.211/2025, em vigor desde 17 de março de 2026; um decreto
regulamentador se seguiu, conforme noticiado: confira o texto primário) vai além para produtos
com probabilidade de uso por menores: verificação de idade confiável e auditável (autodeclaração não
basta), privacidade por concepção e por padrão, e relatório de impacto. **Se ele se aplica ao seu
produto, e qual método é adequado, é uma questão jurídica, e a orientação da ANPD ainda está se
formando: confirme com um advogado.**

O que a plataforma oferece: a categoria de dados `child` (campos precisam ser cifrados), finalidades
com `involves_children` que exigem `guardian_confirmed` no consentimento, e um ponto de encaixe para
verificação de idade: `AGE_ASSURANCE_BACKEND` nomeia uma classe com
`assess(user) -> AgeAssurance` (`apps/privacy/age.py`). Uma concessão de consentimento de quem o
backend aponta como menor é recusada sem confirmação do responsável. O backend padrão admite que não
sabe dizer e não muda nada; um produto voltado a menores deve trocá-lo. Guarde a decisão (`is_minor`,
como foi obtida), nunca o documento.

## Solicitações

`access`, `confirmation`, `correction`, `anonymization`, `blocking`, `deletion`, `portability`,
`consent_withdrawal`, `sharing_information`, `automated_review`, `opposition`.

Caminho de status: `received → verifying → in_progress → (legal_review) → completed | denied | cancelled`.
Nenhuma outra transição existe; as ilegais levantam erro. O prazo-alvo de resposta é
`PRIVACY_REQUEST_TARGET_DAYS` (15) - **a validar** contra a regulamentação em vigor. Correção,
oposição e revisão de decisão automatizada vão para `legal_review`: uma pessoa decide. Tipos
**destrutivos** (eliminação, anonimização, bloqueio) exigem que o solicitante confirme por um link
enviado por e-mail antes de qualquer execução.

## Quem é o controlador

Para os dados de conta e cobrança dos seus clientes você é o controlador; para o que os membros deles
colocam no produto você costuma ser o operador e o cliente o controlador. Veja o
[ADR 17](../adr/controller-and-operator.md) e o
[modelo de acordo de tratamento de dados](templates.md): acerte isso com um advogado antes do primeiro
cliente.

## Executando

O tratamento de DSAR é um flow (workflow do Temporal, ou o motor local), com lembretes em D-5 e D-1 e
um estado de atraso. Jobs: `privacy.dsar_sweep`, `privacy.dsar_sla`, `privacy.incident_deadlines`,
`privacy.retention_sweep`, `privacy.exports_cleanup`.

## Checklist de configuração

1. Defina `PRIVACY_CONTROLLER_NAME`, `PRIVACY_CONTROLLER_ID` (CNPJ), `DPO_NAME`, `DPO_EMAIL`,
   `DPO_CONTACT_URL` (a produção se recusa a iniciar sem controlador e canal do DPO).
2. `python manage.py privacy_seed` e revise cada finalidade (base, retenção, consequência da recusa) com
   um advogado; ative os suboperadores que você usa.
3. Publique um `PrivacyNotice` (imutável depois de ativo; publique uma nova versão para mudar) feito a
   partir dos [modelos](templates.md).
4. Liste os feriados em `PRIVACY_HOLIDAYS` para a conta dos prazos.
5. Registre seus próprios modelos em `<app>/privacy.py` e rode `scripts/gen_docs.py` de novo.
6. `python manage.py doctor` aponta o que ainda falta; revise a [matriz de conformidade](compliance-matrix.md)
   para o que a plataforma não cobre.
