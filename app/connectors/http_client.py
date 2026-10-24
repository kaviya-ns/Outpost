import logging
from typing import Any

import httpx

from app.config import get_settings
from app.errors import ApiError

logger = logging.getLogger(__name__)


async def request_json(
    method: str,
    url: str,
    *,
    connector_key: str,
    headers: dict[str, str] | None = None,
    json_body: dict | None = None,
    timeout: float = 30.0,
) -> tuple[int, dict[str, Any]]:
    settings = get_settings()
    if settings.simulation_mode and not url.startswith("http://mock"):
        # Allow real local lemmy/ghost; mocks use mock-* hostnames in compose
        pass

    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            resp = await client.request(method, url, headers=headers, json=json_body)
        except httpx.RequestError as exc:
            raise ApiError(
                "PLATFORM_UNAVAILABLE",
                f"Platform request failed: {exc}",
                retryable=True,
                status_code=503,
            ) from exc

    if resp.status_code == 429:
        reset = resp.headers.get("Retry-After", resp.headers.get("X-RateLimit-Reset", "60"))
        raise ApiError(
            "PLATFORM_RATE_LIMIT",
            f"Rate limited; reset in {reset}s",
            retryable=True,
            status_code=429,
            details={"reset_seconds": reset},
        )

    try:
        data = resp.json() if resp.content else {}
    except Exception:
        data = {"raw": resp.text}

    if resp.status_code >= 400:
        from app.connectors.registry import get_connector

        conn = get_connector(connector_key)
        mapped = conn.map_platform_error(resp.status_code, data.get("message", resp.text))
        raise ApiError(
            mapped["code"],
            mapped["message"],
            retryable=mapped["retryable"],
            status_code=resp.status_code,
            details=data,
        )

    return resp.status_code, data
