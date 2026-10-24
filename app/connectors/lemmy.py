from typing import Any
from uuid import uuid4

from app.config import get_settings
from app.connectors.base import ConnectorBase
from app.connectors.http_client import request_json
from app.connectors.spec_validate import raise_if_spec_violations, validate_against_manifest
from app.schemas.common import Connection, DestinationRef, Rendition


class LemmyConnector(ConnectorBase):
    key = "lemmy"

    def _base(self, destination: DestinationRef, connection: Connection) -> str:
        return (
            destination.instance_params.get("base_url")
            or connection.credentials.get("base_url")
            or get_settings().lemmy_base_url
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
        base = self._base(destination, connection).rstrip("/")
        community = destination.instance_params.get("community", "main")
        jwt = connection.credentials.get("jwt", "")
        url = f"{base}/api/v3/post"
        name = rendition.title[:200] or "Post"
        body = rendition.body
        if rendition.canonical_url:
            body = f"{body}\n\n{rendition.canonical_url}".strip()
        payload = {
            "name": name,
            "body": body,
            "community_id": destination.instance_params.get("community_id", 1),
            "custom_id": idempotency_key,
        }
        headers = {"Content-Type": "application/json"}
        if jwt:
            headers["Authorization"] = f"Bearer {jwt}"
        _, data = await request_json("POST", url, connector_key=self.key, headers=headers, json_body=payload)
        post = data.get("post_view", {}).get("post") or data.get("post") or data
        post_id = str(post.get("id") or uuid4())
        live_url = post.get("ap_id") or f"{base}/post/{post_id}"
        return {"platform_post_id": post_id, "live_url": live_url, "status": "published"}

    async def get_status(self, platform_post_id: str, connection: Connection) -> dict[str, Any]:
        base = (connection.credentials.get("base_url") or get_settings().lemmy_base_url).rstrip("/")
        url = f"{base}/api/v3/post?id={platform_post_id}"
        _, data = await request_json("GET", url, connector_key=self.key)
        post = data.get("post_view", {}).get("post") or {}
        return {"status": "live" if post else "unknown", "live_url": post.get("ap_id")}

    async def delete(self, platform_post_id: str, connection: Connection) -> dict[str, Any]:
        base = (connection.credentials.get("base_url") or get_settings().lemmy_base_url).rstrip("/")
        url = f"{base}/api/v3/post"
        jwt = connection.credentials.get("jwt", "")
        headers = {"Content-Type": "application/json"}
        if jwt:
            headers["Authorization"] = f"Bearer {jwt}"
        await request_json(
            "DELETE",
            url,
            connector_key=self.key,
            headers=headers,
            json_body={"post_id": int(platform_post_id) if platform_post_id.isdigit() else 1},
        )
        return {"deleted": True}
