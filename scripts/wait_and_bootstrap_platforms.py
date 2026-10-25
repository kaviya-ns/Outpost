#!/usr/bin/env python3
"""Compose init: wait for Ghost/Lemmy and write data/local_platforms.json."""

import sys

from app.services.platform_bootstrap import ensure_local_platforms_ready


def main() -> int:
    try:
        ensure_local_platforms_ready()
    except Exception as exc:  # noqa: BLE001
        print(f"platform bootstrap failed: {exc}", file=sys.stderr)
        return 1
    print("platform bootstrap ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
