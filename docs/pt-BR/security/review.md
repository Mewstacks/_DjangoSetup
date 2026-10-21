# Revisão de segurança

Estado da revisão deste template. Atualize esta página sempre que mudar autenticação, tenancy,
criptografia, logs ou o cliente de saída.

## Linha de base (início do programa): 36 achados

Dois de severidade alta (IP do cliente colapsando atrás de um proxy, então limites e bloqueios eram
compartilhados; a revogação de consentimento podia ser bloqueada), o resto médio e baixo. Todos foram
corrigidos com um teste de regressão nomeado em `tests/test_security_regressions.py`.

## Segunda revisão (2026-10)

Uma revisão estática de configurações, contas, tenancy, auditoria, webhooks, flows, implantação e CI.
Todo achado abaixo foi corrigido com um teste nomeado, salvo indicação.

| Severidade | Achado | Resolução | Teste |
|---|---|---|---|
| Alta | O app `uploads` não estava versionado: uma regra `.gitignore` sem âncora o escondia, então um clone limpo não iniciava | Regras ancoradas; o CI falha com arquivos ignorados em `src/` | Passo do CI; `test_scaffold` copia a árvore |
| Alta | Trilha de auditoria: qualquer sessão podia apagar após definir um GUC; o hash não tinha chave; linhas mais novas não verificáveis; inserts forjados fora da cadeia | Cadeia HMAC chaveada, `audit_prune()` só do dono, separação de papéis, `CHECK`, exportação de cabeças | `test_audit_integrity`, `test_the_chain_is_keyed...`, teste de separação de papéis (PostgreSQL) |
| Média | A guarda de SSRF não via NAT de operadora (100.64/10, metadados da Alibaba), embrulhos NAT64/6to4/Teredo; proxy do ambiente; sem prazo total; descompressão | Lista de endereços globais, checagem do IPv4 embutido, `trust_env=False`, prazo, só bytes brutos | `test_netguard` |
| Média | Staff com `change_user` podia tomar um superusuário (editar o e-mail, redefinir) | Superusuários ocultos, e-mail somente leitura, troca de senha só do superusuário | `test_hardening` |
| Média | Sem MFA para staff ou owners; sem login recente para criar chave; chaves sobreviviam a uma redefinição | `STAFF_MFA_REQUIRED`, `ORG_PRIVILEGED_MFA_REQUIRED`, janela de login recente, revogação na redefinição | `test_hardening` |
| Média | Tokens OAuth guardados em claro; sem proteção contra replay de refresh; DCR aceitava `client_credentials`, redirecionamentos `http` e nunca expirava | Portões da RFC 9700 ligados, armazenamento como checksum, proteção de reuso, política e expiração de registro, `iss` | `test_hardening`, `test_oauth`, `test_mcp_protocol` |
| Média | O Temporal aceitava payloads não selados (entrada de atividade forjável); `run_task` importava qualquer caminho; sem validação na partida | Não selado recusado, ponte de tarefas restrita, validadores | `test_flows`, `test_hardening` |
| Média | A rotação de chaves esquecia sementes de MFA; a decifra de MFA aceitava texto simples; a rotação do HMAC quebrava toda chave | `reencrypt_fields` cobre MFA, texto simples recusado, `PRIVACY_HMAC_KEYS_PREVIOUS`, `SECRET_KEY_FALLBACKS` | `test_key_rotation` |
| Média | Link de exportação reutilizável por 7 dias, relativo no e-mail, token no caminho da URL dos logs | Limite de downloads, `PUBLIC_URL` absoluta, token removido | `test_export_link` |
| Média | Linhas de auditoria de login falho e de ação recusada tinham volume controlado por quem ataca; a trava por id de chave deixava um estranho bloquear o dono | Tetos por cliente, contadores de falha por endereço | `test_abuse_limits` |
| Média | Implantação: saída aberta, uma identidade de banco superusuária para tudo, `:latest`, backups sem cifra, sem portão de release | NetworkPolicy com ipBlock, dois papéis, digests, umask e TLS nos backups, release condicionado ao CI com assinatura | CI (renderização, trivy config, boot) |
| Baixa | Sem Permissions-Policy / CORP; CORS cobria todo caminho; sem coletor de CSP; caminho do admin sem barra vazava; 500 em html para a API; objetos escapavam da redação de logs; login legado | Adicionados, escopados ou desligados | `test_web_hardening` |
| Baixa | O isolamento de tenants era só convenção; o desfazer achava o alvo só por id; recursos por tenant sem limite | Testes estruturais, filtro de organização no desfazer, cotas | `test_tenancy_structure` |
| Baixa | TLS `require` do banco e Redis só com senha aceitos; corpos lentos; a checagem de deploy passava com avisos | TLS verificado, `rediss`, 408 em corpos parados, avisos falham | `test_security_regressions`, `test_body_timeout` |

## Itens em aberto

| Item | Notas |
|---|---|
| Row-level security | Uma opção documentada, não implementada ([ADR 14](../adr/row-level-security.md)) |
| Checagem de senha vazada | Não construída: exige chamada de saída a terceiros; adicione como validador de senha do allauth via `netguard` se quiser |
| Timeout de sessão ociosa | As sessões têm vida absoluta (`SESSION_COOKIE_AGE_SECONDS`, 12 h); adicione um limite ocioso deslizante se o seu modelo de ameaças pedir |
| Autorização por usuário para flows | Um flow roda como a pessoa que o iniciou com o papel dela, mas não com os escopos da credencial inicial: declare o `scope` de cada flow cobrindo tudo que ele faz |
| Digests das imagens base | A imagem da aplicação é assinada e implantada por digest; fixe a imagem base por digest no seu espelho de registro para builds idênticos byte a byte |
| AAD por usuário nos segredos de MFA | O gancho do adaptador do allauth não passa o usuário, então as sementes são presas à coluna, não à pessoa |
| Rotação da `AUDIT_HMAC_KEY` | Nova época, ainda sem ferramenta ([ADR 13](../adr/audit-chain-and-role-split.md)) |

Reporte vulnerabilidades como descrito em `SECURITY.md`.
