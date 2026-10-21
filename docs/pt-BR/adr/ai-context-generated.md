# ADR 16: Os arquivos para agentes são gerados de um só livro de regras

**Status:** aceito.

## Contexto

Agentes leem arquivos diferentes (`AGENTS.md`, `CLAUDE.md`, regras do Cursor, instruções do Copilot,
`llms.txt`). Escritos à mão, divergem entre si e do código, e um agente que segue uma regra velha produz
uma mudança errada com total confiança.

## Decisão

`src/devtools/conventions.py` guarda as regras como dados: cada uma com seu motivo e o que a impõe.
`scripts/gen_docs.py` gera todo arquivo para agentes a partir dele e `--check` falha o CI na divergência.
Só entram regras que algo impõe, ou que são um julgamento humano dito como tal.
`docs/reference/conventions.json` leva as mesmas regras mais o que está registrado agora (ações,
escopos, eventos, jobs, modelos), para programas.

## Consequências

- Uma edição muda todas as cópias. O custo é mais um conjunto de arquivos gerados a manter atualizado,
  coberto pelo mesmo gate `verify.py` do OpenAPI e dos docs de referência.
- Uma regra que nada impõe é uma promessa; o livro de regras é curto de propósito por isso.
- Idiomas: os arquivos para agentes são em inglês (o que agentes de código leem melhor); os guias para
  pessoas existem em inglês e português.
