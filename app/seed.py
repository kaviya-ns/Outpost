from sqlalchemy import select

from app.config import get_settings
from app.models.tables import Destination


async def seed_destinations(force: bool = False) -> None:
    from app.db import SessionLocal

    settings = get_settings()
    async with SessionLocal() as db:
        if not force:
            existing = await db.execute(select(Destination).limit(1))
            if existing.scalar_one_or_none():
                return

        defaults = [
            {
                "name": "Mock Discourse Forum",
                "url": f"{settings.discourse_mock_url}",
                "platform_key": "discourse",
                "connector_key": "discourse",
                "audience_tags": ["creators", "ai", "marketing", "founders"],
                "relevance_score": 4,
                "category": "community",
                "connection": {
                    "instance_params": {"base_url": settings.discourse_mock_url},
                    "connection": {
                        "credentials": {
                            "base_url": settings.discourse_mock_url,
                            "api_key": "test-key",
                            "username": "system",
                        }
                    },
                },
            },
            {
                "name": "Local Lemmy",
                "url": settings.lemmy_base_url,
                "platform_key": "lemmy",
                "connector_key": "lemmy",
                "audience_tags": ["creators", "founders"],
                "relevance_score": 4,
                "category": "community",
                "connection": {
                    "instance_params": {
                        "base_url": settings.lemmy_base_url,
                        "community_id": settings.lemmy_community_id,
                    },
                    "connection": {
                        "credentials": {
                            "base_url": settings.lemmy_base_url,
                            "jwt": settings.lemmy_jwt,
                        }
                    },
                },
            },
            {
                "name": "Mock Dev.to",
                "url": settings.devto_mock_url,
                "platform_key": "devto",
                "connector_key": "devto",
                "audience_tags": ["ai", "saas", "founders"],
                "relevance_score": 5,
                "category": "engineering",
                "connection": {
                    "connection": {
                        "credentials": {"base_url": settings.devto_mock_url, "api_key": "devto-test"}
                    }
                },
            },
            {
                "name": "Local Ghost",
                "url": settings.ghost_url,
                "platform_key": "ghost",
                "connector_key": "ghost",
                "audience_tags": ["saas", "marketing", "founders"],
                "relevance_score": 4,
                "category": "blog",
                "connection": {
                    "instance_params": {"base_url": settings.ghost_url},
                    "connection": {
                        "credentials": {
                            "base_url": settings.ghost_url,
                            "admin_api_key": settings.ghost_admin_api_key,
                        }
                    },
                },
            },
            {
                "name": "Partner Webhook",
                "url": settings.webhook_partner_url,
                "platform_key": "partner",
                "connector_key": "webhook_hmac",
                "audience_tags": ["marketing", "saas"],
                "relevance_score": 4,
                "category": "partner",
                "connection": {
                    "instance_params": {"webhook_url": settings.webhook_partner_url},
                    "connection": {
                        "credentials": {
                            "webhook_url": settings.webhook_partner_url,
                            "hmac_secret": "partner-secret",
                        }
                    },
                },
            },
            {
                "name": "Manual Community (Assisted)",
                "url": "https://example.com/r/example",
                "platform_key": "manual",
                "connector_key": "assisted",
                "audience_tags": ["creators"],
                "relevance_score": 3,
                "automation_allowed": False,
                "connection": {"instance_params": {"submit_url": "https://example.com/submit"}},
            },
        ]

        for row in defaults:
            dest = Destination(
                name=row["name"],
                url=row["url"],
                platform_key=row["platform_key"],
                connector_key=row["connector_key"],
                connection=row.get("connection", {}),
                automation_allowed=row.get("automation_allowed", True),
                self_promo_allowed=row.get("self_promo_allowed", True),
                disclosure_required=row.get("disclosure_required", False),
                audience_tags=row.get("audience_tags", []),
                relevance_score=row.get("relevance_score"),
                category=row.get("category"),
            )
            db.add(dest)
        await db.commit()


async def refresh_platform_destination_credentials() -> None:
    """Update Lemmy/Ghost destination credentials after platform bootstrap (existing DB)."""
    from app.db import SessionLocal

    settings = get_settings()
    if not settings.lemmy_jwt and not settings.ghost_admin_api_key:
        return
    async with SessionLocal() as db:
        result = await db.execute(select(Destination))
        for dest in result.scalars().all():
            if dest.connector_key == "lemmy" and settings.lemmy_jwt:
                conn = dict(dest.connection or {})
                inst = dict(conn.get("instance_params") or {})
                inst["base_url"] = settings.lemmy_base_url
                inst["community_id"] = settings.lemmy_community_id
                cred = dict((conn.get("connection") or {}).get("credentials") or {})
                cred["base_url"] = settings.lemmy_base_url
                cred["jwt"] = settings.lemmy_jwt
                conn["instance_params"] = inst
                conn["connection"] = {"credentials": cred}
                dest.connection = conn
            if dest.connector_key == "ghost" and settings.ghost_admin_api_key:
                conn = dict(dest.connection or {})
                inst = dict(conn.get("instance_params") or {})
                inst["base_url"] = settings.ghost_url
                cred = dict((conn.get("connection") or {}).get("credentials") or {})
                cred["base_url"] = settings.ghost_url
                cred["admin_api_key"] = settings.ghost_admin_api_key
                conn["instance_params"] = inst
                conn["connection"] = {"credentials": cred}
                dest.connection = conn
        await db.commit()
