from fastapi import APIRouter

from app.config import get_settings

router = APIRouter(tags=["demo"])


@router.get("/demo-info")
async def demo_info() -> dict:
    settings = get_settings()
    return {
        "service": settings.app_name,
        "public_base_url": settings.public_base_url,
        "demo_auth_required": bool(settings.demo_api_key),
        "rate_limit_per_minute": settings.rate_limit_per_minute,
        "docs_url": f"{settings.public_base_url.rstrip('/')}/docs",
        "hint": "Use header X-Demo-Token when demo_auth_required is true",
    }
