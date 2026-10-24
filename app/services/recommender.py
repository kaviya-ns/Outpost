import json
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.tables import Destination, PostRecord
from app.schemas.common import Rendition

# IncuBrix audience themes (assessment brief)
AUDIENCE_THEMES: dict[str, list[str]] = {
    "ai": ["ai", "artificial intelligence", "machine learning", "llm", "gpt", "agent"],
    "video": ["video", "youtube", "streaming", "creator", "edit", "footage"],
    "marketing": ["marketing", "growth", "campaign", "brand", "audience"],
    "saas": ["saas", "b2b", "startup", "founder", "product", "subscription"],
    "creators": ["creator", "content", "influencer", "community"],
    "founders": ["founder", "startup", "bootstrapped", "vc", "indie"],
}

PLATFORM_AFFINITY: dict[str, list[str]] = {
    "discourse": ["community", "discussion", "forum", "question"],
    "lemmy": ["community", "discussion", "open source"],
    "devto": ["developer", "engineering", "tutorial", "code", "saas", "ai"],
    "ghost": ["article", "blog", "essay", "longform"],
    "webhook_hmac": ["partner", "integration", "b2b"],
    "assisted": ["manual", "policy", "restricted"],
}


async def _past_performance(db: AsyncSession) -> dict[str, dict[str, int]]:
    result = await db.execute(
        select(
            PostRecord.destination_id,
            func.count(PostRecord.id),
        )
        .where(PostRecord.is_test == False)  # noqa: E712
        .group_by(PostRecord.destination_id)
    )
    return {dest_id: {"success_count": count} for dest_id, count in result.all()}


def _text_blob(rendition: Rendition) -> str:
    parts = [rendition.title, rendition.body, " ".join(rendition.hashtags)]
    if rendition.canonical_url:
        parts.append(rendition.canonical_url)
    return " ".join(parts).lower()


def _theme_hits(text: str, tags: list[str]) -> list[str]:
    hits: list[str] = []
    for tag in tags:
        theme_words = AUDIENCE_THEMES.get(tag.lower(), [tag.lower()])
        if any(w in text for w in theme_words):
            hits.append(tag)
    return hits


def score_destination(
    destination: Destination,
    rendition: Rendition,
    past: dict[str, int],
) -> tuple[float, str]:
    text = _text_blob(rendition)
    reasons: list[str] = []
    score = 0.0

    if destination.relevance_score:
        score += destination.relevance_score * 10
        reasons.append(f"catalogue relevance {destination.relevance_score}/5")

    dest_tags = [t.lower() for t in (destination.audience_tags or [])]
    if not dest_tags and destination.category:
        dest_tags = [destination.category.lower()]

    theme_overlap = _theme_hits(text, dest_tags)
    if theme_overlap:
        score += len(theme_overlap) * 8
        reasons.append(f"audience match: {', '.join(theme_overlap)}")

    for theme, keywords in AUDIENCE_THEMES.items():
        if any(k in text for k in keywords) and theme in dest_tags:
            score += 4

    platform_terms = PLATFORM_AFFINITY.get(destination.connector_key, [])
    if any(p in text for p in platform_terms):
        score += 5
        reasons.append(f"platform fit ({destination.connector_key})")

    if destination.certified:
        score += 8
        reasons.append("certified (L3+)")
    if destination.publish_enabled:
        score += 4
    else:
        score -= 100
        reasons.append("excluded: demoted/disabled")

    if rendition.is_promotional and not destination.self_promo_allowed:
        score -= 40
        reasons.append("blocked: self-promo not allowed")
    if rendition.is_ai_generated and destination.disclosure_required:
        if "ai" not in text and "generated" not in text:
            score -= 15
            reasons.append("needs AI disclosure in copy")
    if not destination.automation_allowed and destination.connector_key != "assisted":
        score -= 25
        reasons.append("automation not allowed")

    if rendition.content_type == "video_link" and destination.connector_key in ("devto", "ghost", "discourse"):
        score += 3

    past_count = past.get("success_count", 0)
    if past_count:
        boost = min(past_count * 2, 12)
        score += boost
        reasons.append(f"past publishes: {past_count}")

    if not reasons:
        reasons.append("baseline catalogue entry")

    return score, "; ".join(reasons)


async def recommend_destinations(
    db: AsyncSession,
    rendition: Rendition,
    *,
    limit: int = 20,
    certified_only: bool = False,
) -> list[dict[str, Any]]:
    result = await db.execute(select(Destination))
    destinations = result.scalars().all()
    past_map = await _past_performance(db)

    ranked: list[dict[str, Any]] = []
    for dest in destinations:
        if certified_only and not dest.certified:
            continue
        score, reason = score_destination(dest, rendition, past_map.get(dest.id, {}))
        ranked.append(
            {
                "destination_id": dest.id,
                "name": dest.name,
                "connector_key": dest.connector_key,
                "platform_key": dest.platform_key,
                "score": round(score, 2),
                "reason": reason,
                "certified": dest.certified,
                "publish_enabled": dest.publish_enabled,
            }
        )

    ranked.sort(key=lambda x: x["score"], reverse=True)
    return ranked[:limit]


def precision_at_k(recommended_ids: list[str], relevant_ids: set[str], k: int = 10) -> float:
    top = recommended_ids[:k]
    if not top:
        return 0.0
    hits = sum(1 for d in top if d in relevant_ids)
    return hits / k


def load_labelled_set(path: Path | None = None) -> list[dict[str, Any]]:
    settings = get_settings()
    file_path = path or Path(settings.evaluation_labelled_path)
    if not file_path.is_absolute():
        file_path = Path(__file__).resolve().parents[2] / file_path
    data = json.loads(file_path.read_text(encoding="utf-8"))
    return data.get("items", data)


async def evaluate_labelled_set(
    db: AsyncSession,
    items: list[dict[str, Any]],
    *,
    k: int = 10,
) -> dict[str, Any]:
    by_connector: dict[str, Destination] = {}
    by_name: dict[str, Destination] = {}
    result = await db.execute(select(Destination))
    for dest in result.scalars().all():
        by_connector[dest.connector_key] = dest
        by_name[dest.name.lower()] = dest

    per_item: list[dict[str, Any]] = []
    precisions: list[float] = []

    for item in items:
        rendition = Rendition(**item["rendition"])
        ranked = await recommend_destinations(db, rendition, limit=k)
        recommended_ids = [r["destination_id"] for r in ranked]

        relevant_ids: set[str] = set()
        for key in item.get("relevant_destination_ids", []):
            relevant_ids.add(key)
        for key in item.get("relevant_connector_keys", []):
            if key in by_connector:
                relevant_ids.add(by_connector[key].id)
        for name in item.get("relevant_destination_names", []):
            if name.lower() in by_name:
                relevant_ids.add(by_name[name.lower()].id)

        p = precision_at_k(recommended_ids, relevant_ids, k=k)
        precisions.append(p)
        per_item.append(
            {
                "item_id": item.get("id"),
                "precision_at_10": round(p, 4),
                "relevant_count": len(relevant_ids),
                "top_recommendations": ranked,
            }
        )

    macro = sum(precisions) / len(precisions) if precisions else 0.0
    return {
        "k": k,
        "items_evaluated": len(per_item),
        "precision_at_10_macro": round(macro, 4),
        "per_item": per_item,
    }
