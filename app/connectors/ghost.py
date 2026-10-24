import jwt
import time
from typing import Any
from uuid import uuid4

from app.config import get_settings
from app.connectors.base import ConnectorBase
from app.connectors.http_client import request_json
from app.connectors.spec_validate import raise_if_spec_violations, validate_against_manifest
from app.schemas.common import Connection, DestinationRef, Rendition


class GhostConnector(ConnectorBase):
    key = "ghost"

    def _admin_token(self, connection: Connection) -> str:
        key = connection.credentials.get("admin_api_key") or get_settings().ghost_admin_api_key
        if not key:
            return "ghost-test-token"
        try:
            id_part, secret = key.split(":", 1)
            iat = int(time.time())
            header = {"alg": "HS256", "typ": "JWT", "kid": id_part}
            payload = {"iat": iat, "exp": iat + 300, "aud": "/admin/"}
            return jwt.encode(payload, bytes.fromhex(secret), algorithm="HS256", headers=header)
        except Exception:
            return key

    def _url(self, destination: DestinationRef, connection: Connection) -> str:
        return (
            destination.instance_params.get("base_url")
            or connection.credentials.get("base_url")
            or get_settings().ghost_url
        ).rstrip("/")

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
        base = self._url(destination, connection)
        token = self._admin_token(connection)
        payload = {
            "posts": [
                {
                    "title": rendition.title,
                    "html": rendition.body,
                    "status": "published",
                    "custom_excerpt": idempotency_key[:50],
                }
            ]
        }
        _, data = await request_json(
            "POST",
            f"{base}/ghost/api/admin/posts/",
            connector_key=self.key,
            headers={"Authorization": f"Ghost {token}", "Content-Type": "application/json"},
            json_body=payload,
        )
        posts = data.get("posts") or []
        post = posts[0] if posts else data
        post_id = str(post.get("id") or uuid4())
        live_url = post.get("url") or f"{base}/{post.get('slug', post_id)}"
        return {"platform_post_id": post_id, "live_url": live_url, "status": "published"}

    async def get_status(self, platform_post_id: str, connection: Connection) -> dict[str, Any]:
        base = self._url(DestinationRef(), connection)
        token = self._admin_token(connection)
        _, data = await request_json(
            "GET",
            f"{base}/ghost/api/admin/posts/{platform_post_id}/",
            connector_key=self.key,
            headers={"Authorization": f"Ghost {token}"},
        )
        posts = data.get("posts") or []
        post = posts[0] if posts else {}
        return {"status": post.get("status", "published"), "live_url": post.get("url")}

    async def fetch_metrics(
        self, platform_post_id: str, connection: Connection, since: str | None = None
    ) -> dict[str, Any]:
        base = self._url(DestinationRef(), connection)
        token = self._admin_token(connection)
        _, data = await request_json(
            "GET",
            f"{base}/ghost/api/admin/posts/{platform_post_id}/metrics/",
            connector_key=self.key,
            headers={"Authorization": f"Ghost {token}"},
        )
        return data

    async def delete(self, platform_post_id: str, connection: Connection) -> dict[str, Any]:
        base = self._url(DestinationRef(), connection)
        token = self._admin_token(connection)
        await request_json(
            "DELETE",
            f"{base}/ghost/api/admin/posts/{platform_post_id}/",
            connector_key=self.key,
            headers={"Authorization": f"Ghost {token}"},
        )
        return {"deleted": True}
