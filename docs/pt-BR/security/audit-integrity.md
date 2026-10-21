# Integridade da auditoria

Cada organização (mais uma cadeia de sistema) tem a própria cadeia de hash. Uma linha guarda um
**HMAC** do hash anterior e do seu conteúdo canônico, com chave `AUDIT_HMAC_KEY` (no ambiente, não no
banco); os inserts pegam um advisory lock do PostgreSQL como último comando, para que a cadeia continue
linear sob concorrência. O histórico de consentimentos é encadeado do mesmo jeito.

- FKs para atores e organizações são ids simples (sem constraint): apagar um usuário ou uma
  organização nunca toca a trilha.
- Um trigger rejeita `UPDATE`, `DELETE` e `TRUNCATE`. O único delete sancionado é a função
  `audit_prune()` usada pela retenção, e o trigger só a aceita para o papel dono da tabela. O papel de
  runtime tem `INSERT` e `SELECT` na tabela e `EXECUTE` na função (`AUDIT_RUNTIME_ROLE`); não consegue
  atualizar, apagar, truncar nem desativar nada. A poda grava uma linha de **âncora** que mantém a
  cadeia verificável depois que linhas antigas saem (`AUDIT_RETENTION_DAYS`, padrão 365, 0 = guardar
  para sempre).
- Uma constraint `CHECK` recusa uma linha sem `seq` ou `hash`, então um insert forjado não fica fora da
  cadeia.
- Os metadados são validados por fragmento de chave e varridos com os padrões de redação; dados pessoais
  não pertencem à trilha. Logins falhos são agrupados por conta e limitados por endereço do cliente;
  ações recusadas são limitadas por credencial, então quem chama não escolhe a velocidade de
  crescimento da tabela.
- `python manage.py audit_verify [--org ID]` recalcula as cadeias e sai com código diferente de zero
  se houver quebra. O job diário `maintenance.verify_audit` faz o mesmo e registra a cabeça de cada
  cadeia (`audit_head`).

## As linhas mais novas

Uma cadeia prova o que antecede sua cabeça: apagar os eventos mais novos deixa uma cadeia mais curta
que ainda verifica. Registre as cabeças onde o banco não alcance e confira contra elas:

```bash
python manage.py audit_verify --json > heads.json      # ou colete as linhas de log audit_head
python manage.py audit_verify --expect heads.json      # falha com "newest events are missing"
```

## Contra o que não protege

O dono da tabela ou um superusuário de banco que também tenha a `AUDIT_HMAC_KEY`. Separe os papéis de
banco ([Implante](../deploy/overview.md#duas-identidades-de-banco)), guarde a chave num cofre de
segredos que o host do banco não leia, e envie as linhas de cabeça a armazenamento de escrita única. O
`manage.py doctor` avisa quando o papel de runtime é dono da tabela ou consegue modificá-la.

Uma cadeia quebrada significa linhas alteradas fora da aplicação. Trate como incidente: veja os
[runbooks](../deploy/runbooks.md).
