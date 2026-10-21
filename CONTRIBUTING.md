# Contributing / Contribuindo

## English

1. `uv sync --all-extras`, then `python scripts/bootstrap.py`.
2. Read [AGENTS.md](AGENTS.md): the rules are enforced by tests, so follow them instead of working
   around a failing one.
3. Prefer `python manage.py scaffold resource <app> <Model> --fields ...` over writing files by hand.
4. `python scripts/verify.py --fast` while you iterate, `python scripts/verify.py` before you push.
5. Docs: every page under `docs/en` has a twin under `docs/pt-BR`. Generated files
   (`docs/reference/*`, `AGENTS.md`, `llms*.txt`) come from `python scripts/gen_docs.py`.
6. Commits use Conventional Commits (`feat:`, `fix:`, `docs:`). Security issues: see
   [SECURITY.md](SECURITY.md), never a public issue.

## Português

1. `uv sync --all-extras`, depois `python scripts/bootstrap.py`.
2. Leia o [AGENTS.md](AGENTS.md): as regras são impostas por testes, então siga-as em vez de contornar
   um teste que falha.
3. Prefira `python manage.py scaffold resource <app> <Model> --fields ...` a escrever arquivos à mão.
4. `python scripts/verify.py --fast` enquanto itera, `python scripts/verify.py` antes do push.
5. Docs: toda página em `docs/en` tem par em `docs/pt-BR`. Arquivos gerados (`docs/reference/*`,
   `AGENTS.md`, `llms*.txt`) saem de `python scripts/gen_docs.py`.
6. Commits seguem Conventional Commits (`feat:`, `fix:`, `docs:`). Problemas de segurança: veja o
   [SECURITY.md](SECURITY.md), nunca uma issue pública.
