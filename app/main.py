import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse

from app.api.connector_routes import router as connector_router
from app.api.v1.router import api_router
from app.config import get_settings
from app.db import init_db
from app.errors import ApiError
from app.logging_config import correlation_id_var, setup_logging
from app.middleware.demo_security import demo_security_middleware
from app.services.platform_bootstrap import ensure_local_platforms_ready
from app.seed import refresh_platform_destination_credentials, seed_destinations
from app.services.scheduler import start_recertification_scheduler, stop_recertification_scheduler


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings = get_settings()
    setup_logging(settings.log_level)
    Path("data").mkdir(exist_ok=True)
    await init_db()
    ensure_local_platforms_ready()
    await seed_destinations()
    await refresh_platform_destination_credentials()
    start_recertification_scheduler()
    yield
    stop_recertification_scheduler()


app = FastAPI(
    title="IncuBrix Long-Tail Distribution",
    version="0.1.0",
    openapi_url="/openapi.json",
    docs_url="/docs",
    lifespan=lifespan,
)

settings = get_settings()
app.include_router(api_router, prefix=settings.api_prefix)
app.include_router(connector_router)


@app.get("/", include_in_schema=False)
async def root():
    """Render health checks hit /; send humans to API docs."""
    return RedirectResponse(url="/docs")


@app.middleware("http")
async def security_middleware(request: Request, call_next):
    return await demo_security_middleware(request, call_next)


@app.middleware("http")
async def correlation_middleware(request: Request, call_next):
    cid = request.headers.get("X-Correlation-Id") or str(uuid.uuid4())
    token = correlation_id_var.set(cid)
    try:
        response = await call_next(request)
        response.headers["X-Correlation-Id"] = cid
        return response
    finally:
        correlation_id_var.reset(token)


@app.exception_handler(ApiError)
async def api_error_handler(_request: Request, exc: ApiError):
    return JSONResponse(status_code=exc.status_code, content=exc.to_body())


@app.exception_handler(RequestValidationError)
async def validation_handler(_request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Request validation failed",
                "retryable": False,
                "details": {"issues": exc.errors()},
            }
        },
    )


@app.exception_handler(Exception)
async def unhandled_handler(_request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": str(exc),
                "retryable": False,
                "details": None,
            }
        },
    )
