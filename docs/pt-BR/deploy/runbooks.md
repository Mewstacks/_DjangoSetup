# Runbooks

## Backup e restauração

- Backup lógico: o compose `--profile backup` ou o CronJob do Kubernetes grava
  `pg_dump --format=custom` toda noite (arquivo só do dono) e guarda 14 dias. Os dumps trazem os dados
  de **todos os tenants em claro**: mantenha o volume cifrado e copie os dumps para fora da máquina
  cifrados.
- Restaure num banco vazio: `pg_restore --clean --if-exists --no-owner -d "$DB" arquivo.dump`, depois
  `entrypoint migrate` (como dono do schema, com `AUDIT_RUNTIME_ROLE` definido), depois
  `entrypoint manage audit_verify`.
- **Reaplique as eliminações depois de restaurar.** Uma restauração traz de volta pessoas eliminadas
  depois que o backup foi feito, e a plataforma não guarda identidade depois de uma eliminação. Mantenha
  um livro-razão **fora do banco** (id da solicitação, data e como identificar a pessoa, sob controle de
  acesso) das eliminações feitas desde o último backup, e repita cada uma depois de restaurar. Retenção
  curta de backups diminui o problema; diga a retenção no aviso de privacidade.
- Guarde o **chaveiro de criptografia** e a `AUDIT_HMAC_KEY` junto do material de recuperação dos
  backups, armazenados à parte deles: sem o chaveiro as colunas cifradas ficam ilegíveis; sem a chave de
  auditoria a cadeia não pode ser verificada.
- Pratique uma restauração ao menos por trimestre; o objetivo é um procedimento cronometrado e escrito.

## Incidente com dados pessoais

1. Crie o incidente (admin ou API): hora da descoberta, categorias, titulares estimados, medidas.
2. O prazo de comunicação à ANPD é calculado em dias úteis (`PRIVACY_INCIDENT_BUSINESS_DAYS`,
   `PRIVACY_HOLIDAYS`, dobrado por `PRIVACY_SMALL_AGENT`); os titulares afetados têm o mesmo prazo; uma
   primeira comunicação pode ser complementada até 20 dias úteis depois. Lembretes disparam de hora em
   hora via `privacy.incident_deadlines`.
3. Contenha: revogue chaves de API e tokens OAuth, rotacione segredos
   ([hardening](../security/hardening.md)), desative endpoints de webhook afetados.
4. Preserve evidências: `audit_verify`, exporte as linhas de auditoria da janela.
5. Decida a comunicação à ANPD e aos titulares com o DPO e um advogado (**o relógio começar na
   confirmação, 3 dias úteis e quem conta como agente de pequeno porte são pontos a validar**), monte o
   conteúdo com `manage.py privacy_incident_export REF`, então registre o desfecho e encerre. Os
   registros são guardados por cinco anos.

## Cadeia de auditoria quebrada

`audit_verify` sai com código diferente de zero (ou o job diário registra `audit_chain_broken`): pare a
poda, tire um snapshot do banco, ache a primeira linha ruim, compare com o último backup, trate como
incidente de segurança. `newest events are missing` significa que a cadeia foi cortada no final:
compare com as linhas de cabeça que você enviou. Rode também `manage.py doctor`: se o papel de runtime
consegue reescrever a trilha, conserte isso primeiro.

## Rotacionando segredos

| Segredo | Procedimento |
|---|---|
| `DJANGO_SECRET_KEY` | Mova o valor antigo para `DJANGO_SECRET_KEY_FALLBACKS`, defina o novo, publique; remova o antigo depois de `SESSION_COOKIE_AGE_SECONDS` |
| Chave de criptografia de campos | Novo id no chaveiro, troque o id ativo, `manage.py reencrypt_fields` (também recifra segredos de MFA), remova a chave antiga depois que ele relatar zero ilegíveis |
| `PRIVACY_HMAC_KEY` | Ponha o valor antigo em `PRIVACY_HMAC_KEYS_PREVIOUS`, defina o novo; chaves de API e titulares são regravados no primeiro uso; remova o antigo quando as chaves tiverem sido usadas ou reemitidas |
| `AUDIT_HMAC_KEY` | Não rotacionável no lugar: comece uma nova época (exporte a cadeia antiga, depois a chave nova) |
| Senha de banco / Redis | Rotacione na plataforma, atualize o secret, reinicie os pods; o `readiness` fica indisponível até conectar |
| Chaves de API, segredos de webhook | `rotate` / `rotate-secret` (24 h de sobreposição) |
| Clientes OAuth | Revogue tokens, emita um cliente novo |

## Temporal indisponível

`/api/v1/health/ready/` continua de pé (o estado do worker é informativo). Iniciar flows só-Temporal
falha rápido; flows portáteis só continuam se você definir `TEMPORAL_ENABLED=false` e rodar o
`scheduler`. Depois da recuperação rode `flows_sync`. Entregas de webhook repetem sozinhas.

## Um endpoint de webhook foi desativado

Ele atingiu `WEBHOOK_DISABLE_AFTER` falhas seguidas. Conserte o receptor, reative o endpoint, depois
`redeliver` as entregas que falharam.

## Atualização

Leia o `CHANGELOG.md`; ordem de deploy: job de migração, depois web, depois worker/scheduler. As
migrações são aditivas entre versões menores. Reverta a imagem, não o banco. Veja
[Atualizando a partir do upstream](../guides/upgrading.md).
