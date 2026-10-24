from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.tables import Destination
from app.schemas.common import TailorRequest
from app.services.tailoring import tailor_rendition

router = APIRouter(prefix="/tailor", tags=["tailoring"])


@router.post("")
async def tailor(body: TailorRequest, db: AsyncSession = Depends(get_db)) -> dict:
    result = await db.execute(select(Destination).where(Destination.id == body.destination_id))
    destination = result.scalar_one_or_none()
    if not destination:
        raise HTTPException(status_code=404, detail="Destination not found")
    tailored, warnings = tailor_rendition(destination, body.rendition)
    return {"rendition": tailored.model_dump(), "warnings": warnings}
