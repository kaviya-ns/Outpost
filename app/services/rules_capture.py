import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import ApiError
from app.models.tables import Destination, RuleProposal
from app.services.ai.factory import get_rules_adapter


async def fetch_rules_page_text(rules_url: str) -> str:
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            resp = await client.get(rules_url)
            resp.raise_for_status()
            return resp.text
    except httpx.HTTPError as exc:
        raise ApiError(
            "PLATFORM_UNAVAILABLE",
            f"Could not fetch rules page: {exc}",
            retryable=True,
            status_code=503,
        ) from exc


async def propose_rules_for_destination(db: AsyncSession, destination: Destination) -> dict:
    rules_url = destination.rules_url
    if not rules_url:
        from app.config import get_settings

        rules_url = get_settings().mock_rules_page_url

    page_text = await fetch_rules_page_text(rules_url)
    adapter = get_rules_adapter()
    proposed = await adapter.propose_posting_rules(page_text, destination.name)

    proposal = RuleProposal(
        destination_id=destination.id,
        status="pending",
        proposed_rules={
            "frequency_cap": proposed.get("frequency_cap"),
            "self_promo_allowed": proposed.get("self_promo_allowed"),
            "link_policy": proposed.get("link_policy"),
            "disclosure_required": proposed.get("disclosure_required"),
        },
        explanation=proposed.get("explanation"),
        source_excerpt=page_text[:2000],
        model_provider=adapter.provider_name,
    )
    db.add(proposal)
    destination.pending_rules = proposal.proposed_rules
    await db.flush()
    return {
        "proposal_id": proposal.id,
        "status": proposal.status,
        "proposed_rules": proposal.proposed_rules,
        "explanation": proposal.explanation,
        "model_provider": proposal.model_provider,
    }


async def confirm_rule_proposal(
    db: AsyncSession,
    destination: Destination,
    proposal: RuleProposal,
    *,
    confirmed_by: str,
    accept: bool,
) -> dict:
    from datetime import datetime, timezone

    if proposal.status != "pending":
        raise ApiError("VALIDATION_ERROR", "Proposal is not pending", status_code=409)

    proposal.confirmed_by = confirmed_by
    proposal.confirmed_at = datetime.now(timezone.utc)
    if accept:
        rules = proposal.proposed_rules
        destination.frequency_cap = rules.get("frequency_cap") or destination.frequency_cap
        destination.self_promo_allowed = bool(rules.get("self_promo_allowed", destination.self_promo_allowed))
        destination.link_policy = rules.get("link_policy") or destination.link_policy
        destination.disclosure_required = bool(rules.get("disclosure_required", destination.disclosure_required))
        proposal.status = "confirmed"
        destination.pending_rules = None
    else:
        proposal.status = "rejected"
        destination.pending_rules = None

    await db.flush()
    return {
        "proposal_id": proposal.id,
        "status": proposal.status,
        "destination_id": destination.id,
    }
