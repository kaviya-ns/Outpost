#!/usr/bin/env python3
"""Run precision@10 evaluation against the labelled set via HTTP API or in-process."""

import argparse
import json
import sys
from pathlib import Path

import httpx


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate recommender precision@10")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--output", default="test-pack/recommender_eval.json")
    parser.add_argument("--k", type=int, default=10)
    args = parser.parse_args()
    base = args.base_url.rstrip("/")

    with httpx.Client(timeout=120.0) as client:
        resp = client.post(
            f"{base}/api/v1/recommend/evaluate",
            json={"k": args.k, "use_default_labelled_set": True},
        )
        resp.raise_for_status()
        report = resp.json()

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    macro = report.get("precision_at_10_macro", 0)
    print(f"precision@{args.k} (macro): {macro}")
    print(f"Report written to {out}")
    return 0 if macro > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
