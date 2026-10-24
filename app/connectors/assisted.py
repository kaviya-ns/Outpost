import json
from typing import Any

from app.connectors.base import ConnectorBase
from app.schemas.common import Connection, DestinationRef, Rendition
from app.services.storage import storage_service


class AssistedConnector(ConnectorBase):
    key = "assisted"

    async def validate(
        self, rendition: Rendition, destination: DestinationRef, connection: Connection
    ) -> dict[str, Any]:
        return {"ok": True, "violations": []}

    async def publish(
        self,
        rendition: Rendition,
        destination: DestinationRef,
        connection: Connection,
        idempotency_key: str,
    ) -> dict[str, Any]:
        pack = await self.build_assist_pack(rendition, destination)
        pack_url = storage_service.put_bytes(
            json.dumps(pack).encode("utf-8"),
            content_type="application/json",
            prefix="assist-packs",
        )
        return {
            "platform_post_id": f"assist-{idempotency_key[:32]}",
            "live_url": pack_url,
            "status": "assist_pack_ready",
        }

    async def get_status(self, platform_post_id: str, connection: Connection) -> dict[str, Any]:
        return {"status": "assist_pack_ready", "live_url": None}

    async def delete(self, platform_post_id: str, connection: Connection) -> dict[str, Any]:
        return {"deleted": True}

    async def build_assist_pack(self, rendition: Rendition, destination: DestinationRef) -> dict[str, Any]:
        checklist = [
            "Confirm community rules allow this post",
            "Add required AI disclosure if applicable",
            "Use discussion-first framing in the opening line",
            "Paste canonical URL in the designated field if required",
        ]
        if destination.rules.get("disclosure_required") or rendition.is_ai_generated:
            checklist.insert(0, "Include AI-generated content disclosure")
        caption = rendition.body
        if rendition.title:
            caption = f"**{rendition.title}**\n\n{caption}"
        files = [{"type": "text", "name": "caption.md", "content": caption}]
        for i, url in enumerate(rendition.media_urls):
            files.append({"type": "media", "name": f"media_{i}", "url": url})
        return {
            "files": files,
            "caption": caption,
            "deep_link": destination.url or destination.instance_params.get("submit_url", ""),
            "checklist": checklist,
            "destination": destination.name,
        }
