# Integridade da auditoria

Cada organização (mais uma cadeia de sistema) tem a própria cadeia de hash. Uma linha guarda
`hash = SHA-256(prev_hash || linha canônica)`; os inserts pegam um advisory lock do PostgreSQL
como último comando, para que a cadeia continue linear sob concorrência.

- FKs para atores e organizações são ids simples (sem constraint): apagar um usuário ou uma
  organização nunca toca a trilha.
- Um trigger rejeita UPDATE e DELETE (e TRUNCATE), salvo se a transação definir
  `app.audit_maintenance`, o que só o job de poda faz; a poda grava uma linha de **âncora** que
  mantém a cadeia verificável depois que linhas antigas saem (`AUDIT_RETENTION_DAYS`, 0 = guardar
  para sempre).
- Os metadados são validados por fragmento de chave e varridos com os padrões de redação; dados
  pessoais não pertencem à trilha.
- `python manage.py audit_verify [--all]` recalcula as cadeias e sai com código diferente de zero
  se houver quebra. Agende (um schedule do Temporal, um CronJob, ou o CI contra um backup
  restaurado).

Uma cadeia quebrada significa linhas alteradas fora da aplicação. Trate como incidente: veja os
[runbooks](../deploy/runbooks.md).
