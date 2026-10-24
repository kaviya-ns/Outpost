from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.errors import ApiError, http_exception_from_api_error
from app.schemas.common import JobResponse, MetricsFetchRequest, OutputManifest
from app.services.jobs import create_job, schedule_job
from app.services.metrics import fetch_normalized_metrics

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("")
async def get_metrics(
    destination_id: str = Query(...),
    platform_post_id: str = Query(...),
    since: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await fetch_normalized_metrics(db, destination_id, platform_post_id, since)
    except ApiError as exc:
        raise http_exception_from_api_error(exc) from exc


@router.post("/fetch", status_code=202, response_model=JobResponse)
async def fetch_metrics_job(body: MetricsFetchRequest, db: AsyncSession = Depends(get_db)) -> JobResponse:
    job = await create_job(db, "fetch_metrics", body.model_dump())

    async def handler(session: AsyncSession, _job) -> dict:
        return await fetch_normalized_metrics(
            session,
            body.destination_id,
            body.platform_post_id,
            body.since,
        )

    schedule_job(job.id, handler, OutputManifest())
    return JobResponse(job_id=job.id, status="queued", progress=0)
