#!/usr/bin/env python3
"""Certify all seeded destinations and write evidence to test-pack/certification/."""

import argparse
import json
import sys
import time
from pathlib import Path

import os

import httpx


def wait_job(client: httpx.Client, base: str, job_id: str) -> dict:
    for _ in range(120):
        r = client.get(f"{base}/api/v1/jobs/{job_id}")
        r.raise_for_status()
        data = r.json()
        if data["status"] in ("succeeded", "failed"):
            return data
        time.sleep(0.25)
    raise TimeoutError(job_id)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument(
        "--demo-token",
        default=None,
        help="X-Demo-Token for protected live demos (or set DEMO_API_KEY env)",
    )
    parser.add_argument("--output", default="test-pack/certification")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)

    token = args.demo_token or os.environ.get("DEMO_API_KEY")
    headers = {"X-Demo-Token": token} if token else {}

    index = []
    with httpx.Client(timeout=60.0, headers=headers) as client:
        health = client.get(f"{base}/api/v1/health")
        health.raise_for_status()
        dests = client.get(f"{base}/api/v1/destinations").json()
        for dest in dests:
            started = time.perf_counter()
            resp = client.post(f"{base}/api/v1/destinations/{dest['id']}/certify")
            resp.raise_for_status()
            job_id = resp.json()["job_id"]
            job = wait_job(client, base, job_id)
            elapsed = time.perf_counter() - started
            record = {
                "destination_id": dest["id"],
                "name": dest["name"],
                "connector_key": dest["connector_key"],
                "job_id": job_id,
                "status": job["status"],
                "duration_s": round(elapsed, 3),
                "result": job.get("result"),
                "error": job.get("error"),
            }
            file_path = out / f"{dest['connector_key']}_{dest['id']}.json"
            file_path.write_text(json.dumps(record, indent=2), encoding="utf-8")
            index.append({"connector": dest["connector_key"], "file": str(file_path), "status": job["status"]})
            print(f"{dest['connector_key']}: {job['status']} ({elapsed:.2f}s)")

    (out / "index.json").write_text(json.dumps(index, indent=2), encoding="utf-8")
    failed = [i for i in index if i["status"] != "succeeded"]
    if failed:
        print(f"{len(failed)} certification(s) failed", file=sys.stderr)
        return 1
    print(f"All {len(index)} certifications passed. Evidence in {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
