# ADR 16: Agent-facing files are generated from one rulebook

**Status:** accepted.

## Context

Agents read different files (`AGENTS.md`, `CLAUDE.md`, Cursor rules, Copilot instructions,
`llms.txt`). Written by hand they drift from each other and from the code, and an agent that
follows a stale rule produces a wrong change with total confidence.

## Decision

`src/devtools/conventions.py` holds the rules as data: each with its reason and what enforces it.
`scripts/gen_docs.py` renders every agent-facing file from it and `--check` fails CI on drift.
Only rules that something enforces, or that are a human judgement said as such, are listed.
`docs/reference/conventions.json` carries the same rules plus what is registered right now (actions,
scopes, events, jobs, models), for programs.

## Consequences

- One edit changes every copy. The cost is one more generated file set to keep fresh, covered by the
  same `verify.py` gate as the OpenAPI and reference docs.
- A rule that nothing enforces is a promise; the rulebook is deliberately short for that reason.
- Languages: the agent files are English (what coding agents read best); the human guides exist in
  English and Portuguese.
