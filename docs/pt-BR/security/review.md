# Revisão de segurança

Estado da revisão deste template. Atualize esta página sempre que mudar autenticação, tenancy,
criptografia, logging ou o cliente de saída.

## Linha de base (início do programa): 36 achados

Dois de severidade alta (IP do cliente colapsando atrás de proxy, o que compartilhava throttles e
lockouts; retirada de consentimento podia ser bloqueada), o restante médio e baixo. Todos foram
corrigidos com teste de regressão nomeado em `tests/test_security_regressions.py`, exceto os
listados abaixo.

## Revisões durante a construção

| Área | Achado | Resolução |
|---|---|---|
| Admin | Inline de Membership permitia autoescalada | Inline restrito; campos só para superusuário |
| Chaves de API | Rotação chamável por quem não é owner | Só owner |
| Fluxos | `flows.start` aceitava identidade na entrada | O motor carimba a identidade; entrada com chaves de identidade é rejeitada |
| LGPD | Requisição destrutiva executava em um POST | Etapa de verificação por link por e-mail |
| Logging | Eventos nativos do structlog pulavam a redação | Redação movida para os processadores finais |
| Webhooks | A listagem de endpoints vazava o segredo decifrado | Segredo só em create/rotate; teste adicionado |
| Contas | O login legado podia contornar MFA e verificação de e-mail | Recusa essas contas; login do admin via allauth |
| Páginas | A página de sessões quebrava (faltava `humanize`) | App adicionado; testes de render de toda página de conta |

## Itens em aberto

| Item | Notas |
|---|---|
| Lacunas de cobertura da auditoria | Mudanças feitas no admin são auditadas por `AuditedAdminMixin`; ações customizadas do admin precisam chamar `record_event` |
| Relatório de CSP e nonces | A CSP é só `'self'` nas páginas entregues; adicione um endpoint de report antes de introduzir scripts inline |
| Build da imagem no CI | O pipeline da imagem está escrito, mas a primeira execução acontece no seu repositório |
| Pin da imagem base por digest | A base está fixada por tag; fixe por digest no seu espelho de registry |

Reporte vulnerabilidades como descrito em `SECURITY.md`.
