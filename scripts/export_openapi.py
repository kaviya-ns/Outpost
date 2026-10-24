#!/usr/bin/env python3
"""Write openapi.yaml from the running FastAPI schema."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.main import app  # noqa: E402


def main() -> int:
    out = ROOT / "openapi.yaml"
    schema = app.openapi()
    out.write_text(json.dumps(schema, indent=2), encoding="utf-8")
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
