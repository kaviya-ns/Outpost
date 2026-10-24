#!/usr/bin/env python3
"""Run a folder of JSON publish requests against the API and write results."""

import argparse
import json
import sys
import time
import uuid
from pathlib import Path

import httpx


def run_one(client: httpx.Client, base: str, payload: dict, out_dir: Path) -> dict:
    headers = {"Idempotency-Key": payload.get("idempotency_key") or str(uuid.uuid4())}
    resp = client.post(f"{base}/api/v1/publish", json=payload, headers=headers)
    result = {"http_status": resp.status_code, "body": resp.json()}
    if resp.status_code == 202:
        job_id = result["body"]["job_id"]
        for _ in range(60):
            job = client.get(f"{base}/api/v1/jobs/{job_id}").json()
            if job["status"] in ("succeeded", "failed"):
                result["job"] = job
                break
            time.sleep(0.5)
    out_file = out_dir / f"{headers['Idempotency-Key']}.json"
    out_file.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="IncuBrix batch API runner")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--input", required=True, help="Folder or single JSON file")
    parser.add_argument("--output", required=True, help="Output folder")
    args = parser.parse_args()

    in_path = Path(args.input)
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    files = [in_path] if in_path.is_file() else sorted(in_path.glob("*.json"))
    index = []
    with httpx.Client(timeout=120.0) as client:
        for f in files:
            payload = json.loads(f.read_text(encoding="utf-8"))
            res = run_one(client, args.base_url.rstrip("/"), payload, out_dir)
            index.append({"input": str(f), "status": res.get("job", {}).get("status", res["http_status"])})
    (out_dir / "index.json").write_text(json.dumps(index, indent=2), encoding="utf-8")
    print(f"Wrote {len(files)} results to {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
