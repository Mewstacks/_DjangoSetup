# ADR 13: A trilha de auditoria é chaveada, e só o dono pode podá-la

**Status:** aceito. Substitui a cadeia sem chave descrita na decisão 8.

## Contexto

A trilha tem cadeia de hash por organização e é protegida por um trigger do PostgreSQL. Uma revisão
achou três jeitos de isso ser mais fraco do que a documentação afirmava:

1. O hash era SHA-256 simples, então quem pudesse escrever na tabela podia reescrever o histórico e
   recalcular todos os hashes de forma consistente.
2. O trigger permitia um `DELETE` depois de `SET LOCAL app.audit_maintenance = 'on'`, que *qualquer*
   sessão pode executar, então uma conta comprometida da aplicação podia apagar a trilha.
3. Uma cadeia prova o que *antecede* sua cabeça. Apagar os eventos mais novos deixa uma cadeia mais
   curta que ainda verifica.

## Decisão

- **Cadeia chaveada.** Cada hash é um HMAC sob `AUDIT_HMAC_KEY` (ambiente, nunca o banco). Quem escreve
  no banco não consegue reencadear sem ela. O mesmo helper chaveia a cadeia de consentimentos.
- **Poda só pelo dono.** O trigger permite um delete apenas para o papel dono da tabela, e o único
  delete sancionado é `audit_prune(cadeia, ate_seq)`, uma função `SECURITY DEFINER` cujo `EXECUTE` é
  concedido ao papel de runtime nomeado em `AUDIT_RUNTIME_ROLE`. O papel de runtime tem `INSERT` e
  `SELECT` na tabela e mais nada (seus `UPDATE`, `DELETE`, `TRUNCATE` são revogados pela migração).
  O `doctor` avisa quando o runtime é dono da tabela.
- **Nenhuma linha fora da cadeia.** Um `CHECK (seq IS NOT NULL AND hash <> '')` recusa inserts forjados
  (adicionado `NOT VALID`, para que linhas anteriores ao encadeamento não o bloqueiem).
- **As cabeças saem do banco.** O job diário `maintenance.verify_audit` registra a cabeça de cada
  cadeia; `audit_verify --expect heads.json` compara uma cabeça registrada com a cadeia e pega a
  remoção do final.

## Consequências

- Só é verdade com dois papéis de banco (dono do schema para migrações, runtime para o app). Os
  manifestos de Compose e Kubernetes os criam; uma implantação de papel único ainda ganha a cadeia
  chaveada, perde a separação de privilégios, e o `doctor` avisa.
- Um superusuário que também tenha `AUDIT_HMAC_KEY` ainda pode reescrever o histórico. Envie as linhas
  de cabeça a um sistema que o banco não alcance (um serviço de logs com armazenamento de escrita
  única) para detectar isso também.
- Rotacionar `AUDIT_HMAC_KEY` invalida a verificação das linhas antigas: comece uma nova época,
  exportando antes a cadeia antiga. Ainda não há ferramenta para isso; é um não-objetivo deliberado até
  que um cliente precise.
