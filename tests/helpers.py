import asyncio
from typing import Any

from httpx import AsyncClient


async def wait_for_job(client: AsyncClient, job_id: str, timeout_s: float = 15.0) -> dict[str, Any]:
    deadline = asyncio.get_event_loop().time() + timeout_s
    while asyncio.get_event_loop().time() < deadline:
        resp = await client.get(f"/api/v1/jobs/{job_id}")
        resp.raise_for_status()
        data = resp.json()
        if data["status"] in ("succeeded", "failed"):
            return data
        await asyncio.sleep(0.05)
    raise TimeoutError(f"Job {job_id} did not complete within {timeout_s}s")


def connector_keys_from_destinations(destinations: list[dict]) -> set[str]:
    return {d["connector_key"] for d in destinations}
