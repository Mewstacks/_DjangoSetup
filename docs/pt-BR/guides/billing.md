# Cobrança e planos (guia de extensão)

A plataforma não traz cobrança: é a parte mais específica de cada SaaS, e um padrão errado sai caro.
O que ela traz são os pontos de encaixe para construí-la sem brigar com a base. Esta página é o
desenho, não um recurso.

## As peças que você já tem

| Necessidade | Use |
|---|---|
| Um cliente é uma organização | `Organization`, com `Membership.Role.BILLING` para quem paga |
| Saber o que um plano permite | `apps.organizations.quotas.limit_for(organization, kind)`: troque o corpo por uma consulta ao plano da organização e todos os pontos de uso acompanham |
| Ligar uma capacidade por cliente | Feature flags com regras por organização ([flags e configurações](flags-and-settings.md)) |
| Receber os eventos do provedor de pagamento | O **receptor** de webhook é código seu; envie as mudanças de estado com o outbox ([webhooks](webhooks.md)) |
| Agir quando um pagamento falha | Um job ou um flow ([adicionar um flow](add-a-flow.md)), iniciado pelo receptor |
| Registrar quem mudou um plano | `record_event(action="billing.plan_changed", ...)`: a trilha de auditoria |

## Um desenho sólido

1. **Modelo** (app `billing`, `OrganizationScopedModel`): `Subscription(plan, status, current_period_end,
   provider_customer_id)`. Classifique-o: o id do cliente no provedor é um identificador, o plano não.
2. **Receptor**: um endpoint que verifica a assinatura do provedor no corpo bruto *antes* de
   interpretar, registra o id do evento (assim uma repetição não faz nada) e responde `2xx` rápido.
   Faça o trabalho num job. Chamadas de saída ao provedor passam por `apps.common.netguard` só se a
   URL vier de usuário; um host fixo do provedor não precisa, mas deve verificar o TLS.
3. **Direitos de uso**: uma única função `entitled(organization, capability) -> bool` lendo a
   assinatura, usada pelas ações (levante `Forbidden(code="plan_required")`) e por
   `quotas.limit_for`. Nunca espalhe nomes de plano pelo código.
4. **Carência e cobrança**: o status `past_due` mantém leitura e bloqueia criação; um job faz o
   rebaixamento depois da carência e avisa o papel `billing` por e-mail.
5. **Impostos e notas** (NF-e/NFS-e no Brasil) são tema jurídico: use um provedor que as emita e
   guarde só os ids.

## O que não fazer

- Não guarde dados de cartão. Use o checkout hospedado do provedor; guarde só ids e status.
- Não confie num nome de plano enviado pelo cliente.
- Não deixe um payload de webhook decidir a organização: resolva-a pelo id do cliente no provedor
  que você guardou.
- Não faça falhas de cobrança derrubarem o produto: os direitos de uso voltam ao último plano
  conhecido quando o provedor está fora.

## LGPD

Dados de cobrança são dados pessoais de quem paga (nome, CPF/CNPJ, endereço). Classifique o modelo,
guarde o que a lei tributária exige (`on_erase="keep"` com o dever legal como motivo) e anonimize o
resto na eliminação. Liste o provedor de pagamento como suboperador com país e mecanismo de
transferência.
