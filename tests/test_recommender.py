import pytest

from app.schemas.common import Rendition
from app.services.recommender import evaluate_labelled_set, precision_at_k, recommend_destinations


async def _seed_recommendation_catalogue(client):
    """Destinations tuned for evaluation labels (connector keys match seeded + extras)."""
    extras = [
        {
            "name": "AI SaaS Blog",
            "url": "https://blog.example.com",
            "platform_key": "ghost",
            "connector_key": "ghost",
            "audience_tags": ["ai", "saas", "founders"],
            "relevance_score": 5,
            "category": "saas",
        },
        {
            "name": "Dev Community Hub",
            "url": "https://dev.example.com",
            "platform_key": "devto",
            "connector_key": "devto",
            "audience_tags": ["ai", "saas"],
            "relevance_score": 5,
        },
        {
            "name": "Creator Video Forum",
            "url": "https://forum.video.example",
            "platform_key": "discourse",
            "connector_key": "discourse",
            "audience_tags": ["video", "creators"],
            "relevance_score": 4,
        },
        {
            "name": "Promo Allowed Partner",
            "url": "https://partner.example/hook",
            "platform_key": "partner",
            "connector_key": "webhook_hmac",
            "audience_tags": ["marketing", "saas"],
            "relevance_score": 4,
            "self_promo_allowed": True,
        },
        {
            "name": "No Promo Lemmy",
            "url": "https://lemmy.example",
            "platform_key": "lemmy",
            "connector_key": "lemmy",
            "audience_tags": ["creators", "founders"],
            "relevance_score": 4,
            "self_promo_allowed": False,
        },
        {
            "name": "Manual Only Club",
            "url": "https://manual.example",
            "platform_key": "manual",
            "connector_key": "assisted",
            "audience_tags": ["creators"],
            "relevance_score": 3,
            "automation_allowed": False,
        },
    ]
    for row in extras:
        payload = {
            "name": row["name"],
            "url": row["url"],
            "platform_key": row["platform_key"],
            "connector_key": row["connector_key"],
            "self_promo_allowed": row.get("self_promo_allowed", True),
            "automation_allowed": row.get("automation_allowed", True),
            "audience_tags": row.get("audience_tags", []),
            "relevance_score": row.get("relevance_score"),
            "category": row.get("category"),
            "connection": {},
        }
        # extend via raw SQL-free approach: POST then patch fields via certify not needed
        r = await client.post("/api/v1/destinations", json=payload)
        assert r.status_code == 201


@pytest.mark.asyncio
async def test_precision_at_k_helper():
    assert precision_at_k(["a", "b", "c"], {"a", "x"}, k=3) == pytest.approx(1 / 3)
    assert precision_at_k(["a", "b"], {"a", "b"}, k=2) == 1.0


@pytest.mark.asyncio
async def test_recommend_api_ranks_ai_content(client):
    await _seed_recommendation_catalogue(client)
    resp = await client.post(
        "/api/v1/recommend",
        json={
            "rendition": {
                "title": "Shipping AI in our SaaS product",
                "body": "Founder notes on B2B machine learning features.",
                "hashtags": ["ai", "saas"],
            },
            "limit": 5,
        },
    )
    assert resp.status_code == 200
    recs = resp.json()["recommendations"]
    assert len(recs) >= 1
    assert recs[0]["score"] >= recs[-1]["score"]
    top_keys = {r["connector_key"] for r in recs[:3]}
    assert "devto" in top_keys or "ghost" in top_keys


@pytest.mark.asyncio
async def test_evaluate_labelled_set_in_process(client):
    from app.db import SessionLocal

    await _seed_recommendation_catalogue(client)
    labelled = {
        "items": [
            {
                "id": "t1",
                "rendition": {
                    "title": "AI SaaS engineering post",
                    "body": "machine learning for founders",
                    "hashtags": ["ai", "saas"],
                },
                "relevant_connector_keys": ["devto", "ghost"],
            },
            {
                "id": "t2",
                "rendition": {
                    "title": "creator video community question",
                    "body": "youtube creators streaming workflow",
                    "hashtags": ["video", "creators"],
                },
                "relevant_connector_keys": ["discourse", "lemmy"],
            },
        ]
    }
    async with SessionLocal() as db:
        report = await evaluate_labelled_set(db, labelled["items"], k=10)
    assert report["items_evaluated"] == 2
    assert report["precision_at_10_macro"] >= 0.2


@pytest.mark.asyncio
async def test_evaluate_endpoint_default_set(client):
    # Seed must include connector keys referenced in catalogue/evaluation_labelled.json
    from sqlalchemy import select

    from app.db import SessionLocal
    from app.models.tables import Destination

    tag_map = {
        "discourse": ["creators", "ai", "marketing"],
        "lemmy": ["creators", "founders"],
        "devto": ["ai", "saas"],
        "ghost": ["saas", "founders", "marketing"],
        "webhook_hmac": ["marketing", "saas"],
        "assisted": ["creators"],
    }
    async with SessionLocal() as db:
        result = await db.execute(select(Destination))
        for dest in result.scalars().all():
            if dest.connector_key in tag_map:
                dest.audience_tags = tag_map[dest.connector_key]
                dest.relevance_score = 4
                if dest.connector_key == "assisted":
                    dest.automation_allowed = False
        await db.commit()

    resp = await client.post(
        "/api/v1/recommend/evaluate",
        json={"k": 10, "use_default_labelled_set": True},
    )
    assert resp.status_code == 200
    macro = resp.json()["precision_at_10_macro"]
    assert macro >= 0.2
