# Resposta a incidentes com dados pessoais

[English version](../../en/runbooks/incident-response.md)

1. **Triar e conter:** abra registro restrito, defina responsáveis técnicos, jurídicos e DPO,
   interrompa a exposição, rotacione credenciais e preserve evidências. Não copie dados pessoais
   para chat, tickets, logs ou Sentry.
2. **Estabelecer fatos:** registre horários, sistemas, categorias, quantidade de titulares,
   geografia, exposição de chaves, acesso/exfiltração e confiança na contenção.
3. **Avaliar:** controlador e responsáveis qualificados decidem se o incidente envolve dados
   pessoais e pode causar risco ou dano relevante. Defina o prazo revisado juridicamente; a
   Resolução 15/2024 geralmente usa três dias úteis.
4. **Notificar quando necessário:** prepare comunicação clara em português para ANPD e
   titulares com natureza, categorias, proteções, riscos, descoberta, mitigação e contato do
   encarregado. Registre horários e versões aprovadas.
5. **Recuperar:** elimine a causa, restaure com segurança, aumente monitoramento, valide limites
   de tenant/dados e comunique sem especulação.
6. **Aprender e reter:** conclua análise de causa e ações corretivas, valide correções, atualize
   RIPD/threat model e retenha o registro por pelo menos cinco anos.

Se Fly, PostgreSQL, Tigris, Upstash, Sentry ou outro operador estiver envolvido, preserve IDs e
comunicados do fornecedor e acione as cláusulas contratuais de cooperação.
