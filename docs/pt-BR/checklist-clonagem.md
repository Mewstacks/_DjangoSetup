# Checklist para clonar um novo SaaS

[English version](../en/clone-checklist.md)

1. Renomeie pacote, metadados, título da API, app Fly, prefixo de cache, projeto Sentry e
   domínios. Gere novos segredos; nunca reutilize chaves entre produtos ou ambientes.
2. Decida se o produto usa uma ou várias organizações. Mantenha o escopo explícito até decidir
   removê-lo conscientemente.
3. Crie models de produto em apps separados. Registros de tenant herdam
   `OrganizationScopedModel`; serviços recebem a organização explicitamente.
4. Defina papéis por ações do produto. Teste que usuários não podem ler, inferir, alterar ou
   apagar registros de outra organização.
5. Complete inventário, finalidades, bases legais, aviso, retenção, fornecedores, transferências,
   direitos dos titulares, contatos de incidente e decisão sobre RIPD.
6. Adicione onboarding, verificação de e-mail, recuperação de senha, MFA/SSO, cobrança e e-mail
   transacional somente depois de definir seus fluxos de segurança e privacidade.
7. Use segredos independentes e dados sintéticos em staging. Nunca copie dados pessoais de
   produção para desenvolvimento, CI, demonstrações ou Sentry.
8. Execute testes, `check --deploy`, scans, restauração, rotação de chaves, teste de carga e uma
   revisão independente antes do lançamento.
