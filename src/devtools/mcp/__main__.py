from __future__ import annotations

import os

# The committed catalog and agent files describe the platform with its optional apps on, so the
# development server loads them on too: otherwise the freshness check reports a diff that only
# comes from this machine's switches (OAuth tokens, their cleanup job).
for switch in ("OAUTH_ENABLED", "MCP_ENABLED"):
    os.environ.setdefault(switch, "true")

from devtools.mcp.server import main  # noqa: E402

main()
