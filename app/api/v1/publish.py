import uuid

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.errors import ApiError, http_exception_from_api_error
from app.schemas.common import JobResponse, OutputManifest, PublishRequest
from app.services.idempotency import get_or_create_idempotency, lookup_idempotency, store_idempotency_response
from app.services.jobs import create_job, get_job, schedule_job
from app.services.publish import publish_to_destination
from app.services.storage import storage_service

router = APIRouter(tags=["publish"])


@router.post("/publish", status_code=202, response_model=JobResponse)
async def publish(
    request: Request,
    body: PublishRequest,
    db: AsyncSession = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> JobResponse:
    key = idempotency_key or body.idempotency_key or str(uuid.uuid4())
    correlation_id = request.headers.get("X-Correlation-Id")

    replay = await lookup_idempotency(db, "publish", key, body.model_dump())
    if replay:
        job = await get_job(db, replay["job_id"])
        if job:
            return JobResponse(
                job_id=job.id,
                status=job.status,
                progress=job.progress,
                result=job.result,
                error=job.error,
                manifest=job.manifest,
            )
        return JobResponse(**replay)

    job = await create_job(
        db,
        "publish",
        body.model_dump(),
        correlation_id=correlation_id,
        callback_url=body.callback_url,
    )

    async def handler(session: AsyncSession, active_job) -> dict:
        result = await publish_to_destination(
            session,
            body.destination_id,
            body.rendition,
            key,
            is_test=body.is_test,
            connection_override=body.connection,
            tailor=body.tailor,
        )
        man = OutputManifest(
            settings={"simulation": False},
            warnings=[],
        )
        if body.rendition.is_ai_generated:
            man.ai_generated_labels.append("rendition")
        from app.config import get_settings as gs

        if result.get("live_url") and gs().s3_enabled:
            result["manifest_url"] = storage_service.put_bytes(
                str(man.model_dump()).encode(),
                content_type="application/json",
            )
        await session.commit()
        await store_idempotency_response(
            session,
            "publish",
            key,
            JobResponse(
                job_id=active_job.id,
                status="succeeded",
                progress=100,
                result=result,
            ).model_dump(),
        )
        await session.commit()
        return result

    schedule_job(job.id, handler)
    response = JobResponse(job_id=job.id, status="queued", progress=0)
    await get_or_create_idempotency(db, "publish", key, body.model_dump(), job.id)
    await store_idempotency_response(db, "publish", key, response.model_dump())
    await db.commit()
    return response


@router.post("/validate")
async def validate_post(body: PublishRequest, db: AsyncSession = Depends(get_db)) -> dict:
    from sqlalchemy import select

    from app.connectors.registry import get_connector
    from app.models.tables import Destination
    from app.schemas.common import Connection, DestinationRef
    from app.services.rules import check_posting_rules

    result = await db.execute(select(Destination).where(Destination.id == body.destination_id))
    destination = result.scalar_one_or_none()
    if not destination:
        raise http_exception_from_api_error(
            ApiError("DESTINATION_NOT_FOUND", "Destination not found", status_code=404)
        )
    rules = await check_posting_rules(db, destination, body.rendition.model_dump())
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
    conn = body.connection or Connection(credentials=destination.connection)
    spec = await connector.validate(body.rendition, dest_ref, conn)
    return {
        "ok": rules.ok and spec.get("ok", True),
        "rule_violations": rules.violations,
        "spec_violations": spec.get("violations", []),
    }
