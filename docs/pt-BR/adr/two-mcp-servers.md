# ADR 15: Dois servidores MCP, com trabalhos diferentes

**Status:** aceito.

## Contexto

"Um servidor MCP" era uma ideia com dois públicos. Um agente de IA pode ser chamado para **operar um
produto em execução** em nome de uma pessoa (ler as notas, criar uma fatura), ou para **construir o
produto** (adicionar um recurso, corrigir um bug). Os riscos, a identidade e o tempo de vida diferem.

## Decisão

- **MCP da plataforma** (`/mcp`, no serviço publicado). As ferramentas são as ações marcadas para o
  canal `mcp`; a identidade é a chave de API ou o token OAuth de uma pessoa; toda chamada é auditada;
  as escritas podem ser desfeitas. Serve também `platform://actions`, `platform://scopes` e um prompt
  de comportamento.
- **MCP de desenvolvimento** (`python -m devtools.mcp`, na máquina de quem desenvolve, stdio). Sem
  identidade: lê o livro de regras, os registros e a documentação, gera código, verifica convenções e
  roda o gate. Escreve só em `src/` e `tests/`, só quando pedido, e nunca é montado num serviço
  publicado.

Não compartilham nada em tempo de execução. O servidor de desenvolvimento reutiliza os mesmos
registros (ações, catálogo de dados), então o que um agente aprende sobre o código é o que a
plataforma impõe.

## Consequências

- Um servidor de desenvolvimento vazado é uma capacidade local de escrita de arquivos, não acesso a
  dados de clientes, porque não tem credenciais de banco próprias além das configurações locais de
  quem desenvolve.
- A superfície de ataque do servidor da plataforma não cresce com ferramentas de desenvolvimento.
- As ferramentas do servidor de desenvolvimento são a primeira coisa a atualizar quando uma convenção
  muda: elas leem `src/devtools/conventions.py`, a mesma fonte do `AGENTS.md`.
