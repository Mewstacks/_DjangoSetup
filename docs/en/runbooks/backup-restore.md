# Backup and restore

[Versão em português](../../pt-BR/runbooks/backup-restauracao.md)

- Use Fly Managed Postgres rather than unmanaged Postgres for production. Confirm automatic
  backup/HA status and retention in the dashboard.
- Define RPO/RTO per product. Managed service defaults are not the business requirement.
- Schedule an additional logical backup to a restricted, encrypted destination when the
  approved RPO, ransomware threat model, or portability requirement needs it.
- Keep object-storage versioning/snapshots where required and lifecycle them according to the
  same retention inventory as the database.
- Restore quarterly and before risky migrations: restore to a new isolated cluster, run
  integrity counts and application smoke tests, verify encrypted fields with the matching
  historical keys, then destroy the rehearsal environment securely.
- Never overwrite the only production database as a restore test. Never download production
  dumps to a developer workstation.

Record the backup identifier, restore start/end, RPO/RTO achieved, validation results, operator,
problems, and corrective actions without including personal data.
