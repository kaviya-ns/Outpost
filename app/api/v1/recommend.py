from pathlib import Path

from fastapi import APIRouter, Depends, File, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.schemas.common import JobResponse, OutputManifest, Rendition
from app.services.jobs import create_job, schedule_job
from app.services.recommender import evaluate_labelled_set, load_labelled_set, recommend_destinations

router = APIRouter(prefix="/recommend", tags=["recommend"])


class RecommendRequest(BaseModel):
    rendition: Rendition
    limit: int = Field(default=20, ge=1, le=100)
    certified_only: bool = False


class EvaluateRequest(BaseModel):
    k: int = Field(default=10, ge=1, le=50)
    use_default_labelled_set: bool = True


@router.post("")
async def recommend(body: RecommendRequest, db: AsyncSession = Depends(get_db)) -> dict:
    ranked = await recommend_destinations(
        db,
        body.rendition,
        limit=body.limit,
        certified_only=body.certified_only,
    )
    return {"recommendations": ranked, "count": len(ranked)}


@router.post("/evaluate")
async def evaluate_recommender(
    body: EvaluateRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    items = load_labelled_set() if body.use_default_labelled_set else []
    if not items:
        return {"error": "No labelled items loaded", "precision_at_10_macro": 0.0}
    return await evaluate_labelled_set(db, items, k=body.k)


@router.post("/evaluate/upload", status_code=202, response_model=JobResponse)
async def evaluate_upload(
    file: UploadFile = File(...),
    k: int = 10,
    db: AsyncSession = Depends(get_db),
) -> JobResponse:
    raw = (await file.read()).decode("utf-8")
    job = await create_job(db, "recommender_evaluate", {"filename": file.filename, "k": k})

    async def handler(session: AsyncSession, _job) -> dict:
        import json

        data = json.loads(raw)
        items = data.get("items", data)
        return await evaluate_labelled_set(session, items, k=k)

    schedule_job(job.id, handler, OutputManifest(settings={"eval": "recommender"}))
    return JobResponse(job_id=job.id, status="queued", progress=0)
