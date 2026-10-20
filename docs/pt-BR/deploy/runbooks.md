# Runbooks

## Backup e restauração

- Backup lógico: compose `--profile backup` ou o CronJob do Kubernetes grava
  `pg_dump --format=custom` toda noite e guarda 14 dias. Copie os dumps para fora da máquina
  também.
- Restaurar num banco vazio: `pg_restore --clean --if-exists --no-owner -d "$DB" arquivo.dump`,
  depois `entrypoint migrate`, depois `entrypoint manage audit_verify --all`.
- Guarde o **chaveiro de criptografia** junto do material de recuperação dos backups, em local
  separado: sem ele as colunas cifradas ficam ilegíveis.
- Pratique uma restauração ao menos por trimestre; o objetivo é um procedimento escrito e
  cronometrado.

## Incidente com dados pessoais

1. Crie o incidente (admin ou API): momento da descoberta, categorias, titulares estimados.
2. O prazo de comunicação à ANPD é calculado em dias úteis (`PRIVACY_INCIDENT_BUSINESS_DAYS`,
   `PRIVACY_HOLIDAYS`); lembretes disparam de hora em hora via `privacy.incident_deadlines`.
3. Contenha: revogue chaves de API e tokens OAuth, rotacione segredos
   ([hardening](../security/hardening.md)), desligue os endpoints de webhook afetados.
4. Preserve evidências: `audit_verify --all`, exporte as linhas de auditoria da janela.
5. Decida a comunicação à ANPD e aos titulares com o encarregado e o jurídico (**3 dias úteis é
   para validar**), registre o desfecho e feche.

## Cadeia de auditoria quebrada

`audit_verify` sai com erro: pare a poda, tire um snapshot do banco, ache a primeira linha ruim,
compare com o último backup, trate como incidente de segurança.

## Temporal indisponível

`/api/v1/health/ready/` continua de pé (o estado do worker é informativo). Inícios de fluxos
só-Temporal falham rápido; fluxos portáveis só continuam se você definir
`TEMPORAL_ENABLED=false` e rodar o `scheduler`. Depois da recuperação rode `flows_sync`. As
entregas de webhook tentam de novo sozinhas.

## Um endpoint de webhook foi desligado

Ele chegou a `WEBHOOK_DISABLE_AFTER` falhas consecutivas. Conserte o receptor, reative o
endpoint e faça `redeliver` das entregas que falharam.

## Atualização

Leia o `CHANGELOG.md`; ordem de deploy: job de migrate, depois web, depois worker/scheduler. As
migrations são aditivas entre versões menores. Faça rollback da imagem, não do banco.
