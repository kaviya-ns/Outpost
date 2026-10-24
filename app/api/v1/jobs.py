from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.errors import JOB_NOT_FOUND, ApiError, http_exception_from_api_error
from app.schemas.common import JobResponse
from app.services.jobs import get_job
from app.services.storage import storage_service

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}", response_model=JobResponse)
async def get_job_status(job_id: str, db: AsyncSession = Depends(get_db)) -> JobResponse:
    job = await get_job(db, job_id)
    if not job:
        raise http_exception_from_api_error(
            ApiError(JOB_NOT_FOUND, "Job not found", status_code=404)
        )
    result_links: list[str] = []
    if job.result:
        for key in ("manifest_url", "report_url", "assist_pack_url"):
            if job.result.get(key):
                result_links.append(job.result[key])
        if job.result.get("live_url"):
            result_links.append(job.result["live_url"])
    return JobResponse(
        job_id=job.id,
        status=job.status,
        progress=job.progress,
        result=job.result,
        result_links=result_links,
        error=job.error,
        manifest=job.manifest,
    )
