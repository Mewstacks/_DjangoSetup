"""Container health probe: the web role answers /api/v1/health/live/; other roles have no port."""

from __future__ import annotations

import os
import sys
import urllib.request


def main() -> int:
    if os.environ.get("CONTAINER_ROLE", "web") != "web":
        return 0
    port = os.environ.get("PORT", "8000")
    url = f"http://127.0.0.1:{port}/api/v1/health/live/"
    try:
        with urllib.request.urlopen(url, timeout=3) as response:
            return 0 if response.status == 200 else 1
    except OSError:
        return 1


if __name__ == "__main__":
    sys.exit(main())
