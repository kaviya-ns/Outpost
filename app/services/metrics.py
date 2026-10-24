from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.registry import get_connector
from app.errors import ApiError
from app.models.tables import Destination, PostRecord
from app.schemas.common import Connection


def normalize_metrics(raw: dict[str, Any]) -> dict[str, Any]:
    if "metrics" in raw and isinstance(raw["metrics"], dict):
        raw = {**raw, **raw["metrics"]}
    return {
        "views": int(raw.get("views") or raw.get("page_views_count") or 0),
        "likes": int(raw.get("likes") or raw.get("public_reactions_count") or 0),
        "comments": int(raw.get("comments") or raw.get("comments_count") or 0),
        "shares": int(raw.get("shares") or 0),
        "saves": int(raw.get("saves") or 0),
        "watch_time_s": float(raw.get("watch_time_s") or 0),
        "clicks": int(raw.get("clicks") or 0),
    }


async def fetch_normalized_metrics(
    db: AsyncSession,
    destination_id: str,
    platform_post_id: str,
    since: str | None = None,
) -> dict[str, Any]:
    result = await db.execute(select(Destination).where(Destination.id == destination_id))
    destination = result.scalar_one_or_none()
    if not destination:
        raise ApiError("DESTINATION_NOT_FOUND", "Destination not found", status_code=404)

    from app.services.manifest_loader import manifest_loader

    manifest = manifest_loader.get(destination.connector_key)
    caps = (manifest or {}).get("capabilities", [])
    if "metrics" not in caps:
        raise ApiError(
            "VALIDATION_ERROR",
            f"Connector {destination.connector_key} does not support metrics",
            status_code=422,
        )

    conn = Connection(credentials=destination.connection.get("connection", {}).get("credentials", destination.connection))
    connector = get_connector(destination.connector_key)
    raw = await connector.fetch_metrics(platform_post_id, conn, since)
    normalized = normalize_metrics(raw)

    post = await db.execute(
        select(PostRecord).where(
            PostRecord.destination_id == destination_id,
            PostRecord.platform_post_id == platform_post_id,
        )
    )
    post_row = post.scalar_one_or_none()
    return {
        "destination_id": destination_id,
        "connector_key": destination.connector_key,
        "platform_post_id": platform_post_id,
        "live_url": post_row.live_url if post_row else None,
        "metrics": normalized,
        "raw": raw,
    }
