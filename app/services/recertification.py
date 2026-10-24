import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.tables import Destination, RecertificationAlert
from app.services.certification import run_certification

logger = logging.getLogger(__name__)


def _age_days(last_certified_at: datetime | None) -> float:
    if not last_certified_at:
        return float("inf")
    now = datetime.now(timezone.utc)
    cert = last_certified_at
    if cert.tzinfo is None:
        cert = cert.replace(tzinfo=timezone.utc)
    return (now - cert).total_seconds() / 86400


async def create_alert(db: AsyncSession, destination_id: str, message: str, severity: str = "critical") -> None:
    db.add(
        RecertificationAlert(
            destination_id=destination_id,
            message=message,
            severity=severity,
            resolved=False,
        )
    )


async def demote_destination(db: AsyncSession, destination: Destination, reason: str) -> None:
    destination.certified = False
    destination.level = "L0"
    destination.publish_enabled = False
    await create_alert(db, destination.id, reason, severity="critical")
    await db.flush()
    logger.warning(
        "destination_demoted",
        extra={"extra_fields": {"destination_id": destination.id, "reason": reason}},
    )


async def run_recertification_cycle(db: AsyncSession) -> dict:
    settings = get_settings()
    max_age = settings.certification_max_age_days
    lead = settings.recert_lead_days

    result = await db.execute(select(Destination).where(Destination.certified == True))  # noqa: E712
    destinations = result.scalars().all()

    summary = {"checked": 0, "recertified": 0, "demoted": 0, "alerts": 0}
    for dest in destinations:
        summary["checked"] += 1
        age = _age_days(dest.last_certified_at)
        if age < max_age - lead:
            continue

        if age >= max_age:
            await demote_destination(db, dest, f"Certification expired ({age:.0f}d > {max_age}d)")
            summary["demoted"] += 1
            summary["alerts"] += 1
            continue

        cert = await run_certification(db, dest)
        if cert.get("status") == "passed":
            summary["recertified"] += 1
        else:
            await demote_destination(db, dest, "Scheduled recertification failed")
            summary["demoted"] += 1
            summary["alerts"] += 1

    await db.commit()
    return summary
