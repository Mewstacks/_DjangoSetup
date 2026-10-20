"""Print connection snippets for MCP clients. Never prints a real secret."""

from __future__ import annotations

import json
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand


def snippets(base_url: str, org_slug: str | None, name: str) -> dict[str, str]:
    base = base_url.rstrip("/")
    url = f"{base}{settings.MCP_PATH}" + (f"/{org_slug}" if org_slug else "")
    header = "Authorization: Bearer <YOUR_API_KEY>"
    http_config = {
        "type": "http",
        "url": url,
        "headers": {"Authorization": "Bearer <YOUR_API_KEY>"},
    }
    return {
        "Claude Code": f'claude mcp add --transport http {name} {url} --header "{header}"',
        "Claude Code (OAuth)": f"claude mcp add --transport http {name} {url}",
        "Cursor / VS Code / generic JSON": json.dumps(
            {"mcpServers": {name: http_config}}, indent=2
        ),
        "curl check": (
            f"curl -s {url} -H '{header}' -H 'Content-Type: application/json' "
            "-H 'Accept: application/json, text/event-stream' "
            '-d \'{"jsonrpc":"2.0","id":1,"method":"tools/list"}\''
        ),
    }


class Command(BaseCommand):
    help = "Show how to connect MCP clients to this server."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--url", default=settings.MCP_PUBLIC_URL or "https://localhost")
        parser.add_argument("--org", help="Organization slug to put in the URL")
        parser.add_argument("--name", default=settings.MCP_SERVER_NAME)

    def handle(self, *args: Any, **options: Any) -> None:
        for title, text in snippets(options["url"], options["org"], options["name"]).items():
            self.stdout.write(f"\n# {title}\n{text}")
        self.stdout.write("")
