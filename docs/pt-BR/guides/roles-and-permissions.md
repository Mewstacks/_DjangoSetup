# Papéis e permissões

Três camadas decidem se uma chamada passa. As três precisam dizer sim.

| Camada | Pergunta | Onde |
|---|---|---|
| Escopo da credencial | Esta chave, token ou sessão tem o escopo que a ação exige? | `@action(scope=...)`, `ApiKey.scopes`, consentimento OAuth |
| Papel | O papel da pessoa **nesta organização** permite? | `Membership.role`, lido a **cada** chamada |
| Tenant | A linha é desta organização? | `ctx.scoped`, `OrganizationScopedViewSet` |

## Papéis

| Papel | Escreve dados do tenant | Cria chaves de API | Vê e revoga chaves de outros | Endpoints de webhook |
|---|---|---|---|---|
| `owner` | sim | sim | sim (nunca obtém uma cópia funcional) | gerencia |
| `admin` | sim | sim | sim (nunca obtém uma cópia funcional) | gerencia |
| `member` | sim | sim (as próprias) | não | lê |
| `billing` | **não** | não | não | lê |
| `auditor` | **não** | não | não | lê |

`billing` e `auditor` são somente leitura: uma ação que escreve devolve `403 read_only_role` para
eles, quaisquer que sejam os escopos da credencial, e uma chave criada antes de um rebaixamento
para de escrever na hora.

O papel nunca é copiado para um token. Rebaixar ou remover uma pessoa limita suas chaves e tokens
OAuth na chamada seguinte.

## Restringindo uma ação

```python
@action("invoices.void", write=True, roles={"owner", "admin"}, destructive=True, undoable=True)
def void_invoice(ctx, data): ...
```

`roles=` substitui a regra padrão de escrita para aquela ação. O catálogo
(`docs/reference/actions.json`) registra `roles`, então afrouxar aparece na revisão.

## Escopos

Um escopo é `dominio:nivel` (`notes:read`, `notes:write`). Novos aparecem com novas ações. Perfis de
chave de API: `read` (todo escopo de leitura) e `full` (todo escopo que o papel permite). Uma chave
pode ser mais estreita que o papel do dono, nunca mais larga.

## Segundos fatores

Staff precisa de um autenticador antes de `/admin/` abrir (`STAFF_MFA_REQUIRED`). Em produção, um
owner ou admin logado por sessão precisa de um antes que os endpoints da organização respondam
(`ORG_PRIVILEGED_MFA_REQUIRED`): a API diz o motivo em vez de um 403 seco. Criar ou rotacionar uma
chave de API também exige um login com no máximo `APIKEY_REQUIRE_RECENT_AUTH_SECONDS` (15 minutos),
e a redefinição de senha ou do segundo fator revoga as chaves da pessoa.
