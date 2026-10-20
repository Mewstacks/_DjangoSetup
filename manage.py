#!/usr/bin/env python
from __future__ import annotations

import os
import sys
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parent
    sys.path.insert(0, str(root / "src"))
    # Development opts in through .env (written by scripts/init_local.py). Without it the
    # safe module is used, so a forgotten variable can never expose a DEBUG server.
    try:
        from dotenv import load_dotenv

        load_dotenv(root / ".env")
    except ImportError:  # python-dotenv is a production dependency, but stay tolerant
        pass
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")

    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
