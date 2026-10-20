"""Post-deploy smoke test against a running instance.

    python scripts/e2e_smoke.py --base-url https://app.example.com --api-key "$API_KEY" \\
        [--org <organization-id>] [--mcp]

Checks, in order: liveness and readiness, the action catalog, that one Idempotency-Key produces
exactly one effect, that the same action is visible over MCP (with --mcp), and that the response
headers carry the hardening the platform promises. Exits 1 on the first failure. It creates one
note titled "smoke <id>" and archives it afterwards.
"""

from __future__ import annotations

import argparse
import sys
import uuid

import httpx


def check(condition: bool, label: str, detail: str = "") -> None:
    print(
        ("ok   " if condition else "FAIL ")
        + label
        + (f"  ({detail})" if detail and not condition else "")
    )
    if not condition:
        sys.exit(1)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--api-key", required=True)
    parser.add_argument("--org", help="Organization id when the key belongs to several")
    parser.add_argument("--mcp", action="store_true", help="Also check /mcp (MCP_ENABLED)")
    args = parser.parse_args()

    base = args.base_url.rstrip("/")
    headers = {"Authorization": f"Bearer {args.api_key}"}
    if args.org:
        headers["X-Organization-Id"] = args.org
    client = httpx.Client(base_url=base, headers=headers, timeout=15, follow_redirects=False)

    live = client.get("/api/v1/health/live/")
    check(live.status_code == 200, "liveness", str(live.status_code))
    ready = client.get("/api/v1/health/ready/")
    check(ready.status_code == 200, "readiness", str(ready.status_code))
    check(
        ready.headers.get("cache-control", "").lower().find("no-store") >= 0,
        "API responses are not cacheable",
    )

    catalog = client.get("/api/v1/actions/")
    check(catalog.status_code == 200, "action catalog", str(catalog.status_code))
    names = {a["name"] for a in catalog.json()["items"]}
    check("notes.create" in names, "catalog lists notes.create", f"{len(names)} actions")

    title = f"smoke {uuid.uuid4().hex[:8]}"
    key = str(uuid.uuid4())
    first = client.post(
        "/api/v1/actions/notes.create/", json={"title": title}, headers={"Idempotency-Key": key}
    )
    check(first.status_code in (200, 201), "create note", first.text[:200])
    second = client.post(
        "/api/v1/actions/notes.create/", json={"title": title}, headers={"Idempotency-Key": key}
    )
    check(second.json() == first.json(), "same Idempotency-Key returns the same result")
    listed = client.post("/api/v1/actions/notes.list/", json={"limit": 50}).json()
    matching = [n for n in listed.get("items", []) if n["title"] == title]
    check(len(matching) == 1, "exactly one note was created", f"found {len(matching)}")

    changed = client.post(
        "/api/v1/actions/notes.create/",
        json={"title": title + " changed"},
        headers={"Idempotency-Key": key},
    )
    check(
        changed.status_code == 409,
        "same key with another payload is refused",
        str(changed.status_code),
    )

    if args.mcp:
        rpc = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
            headers={"Accept": "application/json, text/event-stream"},
        )
        check(rpc.status_code == 200, "MCP tools/list", str(rpc.status_code))
        check("notes_create" in rpc.text or "notes.create" in rpc.text, "MCP exposes notes.create")

    client.post("/api/v1/actions/notes.archive/", json={"id": matching[0]["id"]})
    print("\nsmoke test passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
