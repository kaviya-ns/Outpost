from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.tables import Destination
from app.schemas.common import JobResponse, OutputManifest
from app.services.certification import run_certification
from app.services.jobs import create_job, get_job, schedule_job

router = APIRouter(prefix="/destinations", tags=["destinations"])


class DestinationCreate(BaseModel):
    name: str
    url: str
    platform_key: str
    connector_key: str
    surface: str = "default"
    connection: dict = Field(default_factory=dict)
    frequency_cap: dict = Field(default_factory=lambda: {"count": 1, "window_days": 7})
    self_promo_allowed: bool = True
    link_policy: str = "allowed"
    disclosure_required: bool = False
    automation_allowed: bool = True
    audience_tags: list[str] = Field(default_factory=list)
    relevance_score: int | None = None
    category: str | None = None


@router.get("")
async def list_destinations(db: AsyncSession = Depends(get_db)) -> list[dict]:
    result = await db.execute(select(Destination))
    rows = result.scalars().all()
    return [
        {
            "id": d.id,
            "name": d.name,
            "url": d.url,
            "connector_key": d.connector_key,
            "platform_key": d.platform_key,
            "certified": d.certified,
            "level": d.level,
            "publish_enabled": d.publish_enabled,
            "disclosure_required": d.disclosure_required,
            "self_promo_allowed": d.self_promo_allowed,
            "last_certified_at": d.last_certified_at.isoformat() if d.last_certified_at else None,
        }
        for d in rows
    ]


@router.post("", status_code=201)
async def create_destination(body: DestinationCreate, db: AsyncSession = Depends(get_db)) -> dict:
    dest = Destination(
        name=body.name,
        url=body.url,
        platform_key=body.platform_key,
        connector_key=body.connector_key,
        surface=body.surface,
        connection=body.connection,
        frequency_cap=body.frequency_cap,
        self_promo_allowed=body.self_promo_allowed,
        link_policy=body.link_policy,
        disclosure_required=body.disclosure_required,
        automation_allowed=body.automation_allowed,
        audience_tags=body.audience_tags,
        relevance_score=body.relevance_score,
        category=body.category,
    )
    db.add(dest)
    await db.commit()
    await db.refresh(dest)
    return {"id": dest.id, "name": dest.name, "connector_key": dest.connector_key}


@router.post("/{destination_id}/certify")
async def certify_destination(
    destination_id: str,
    db: AsyncSession = Depends(get_db),
    idempotency_key: str | None = None,
) -> JobResponse:
    result = await db.execute(select(Destination).where(Destination.id == destination_id))
    destination = result.scalar_one_or_none()
    if not destination:
        raise HTTPException(status_code=404, detail="Destination not found")

    job = await create_job(db, "certification", {"destination_id": destination_id})

    async def handler(session: AsyncSession, _job) -> dict:
        res = await session.execute(select(Destination).where(Destination.id == destination_id))
        dest = res.scalar_one()
        out = await run_certification(session, dest)
        await session.commit()
        return out

    schedule_job(job.id, handler, OutputManifest(settings={"destination_id": destination_id}))
    return JobResponse(job_id=job.id, status="queued", progress=0)
