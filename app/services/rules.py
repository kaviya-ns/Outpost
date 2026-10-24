from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tables import Destination, PostRecord, RuleViolationLog


class RuleCheckResult:
    def __init__(self, ok: bool, violations: list[dict], blocked: bool = True) -> None:
        self.ok = ok
        self.violations = violations
        self.blocked = blocked


async def check_posting_rules(
    db: AsyncSession,
    destination: Destination,
    rendition: dict,
) -> RuleCheckResult:
    violations: list[dict] = []

    cap = destination.frequency_cap or {"count": 1, "window_days": 7}
    count = int(cap.get("count", 1))
    window_days = int(cap.get("window_days", 7))
    since = datetime.now(timezone.utc) - timedelta(days=window_days)
    result = await db.execute(
        select(func.count(PostRecord.id)).where(
            PostRecord.destination_id == destination.id,
            PostRecord.is_test == False,  # noqa: E712
            PostRecord.created_at >= since,
        )
    )
    recent = result.scalar() or 0
    if recent >= count:
        violations.append(
            {
                "code": "DEST_RULE_FREQUENCY_CAP",
                "field": "frequency",
                "message": f"Frequency cap {count} per {window_days}d reached",
                "retryable": True,
            }
        )

    if rendition.get("is_promotional") and not destination.self_promo_allowed:
        violations.append(
            {
                "code": "DEST_RULE_SELF_PROMO",
                "field": "is_promotional",
                "message": "Self-promotion not allowed at this destination",
                "retryable": False,
            }
        )

    link_policy = destination.link_policy or "allowed"
    has_link = bool(rendition.get("canonical_url")) or "http://" in rendition.get("body", "") or "https://" in rendition.get(
        "body", ""
    )
    if has_link and link_policy == "forbidden":
        violations.append(
            {
                "code": "DEST_RULE_LINK_POLICY",
                "field": "body",
                "message": "Links are not allowed",
                "retryable": False,
            }
        )

    if rendition.get("is_ai_generated") and destination.disclosure_required:
        body = rendition.get("body", "")
        if "ai" not in body.lower() and "generated" not in body.lower():
            violations.append(
                {
                    "code": "DEST_RULE_AI_DISCLOSURE",
                    "field": "body",
                    "message": "AI-generated content requires disclosure in body text",
                    "retryable": False,
                }
            )

    if not destination.automation_allowed and destination.connector_key != "assisted":
        violations.append(
            {
                "code": "DEST_RULE_AUTOMATION",
                "field": "automation",
                "message": "Automation not allowed; use assisted connector",
                "retryable": False,
            }
        )

    ok = len(violations) == 0
    for v in violations:
        db.add(
            RuleViolationLog(
                destination_id=destination.id,
                violation_type=v["code"],
                message=v["message"],
                blocked=ok is False,
            )
        )
    await db.flush()
    return RuleCheckResult(ok=ok, violations=violations, blocked=not ok)
