# Matriz de conformidade com a LGPD

Artigo → recurso da plataforma → código → teste. "Operador" significa que a organização que roda o
sistema ainda precisa fazer algo. Interpretações estão marcadas **a validar**.

| Art. | Exigência | Plataforma | Código | Teste |
|---|---|---|---|---|
| 5º, 39, 42 | Controlador e operador | Orientação, modelo de DPA; modelo de dados não dividido por papel ([ADR 17](../adr/controller-and-operator.md)); operador: decida e registre | - | - |
| 6º | Princípios (finalidade, necessidade, segurança) | Finalidades com retenção; a classificação força uma decisão por modelo | `privacy.models.ProcessingPurpose`, `privacy.catalog` | `test_every_model_has_been_classified`, `test_catalog_lint` |
| 7º-8º | Base legal; consentimento | Base por finalidade; registros de consentimento com digest congelado do aviso, cadeia chaveada; escolhas de cookies de visitantes | `privacy.models.ConsentRecord`, `CookieConsent` | `test_lgpd`, `test_lgpd_extras` |
| 8º §2º | Prova do consentimento | Cadeia de hash chaveada, hashes de evidência | `common.encryption.chain_digest` | `test_lgpd` |
| 9º | Acesso à informação sobre o tratamento | Aviso público, finalidades (com a consequência da recusa), suboperadores | `privacy.public_api` | `test_lgpd`, `test_lgpd_extras` |
| 11 | Dados sensíveis | Categoria `sensitive`; campos cifrados impostos por teste; **restringir as bases permitidas é trabalho do operador (a validar)** | `privacy.catalog.Category`, `common.encryption` | `test_catalog_lint` |
| 12 | Dados anonimizados | Executores de anonimização; linhas de auditoria pseudonimizadas são mantidas: **se são dados pessoais é a validar** | `privacy.services` | `test_lgpd` |
| 14 | Crianças | Categoria `child` (cifrada), confirmação do responsável, ponto de encaixe de verificação de idade, notas do ECA Digital; o operador escolhe o método | `privacy.age`, `ProcessingPurpose.involves_children` | `test_lgpd_extras` |
| 15-16 | Término do tratamento; retenção | Varredura com dry run; contas inativas, uploads, chaves, consentimentos de cookies; bloqueios legais | `privacy.retention` | `test_lgpd`, `test_lgpd_retention` |
| 18 I | Confirmação | A resposta diz se há dados | `privacy.services` | `test_lgpd_extras` |
| 18 II, V | Acesso; portabilidade | Exportação selada, link de uso limitado; **formato da ANPD ainda pendente** (a validar) | `privacy.services` | `test_export_link` |
| 18 III | Correção | Encaminhada a uma pessoa (`legal_review`) | `privacy.services` | `test_lgpd` |
| 18 IV, VI | Anonimização, bloqueio, eliminação | Executores a partir do catálogo; arquivos guardados removidos; confirmação por e-mail | `privacy.services`, `uploads.signals` | `test_lgpd`, `test_lgpd_retention` |
| 18 VII | Com quem os dados são compartilhados | Suboperadores ativos; rascunhos dos fornecedores da própria plataforma | `privacy.public_api`, `privacy_seed` | `test_lgpd_extras` |
| 18 VIII | Consequência de recusar o consentimento | `ProcessingPurpose.refusal_consequence`, publicada junto com a finalidade | `privacy.public_api` | `test_lgpd_extras` |
| 18 IX | Revogação | Sempre possível, nunca limitada | `privacy.services` | `test_lgpd` |
| 19 | Prazos de resposta | Configuração de dias-alvo; lembretes; atraso | `privacy.deadlines`, `privacy.jobs` | `test_lgpd` |
| 33 | Transferência internacional | `SubProcessor.transfer_mechanism`, país; **textos de cláusulas e cláusulas-padrão da ANPD são trabalho do operador (Res. CD/ANPD 19/2024)** | `privacy.models.SubProcessor` | `test_lgpd_extras` |
| 37 | Registro das operações | Exportação do RoPA a partir do catálogo (**nível de tabela: destinatários e medidas de segurança são texto do operador**) | `manage.py privacy_ropa` | `test_lgpd` |
| 38 | Relatório de impacto (RIPD) | Modelo `ImpactAssessment` e modelo de documento | `privacy.models.ImpactAssessment` | `test_lgpd_extras` |
| 41 | DPO | `DPO_*` publicado e obrigatório em produção; endpoint de contato | `privacy.public_api`, `settings.validators` | `test_lgpd_extras` |
| 46-47 | Segurança | Hardening, MFA, criptografia, auditoria chaveada, validadores estritos de produção | veja [hardening](../security/hardening.md) | `test_security_regressions`, `test_hardening` |
| 48 | Comunicação de incidente | Modelo de incidente; prazos da ANPD e dos titulares, complemento de 20 dias úteis, dobra para pequeno porte, exportação do conteúdo (**início do relógio e 3 dias úteis: a validar**) | `privacy.models.PersonalDataIncident`, `privacy_incident_export` | `test_lgpd`, `test_lgpd_extras` |
| 50 | Governança | Cadeia de auditoria chaveada, runbooks | `audit`, [runbooks](../deploy/runbooks.md) | `test_audit_integrity` |
| ECA Digital | Verificação de idade, privacidade por padrão (Lei 15.211/2025) | O ponto de encaixe acima; **a aplicabilidade é uma questão jurídica** | `privacy.age` | `test_lgpd_extras` |

Não coberto por software: escolher bases legais, redigir avisos (os modelos ajudam), cláusulas de
transferência internacional, conteúdo do RIPD, treinamento, contratos com operadores, a divisão
controlador/operador. A plataforma dá o registro, a evidência e os executores; pessoas decidem.
