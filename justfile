# Task runner (https://just.systems). Every recipe is a plain command; nothing here is magic.
set windows-shell := ["powershell.exe", "-NoLogo", "-Command"]

default:
    @just --list

# First run: env file, database, LGPD purposes, a verified superuser and an organization.
setup:
    uv sync --all-extras
    uv run python scripts/bootstrap.py

run:
    uv run python manage.py runserver

test *args:
    uv run python -m pytest -q {{args}}

# The quality gate CI runs. `just verify --fast` skips mypy and the deploy check.
verify *args:
    uv run python scripts/verify.py {{args}}

fmt:
    uv run ruff format .
    uv run ruff check --fix .

# Regenerate every generated file (action catalog, OpenAPI, reference docs, AI context files).
generate:
    uv run python manage.py actions_catalog
    uv run python scripts/check_openapi.py --write
    uv run python scripts/gen_docs.py

# MCP server for AI coding agents (stdio). See docs/en/guides/ai-development.md.
devmcp:
    uv run python -m devtools.mcp

doctor:
    uv run python manage.py doctor
