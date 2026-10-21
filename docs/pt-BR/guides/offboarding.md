# Encerrando um tenant

Um cliente sai, ou pede os dados dele. Os dois casos são comuns; trate-os sempre do mesmo jeito.

## Entregue os dados

Dois níveis, nesta ordem:

1. **O que a plataforma exporta de uma pessoa**: uma solicitação de acesso ou portabilidade gera uma
   exportação selada de tudo que o catálogo diz que guardamos sobre aquela pessoa, atrás de um link
   que expira e tem uso limitado (`PRIVACY_EXPORT_TTL_DAYS`, `PRIVACY_EXPORT_MAX_DOWNLOADS`).
2. **O que a organização possui** (seus dados de negócio): exporte com uma ação sua, por exemplo
   `invoices.export`, escopada à organização e auditada. O catálogo diz os modelos; o
   [catálogo de dados](../reference/data-catalog.md) é a lista de conferência. Entregue por um link
   que expira, nunca como anexo de e-mail.

## Encerre a organização

1. Revogue o acesso: `Organization.is_active=False` (membros e chaves param na chamada seguinte),
   revogue chaves de API e tokens OAuth, desative os endpoints de webhook.
2. Aguarde a carência contratual; diga quanto tempo nos termos.
3. Elimine. Os dados de negócio da organização são **seus para apagar** (são dados do tenant, que você
   guarda por conta dele); dados pessoais dos membros são tratados por pessoa pelos executores de
   eliminação, que respeitam bloqueios legais. Arquivos enviados saem do bucket junto com as linhas.
4. Guarde só o que um dever legal exige (notas, provas de consentimento, registros de incidentes, a
   trilha de auditoria até acabar sua retenção) e diga isso no aviso de privacidade.
5. Registre: um evento de auditoria, e uma nota no registro de operações se a finalidade mudou.

## O que a eliminação não alcança

- **Backups** guardam os dados até expirarem. Diga a retenção dos backups no aviso e, depois de
  restaurar um backup, reaplique as eliminações feitas desde então (o passo do runbook).
- **A trilha de auditoria** aponta para ids, não conteúdo, e é podada por `AUDIT_RETENTION_DAYS`.
- **Logs** são redigidos na escrita e expiram com a sua retenção de logs.

## Controlador ou operador

Para os dados dos membros de um cliente no seu produto você costuma ser **operador** e o cliente o
**controlador** (LGPD arts. 5º e 39): ele instrui, você executa. Para os dados de conta e cobrança
dos seus próprios clientes você é o controlador. Escreva quem é quem no contrato e no aviso de
privacidade; há um modelo de acordo de tratamento de dados em
[modelos de documentos da LGPD](../lgpd/templates.md). Essa divisão decide quem responde a um
titular: acerte-a com um advogado antes do primeiro cliente.
