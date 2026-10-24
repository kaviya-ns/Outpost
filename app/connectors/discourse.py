from typing import Any
from uuid import uuid4

from app.config import get_settings
from app.connectors.base import ConnectorBase
from app.connectors.http_client import request_json
from app.connectors.spec_validate import raise_if_spec_violations, validate_against_manifest
from app.schemas.common import Connection, DestinationRef, Rendition


class DiscourseConnector(ConnectorBase):
    key = "discourse"

    def _base_url(self, destination: DestinationRef, connection: Connection) -> str:
        return (
            destination.instance_params.get("base_url")
            or connection.credentials.get("base_url")
            or get_settings().discourse_mock_url
        )

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
        base = self._base_url(destination, connection).rstrip("/")
        api_key = connection.credentials.get("api_key", "test-key")
        username = connection.credentials.get("username", "system")
        url = f"{base}/posts.json"
        payload = {
            "title": rendition.title,
            "raw": rendition.body,
            "external_id": idempotency_key,
        }
        _, data = await request_json(
            "POST",
            url,
            connector_key=self.key,
            headers={"Api-Key": api_key, "Api-Username": username},
            json_body=payload,
        )
        post_id = str(data.get("id") or data.get("post_id") or uuid4())
        topic_id = data.get("topic_id", post_id)
        live_url = data.get("url") or f"{base}/t/topic/{topic_id}"
        return {"platform_post_id": post_id, "live_url": live_url, "status": "published"}

    async def get_status(self, platform_post_id: str, connection: Connection) -> dict[str, Any]:
        base = connection.credentials.get("base_url") or get_settings().discourse_mock_url
        url = f"{base.rstrip('/')}/posts/{platform_post_id}.json"
        api_key = connection.credentials.get("api_key", "test-key")
        username = connection.credentials.get("username", "system")
        _, data = await request_json(
            "GET",
            url,
            connector_key=self.key,
            headers={"Api-Key": api_key, "Api-Username": username},
        )
        return {"status": data.get("status", "live"), "live_url": data.get("url")}

    async def fetch_metrics(
        self, platform_post_id: str, connection: Connection, since: str | None = None
    ) -> dict[str, Any]:
        base = connection.credentials.get("base_url") or get_settings().discourse_mock_url
        url = f"{base.rstrip('/')}/posts/{platform_post_id}/metrics.json"
        _, data = await request_json(
            "GET",
            url,
            connector_key=self.key,
            headers={
                "Api-Key": connection.credentials.get("api_key", "test-key"),
                "Api-Username": connection.credentials.get("username", "system"),
            },
        )
        return data

    async def delete(self, platform_post_id: str, connection: Connection) -> dict[str, Any]:
        base = connection.credentials.get("base_url") or get_settings().discourse_mock_url
        url = f"{base.rstrip('/')}/posts/{platform_post_id}.json"
        api_key = connection.credentials.get("api_key", "test-key")
        username = connection.credentials.get("username", "system")
        await request_json(
            "DELETE",
            url,
            connector_key=self.key,
            headers={"Api-Key": api_key, "Api-Username": username},
        )
        return {"deleted": True}
