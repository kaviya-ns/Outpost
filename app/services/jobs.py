import asyncio
import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.errors import ApiError
from app.logging_config import job_id_var
from app.models.tables import Job
from app.schemas.common import OutputManifest

logger = logging.getLogger(__name__)


async def create_job(
    db: AsyncSession,
    job_type: str,
    payload: dict[str, Any],
    *,
    correlation_id: str | None = None,
    callback_url: str | None = None,
) -> Job:
    job = Job(
        type=job_type,
        status="queued",
        progress=0,
        payload=payload,
        callback_url=callback_url,
        correlation_id=correlation_id,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


async def get_job(db: AsyncSession, job_id: str) -> Job | None:
    result = await db.execute(select(Job).where(Job.id == job_id))
    return result.scalar_one_or_none()


async def update_job(
    db: AsyncSession,
    job: Job,
    *,
    status: str | None = None,
    progress: int | None = None,
    result: dict | None = None,
    error: dict | None = None,
    manifest: dict | None = None,
) -> Job:
    if status is not None:
        job.status = status
    if progress is not None:
        job.progress = progress
    if result is not None:
        job.result = result
    if error is not None:
        job.error = error
    if manifest is not None:
        job.manifest = manifest
    job.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(job)
    return job


def _sign_callback(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


async def _send_callback(job: Job) -> None:
    if not job.callback_url:
        return
    settings = get_settings()
    payload = {
        "job_id": job.id,
        "status": job.status,
        "progress": job.progress,
        "result": job.result,
        "error": job.error,
    }
    body = json.dumps(payload).encode()
    headers = {"Content-Type": "application/json"}
    sig = _sign_callback(body, settings.callback_hmac_secret)
    headers["X-IncuBrix-Signature"] = sig
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            await client.post(job.callback_url, content=body, headers=headers)
    except Exception:
        logger.exception("callback_failed", extra={"extra_fields": {"job_id": job.id}})


async def run_job_in_background(
    job_id: str,
    handler: Callable[[AsyncSession, Job], Awaitable[dict[str, Any]]],
    manifest: OutputManifest | None = None,
) -> None:
    from app.db import SessionLocal

    token = job_id_var.set(job_id)
    try:
        async with SessionLocal() as db:
            job = await get_job(db, job_id)
            if not job:
                return
            await update_job(db, job, status="running", progress=5)
            try:
                result = await handler(db, job)
                man = manifest or OutputManifest()
                man.timings_ms["total"] = man.timings_ms.get("total", 0)
                await update_job(
                    db,
                    job,
                    status="succeeded",
                    progress=100,
                    result=result,
                    manifest=man.model_dump(),
                )
            except ApiError as exc:
                err = {
                    "code": exc.code,
                    "message": exc.message,
                    "retryable": exc.retryable,
                    "details": exc.details,
                }
                await update_job(db, job, status="failed", progress=100, error=err)
            except Exception as exc:
                err = {"code": "JOB_FAILED", "message": str(exc), "retryable": False}
                await update_job(db, job, status="failed", progress=100, error=err)
            job = await get_job(db, job_id)
            if job:
                await _send_callback(job)
    finally:
        job_id_var.reset(token)


def schedule_job(
    job_id: str,
    handler: Callable[[AsyncSession, Job], Awaitable[dict[str, Any]]],
    manifest: OutputManifest | None = None,
) -> None:
    asyncio.create_task(run_job_in_background(job_id, handler, manifest))
