from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.schemas.common import JobResponse, OutputManifest
from app.services.catalogue_import import import_catalogue_csv
from app.services.jobs import create_job, schedule_job

router = APIRouter(prefix="/catalogue", tags=["catalogue"])


@router.post("/import", status_code=202, response_model=JobResponse)
async def import_catalogue(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> JobResponse:
    raw = (await file.read()).decode("utf-8", errors="replace")
    job = await create_job(db, "catalogue_import", {"filename": file.filename})

    async def handler(session: AsyncSession, _job) -> dict:
        report = await import_catalogue_csv(session, raw)
        await session.commit()
        return report

    schedule_job(job.id, handler, OutputManifest(settings={"filename": file.filename}))
    return JobResponse(job_id=job.id, status="queued", progress=0)
