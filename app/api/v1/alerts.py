from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.tables import RecertificationAlert

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("/recertification")
async def list_recert_alerts(db: AsyncSession = Depends(get_db), unresolved_only: bool = True) -> list[dict]:
    stmt = select(RecertificationAlert).order_by(RecertificationAlert.created_at.desc())
    if unresolved_only:
        stmt = stmt.where(RecertificationAlert.resolved == False)  # noqa: E712
    rows = (await db.execute(stmt)).scalars().all()
    return [
        {
            "id": a.id,
            "destination_id": a.destination_id,
            "severity": a.severity,
            "message": a.message,
            "resolved": a.resolved,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in rows
    ]
