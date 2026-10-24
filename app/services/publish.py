from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.registry import get_connector
from app.errors import CONNECTOR_DISABLED, ApiError
from app.models.tables import Destination, PostRecord
from app.schemas.common import Connection, DestinationRef, Rendition
from app.config import get_settings
from app.services.rules import check_posting_rules
from app.services.tailoring import tailor_rendition


async def publish_to_destination(
    db: AsyncSession,
    destination_id: str,
    rendition: Rendition,
    idempotency_key: str,
    *,
    is_test: bool = False,
    connection_override: Connection | None = None,
    tailor: bool | None = None,
) -> dict:
    settings = get_settings()
    if settings.connector_disabled:
        raise ApiError(CONNECTOR_DISABLED, "Connector kill switch is enabled", retryable=False, status_code=503)

    result = await db.execute(select(Destination).where(Destination.id == destination_id))
    destination = result.scalar_one_or_none()
    if not destination:
        raise ApiError("DESTINATION_NOT_FOUND", "Destination not found", status_code=404)

    if not destination.publish_enabled and not is_test:
        raise ApiError(
            "CONNECTOR_DISABLED",
            "Destination is demoted and excluded from publishing",
            retryable=False,
            status_code=403,
        )

    do_tailor = tailor if tailor is not None else settings.tailor_on_publish
    tailor_warnings: list[str] = []
    if do_tailor:
        rendition, tailor_warnings = tailor_rendition(destination, rendition)

    existing = await db.execute(select(PostRecord).where(PostRecord.idempotency_key == idempotency_key))
    if existing.scalar_one_or_none():
        prior = await db.execute(select(PostRecord).where(PostRecord.idempotency_key == idempotency_key))
        post = prior.scalar_one()
        return {
            "platform_post_id": post.platform_post_id,
            "live_url": post.live_url,
            "status": post.status,
            "deduplicated": True,
        }

    rule_result = await check_posting_rules(db, destination, rendition.model_dump())
    if not rule_result.ok:
        freq_only = all(v.get("code") == "DEST_RULE_FREQUENCY_CAP" for v in rule_result.violations)
        if freq_only:
            raise ApiError(
                "DEST_RULE_FREQUENCY_CAP",
                rule_result.violations[0]["message"],
                retryable=True,
                status_code=429,
                details={"violations": rule_result.violations},
            )
        raise ApiError(
            "DEST_RULE_VIOLATION",
            "Posting blocked by destination rules",
            retryable=False,
            status_code=422,
            details={"violations": rule_result.violations},
        )

    connector = get_connector(destination.connector_key)
    dest_ref = DestinationRef(
        id=destination.id,
        name=destination.name,
        url=destination.url,
        platform_key=destination.platform_key,
        surface=destination.surface,
        connector_key=destination.connector_key,
        instance_params=destination.connection.get("instance_params", {}),
    )
    conn = connection_override or Connection(**destination.connection.get("connection", {"credentials": destination.connection}))

    validation = await connector.validate(rendition, dest_ref, conn)
    if not validation.get("ok"):
        raise ApiError(
            "DEST_SPEC_VIOLATION",
            "Format validation failed",
            retryable=False,
            status_code=422,
            details=validation,
        )

    pub = await connector.publish(rendition, dest_ref, conn, idempotency_key)
    record = PostRecord(
        destination_id=destination.id,
        connector_key=destination.connector_key,
        platform_post_id=pub["platform_post_id"],
        live_url=pub.get("live_url"),
        status=pub.get("status", "published"),
        idempotency_key=idempotency_key,
        is_test=is_test,
    )
    db.add(record)
    await db.flush()
    if tailor_warnings:
        pub["tailor_warnings"] = tailor_warnings
    return pub
