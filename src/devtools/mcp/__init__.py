"""The development MCP server: how an AI coding agent learns this codebase and builds on it.

Not the same thing as the platform's ``/mcp`` endpoint. That one lets an agent *operate a running
product* as a user, through actions, with that user's scopes. This one lets an agent *write the
product*: it reads the rules, the registries and the docs, scaffolds a resource, checks its own
work against the conventions and runs the quality gate. It runs on the developer's machine over
stdio, reads and writes the working tree, and is never mounted in a deployed service.

    python -m devtools.mcp            # or the entry in .mcp.json
"""
