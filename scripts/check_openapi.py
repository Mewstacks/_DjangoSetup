"""Fail when the committed OpenAPI file differs from what the code generates.

python scripts/check_openapi.py          # check
python scripts/check_openapi.py --write  # regenerate openapi-schema.yml
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMMITTED = ROOT / "openapi-schema.yml"


def main() -> int:
    env = {**os.environ, "DJANGO_SETTINGS_MODULE": "config.settings.test"}
    with tempfile.TemporaryDirectory() as tmp:
        generated = Path(tmp) / "schema.yml"
        subprocess.run(  # noqa: S603
            [sys.executable, "manage.py", "spectacular", "--validate", "--file", str(generated)],
            cwd=ROOT,
            env=env,
            check=True,
        )
        fresh = generated.read_text(encoding="utf-8")
    if "--write" in sys.argv:
        COMMITTED.write_text(fresh, encoding="utf-8", newline="\n")
        print(f"wrote {COMMITTED.name}")
        return 0
    current = COMMITTED.read_text(encoding="utf-8") if COMMITTED.exists() else ""
    if current != fresh:
        print("openapi-schema.yml is out of date; run `python scripts/check_openapi.py --write`.")
        return 1
    print("openapi-schema.yml is up to date")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
