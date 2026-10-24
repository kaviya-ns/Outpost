from fastapi import APIRouter

from app.api.v1 import alerts, catalogue, demo_info, destinations, health, jobs, metrics, publish, recommend, rules, tailoring

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(demo_info.router)
api_router.include_router(jobs.router)
api_router.include_router(destinations.router)
api_router.include_router(rules.router)
api_router.include_router(publish.router)
api_router.include_router(catalogue.router)
api_router.include_router(tailoring.router)
api_router.include_router(metrics.router)
api_router.include_router(alerts.router)
api_router.include_router(recommend.router)
