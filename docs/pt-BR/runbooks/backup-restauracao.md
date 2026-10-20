# Backup e restauração

[English version](../../en/runbooks/backup-restore.md)

- Use Fly Managed Postgres em produção e confirme backup, alta disponibilidade e retenção.
- Defina RPO/RTO por produto; padrões do serviço não substituem requisitos de negócio.
- Crie backup lógico adicional em destino restrito e criptografado quando RPO, ransomware ou
  portabilidade exigirem.
- Use versionamento/snapshots no object storage conforme o inventário de retenção.
- Teste restauração trimestralmente e antes de migrations arriscadas: restaure em cluster
  isolado, valide contagens, smoke tests e campos criptografados com chaves históricas, depois
  destrua o ambiente com segurança.
- Nunca sobrescreva o único banco de produção em um teste e nunca baixe dumps em computadores
  de desenvolvedores.

Registre identificador do backup, início/fim, RPO/RTO atingido, validações, operador, problemas
e ações corretivas sem incluir dados pessoais.
