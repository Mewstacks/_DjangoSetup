# Matriz de conformidade LGPD

Artigo → recurso da plataforma → código → teste. "Operador" significa que a organização que roda
o sistema ainda precisa fazer algo. Interpretações estão marcadas como **validar**.

| Art. | Exigência | Plataforma | Código | Teste |
|---|---|---|---|---|
| 6 | Princípios (finalidade, necessidade, segurança) | Finalidades com retenção; a classificação força uma decisão por model | `privacy.models.ProcessingPurpose`, `privacy.catalog` | `test_every_model_has_been_classified` |
| 7-8 | Base legal; consentimento | Base por finalidade; registros de consentimento com digest congelado do aviso, cadeia | `privacy.models.ConsentRecord` | `test_lgpd` (cadeia, retirada) |
| 9 | Acesso a informações sobre o tratamento | Aviso público, finalidades, suboperadores | `privacy.public_api` | `test_lgpd` (endpoints públicos) |
| 11 | Dados sensíveis | Categoria `sensitive`; campos cifrados | `privacy.catalog.Category`, `common.encryption` | `test_security_regressions` |
| 14 | Crianças | Categoria `child`; o operador define o fluxo do responsável | catálogo | teste do catálogo (operador) |
| 15-16 | Término do tratamento; retenção | Varredura com dry run; legal holds | `privacy.retention` | `test_lgpd` (retenção) |
| 18 | Direitos do titular | 11 tipos de requisição, executores, SLA | `privacy.services`, `privacy.workflows` | `test_lgpd` (requisições ponta a ponta) |
| 18 V | Portabilidade | Pacote de exportação; **formato da ANPD ainda pendente** (validar) | `privacy.services` | teste de exportação |
| 19 | Prazos de resposta | Setting de dias-alvo; lembretes; atraso | `privacy.deadlines`, `privacy.jobs` | `test_lgpd` (SLA) |
| 37 | Registro das operações | Exportação do RoPA a partir do catálogo | `manage.py privacy_ropa` | `test_lgpd` |
| 38 | Relatório de impacto (RIPD) | Operador: catálogo e RoPA são insumos | - | - |
| 41 | Encarregado | `DPO_*` publicado; endpoint de contato | `privacy.public_api` | teste do endpoint público |
| 46-47 | Segurança | Hardening, MFA, criptografia, validadores estritos de produção | veja [hardening](../security/hardening.md) | `test_security_regressions` |
| 48 | Comunicação de incidente | Modelo de incidente, prazo em dias úteis, lembretes (**3 dias úteis: validar**) | `privacy.deadlines`, `PersonalDataIncident` | `test_lgpd` (prazos) |
| 50 | Governança | Cadeia de auditoria, runbooks | `audit`, [runbooks](../deploy/runbooks.md) | `test_audit_integrity` |

Fora do alcance do software: escolher bases legais, redigir avisos, cláusulas de transferência
internacional, conteúdo do RIPD, treinamento, contratos com operadores. A plataforma entrega o
registro, a evidência e os executores; as decisões são de pessoas.
