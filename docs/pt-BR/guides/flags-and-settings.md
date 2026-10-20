# Feature flags e settings

## Flags

Chaves que operadores viram sem deploy. Flags desconhecidas ficam **desligadas**. Ordem de
avaliação: regra do usuário, regra da organização, faixa percentual (estável por usuário ou
organização), padrão da flag.

```python
from apps.flags.services import is_enabled

if is_enabled("notes-v2", organization=ctx.organization, user=ctx.user):
    ...
```

Gerencie no admin ou: `python manage.py flag notes-v2 on --org acme` (também `--user`,
`--percent 25`, ou sem alvo para o padrão). Pela API: ação `flags.evaluate`.

## Settings tipados

Declare um valor de runtime com tipo e padrão; um override nunca é inválido.

```python
# <app>/dynamic.py
declare_setting("notes.max_title_length", int, 200, "Maior título de nota aceito.")
get_setting(
    "notes.max_title_length", organization=org
)  # override da org, senão global, senão padrão
```

Quem grava usa `set_setting(chave, valor, organization=...)`, que valida o tipo (bool não é int).
A ação `settings.get` lê o valor efetivo.

As leituras vêm de um snapshot em cache (60 s) invalidado a cada escrita.
