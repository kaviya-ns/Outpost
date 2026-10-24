import hashlib
import hmac
import json
from typing import Any
from uuid import uuid4

import httpx

from app.config import get_settings
from app.connectors.base import ConnectorBase
from app.connectors.spec_validate import raise_if_spec_violations, validate_against_manifest
from app.errors import ApiError
from app.schemas.common import Connection, DestinationRef, Rendition


class WebhookConnector(ConnectorBase):
    key = "webhook_hmac"

    async def validate(
        self, rendition: Rendition, destination: DestinationRef, connection: Connection
    ) -> dict[str, Any]:
        return validate_against_manifest(self.key, rendition, destination)

    async def publish(
        self,
        rendition: Rendition,
        destination: DestinationRef,
        connection: Connection,
        idempotency_key: str,
    ) -> dict[str, Any]:
        raise_if_spec_violations(await self.validate(rendition, destination, connection))
        url = destination.instance_params.get("webhook_url") or connection.credentials.get(
            "webhook_url", get_settings().webhook_partner_url
        )
        secret = connection.credentials.get("hmac_secret", "partner-secret")
        body = {
            "idempotency_key": idempotency_key,
            "title": rendition.title,
            "body": rendition.body,
            "canonical_url": rendition.canonical_url,
            "content_type": rendition.content_type,
        }
        raw = json.dumps(body, sort_keys=True).encode()
        sig = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                resp = await client.post(
                    url,
                    content=raw,
                    headers={
                        "Content-Type": "application/json",
                        "X-IncuBrix-Signature": sig,
                        "Idempotency-Key": idempotency_key,
                    },
                )
            except httpx.RequestError as exc:
                raise ApiError("PLATFORM_UNAVAILABLE", str(exc), retryable=True, status_code=503) from exc
        if resp.status_code >= 400:
            mapped = self.map_platform_error(resp.status_code, resp.text)
            raise ApiError(
                mapped["code"],
                mapped["message"],
                retryable=mapped["retryable"],
                status_code=resp.status_code,
            )
        data = resp.json() if resp.content else {}
        post_id = str(data.get("id") or data.get("platform_post_id") or uuid4())
        live_url = data.get("live_url") or f"{url}/posts/{post_id}"
        return {"platform_post_id": post_id, "live_url": live_url, "status": "published"}

    async def get_status(self, platform_post_id: str, connection: Connection) -> dict[str, Any]:
        url = connection.credentials.get("webhook_url", get_settings().webhook_partner_url)
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(f"{url.rstrip('/')}/posts/{platform_post_id}")
        if resp.status_code >= 400:
            return {"status": "unknown", "live_url": None}
        data = resp.json()
        return {"status": data.get("status", "live"), "live_url": data.get("live_url")}

    async def delete(self, platform_post_id: str, connection: Connection) -> dict[str, Any]:
        url = connection.credentials.get("webhook_url", get_settings().webhook_partner_url)
        async with httpx.AsyncClient(timeout=30.0) as client:
            await client.delete(f"{url.rstrip('/')}/posts/{platform_post_id}")
        return {"deleted": True}
