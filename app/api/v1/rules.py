from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.errors import ApiError, http_exception_from_api_error
from app.models.tables import Destination, RuleProposal
from app.schemas.common import JobResponse, OutputManifest, RuleProposalConfirm
from app.services.jobs import create_job, schedule_job
from app.services.rules_capture import confirm_rule_proposal, propose_rules_for_destination

router = APIRouter(prefix="/destinations", tags=["rules"])


@router.post("/{destination_id}/rules/propose", status_code=202, response_model=JobResponse)
async def propose_rules(destination_id: str, db: AsyncSession = Depends(get_db)) -> JobResponse:
    result = await db.execute(select(Destination).where(Destination.id == destination_id))
    destination = result.scalar_one_or_none()
    if not destination:
        raise HTTPException(status_code=404, detail="Destination not found")

    job = await create_job(db, "rules_propose", {"destination_id": destination_id})

    async def handler(session: AsyncSession, _job) -> dict:
        res = await session.execute(select(Destination).where(Destination.id == destination_id))
        dest = res.scalar_one()
        out = await propose_rules_for_destination(session, dest)
        await session.commit()
        return out

    schedule_job(job.id, handler, OutputManifest(models=[{"provider": "rules-extraction", "name": "mock"}]))
    return JobResponse(job_id=job.id, status="queued", progress=0)


@router.get("/{destination_id}/rules/proposals")
async def list_rule_proposals(destination_id: str, db: AsyncSession = Depends(get_db)) -> list[dict]:
    result = await db.execute(
        select(RuleProposal)
        .where(RuleProposal.destination_id == destination_id)
        .order_by(RuleProposal.created_at.desc())
    )
    rows = result.scalars().all()
    return [
        {
            "id": p.id,
            "status": p.status,
            "proposed_rules": p.proposed_rules,
            "explanation": p.explanation,
            "model_provider": p.model_provider,
            "confirmed_by": p.confirmed_by,
            "confirmed_at": p.confirmed_at.isoformat() if p.confirmed_at else None,
        }
        for p in rows
    ]


@router.post("/{destination_id}/rules/proposals/{proposal_id}/confirm")
async def confirm_rules(
    destination_id: str,
    proposal_id: str,
    body: RuleProposalConfirm,
    db: AsyncSession = Depends(get_db),
) -> dict:
    dest_result = await db.execute(select(Destination).where(Destination.id == destination_id))
    destination = dest_result.scalar_one_or_none()
    if not destination:
        raise HTTPException(status_code=404, detail="Destination not found")

    prop_result = await db.execute(
        select(RuleProposal).where(
            RuleProposal.id == proposal_id,
            RuleProposal.destination_id == destination_id,
        )
    )
    proposal = prop_result.scalar_one_or_none()
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")

    try:
        out = await confirm_rule_proposal(
            db,
            destination,
            proposal,
            confirmed_by=body.confirmed_by,
            accept=body.accept,
        )
        await db.commit()
        return out
    except ApiError as exc:
        raise http_exception_from_api_error(exc) from exc
