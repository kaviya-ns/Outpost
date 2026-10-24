from typing import Any
from uuid import uuid4

from app.config import get_settings
from app.connectors.base import ConnectorBase
from app.connectors.http_client import request_json
from app.connectors.spec_validate import raise_if_spec_violations, validate_against_manifest
from app.schemas.common import Connection, DestinationRef, Rendition


class DevToConnector(ConnectorBase):
    key = "devto"

    def _base(self, connection: Connection) -> str:
        return connection.credentials.get("base_url") or get_settings().devto_mock_url

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
        base = self._base(connection).rstrip("/")
        api_key = connection.credentials.get("api_key", "devto-test")
        payload = {
            "title": rendition.title,
            "body_markdown": rendition.body,
            "canonical_url": rendition.canonical_url,
            "idempotency_key": idempotency_key,
        }
        _, data = await request_json(
            "POST",
            f"{base}/api/articles",
            connector_key=self.key,
            headers={"api-key": api_key, "Content-Type": "application/json"},
            json_body=payload,
        )
        post_id = str(data.get("id") or uuid4())
        live_url = data.get("url") or f"{base}/articles/{post_id}"
        return {"platform_post_id": post_id, "live_url": live_url, "status": "published"}

    async def get_status(self, platform_post_id: str, connection: Connection) -> dict[str, Any]:
        base = self._base(connection).rstrip("/")
        api_key = connection.credentials.get("api_key", "devto-test")
        _, data = await request_json(
            "GET",
            f"{base}/api/articles/{platform_post_id}",
            connector_key=self.key,
            headers={"api-key": api_key},
        )
        return {"status": "live", "live_url": data.get("url")}

    async def fetch_metrics(
        self, platform_post_id: str, connection: Connection, since: str | None = None
    ) -> dict[str, Any]:
        base = self._base(connection).rstrip("/")
        api_key = connection.credentials.get("api_key", "devto-test")
        _, data = await request_json(
            "GET",
            f"{base}/api/articles/{platform_post_id}/metrics",
            connector_key=self.key,
            headers={"api-key": api_key},
        )
        return data

    async def delete(self, platform_post_id: str, connection: Connection) -> dict[str, Any]:
        base = self._base(connection).rstrip("/")
        api_key = connection.credentials.get("api_key", "devto-test")
        await request_json(
            "DELETE",
            f"{base}/api/articles/{platform_post_id}",
            connector_key=self.key,
            headers={"api-key": api_key},
        )
        return {"deleted": True}
