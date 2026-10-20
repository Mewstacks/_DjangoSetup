# Feature flags and settings

## Flags

Switches operators flip without a deploy. Unknown flags are **off**. Evaluation order: user rule,
organization rule, percentage bucket (stable per user or organization), the flag's default.

```python
from apps.flags.services import is_enabled

if is_enabled("notes-v2", organization=ctx.organization, user=ctx.user):
    ...
```

Manage in the admin or: `python manage.py flag notes-v2 on --org acme` (also `--user`,
`--percent 25`, or no target for the default). Over the API: action `flags.evaluate`.

## Typed settings

Declare a runtime value with a type and default; an override can never be invalid.

```python
# <app>/dynamic.py
declare_setting("notes.max_title_length", int, 200, "Longest accepted note title.")
get_setting("notes.max_title_length", organization=org)  # org override, else global, else default
```

Writers use `set_setting(key, value, organization=...)`, which validates the type (a bool is not an
int). Action `settings.get` reads the effective value.

Reads are served from a cached snapshot (60 s) invalidated on every write.
