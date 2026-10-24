import hashlib
import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import IDEMPOTENCY_CONFLICT, ApiError
from app.models.tables import IdempotencyRecord


def _hash_request(payload: dict) -> str:
    normalized = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(normalized.encode()).hexdigest()


async def lookup_idempotency(
    db: AsyncSession,
    scope: str,
    idempotency_key: str,
    payload: dict,
) -> dict | None:
    req_hash = _hash_request(payload)
    result = await db.execute(
        select(IdempotencyRecord).where(
            IdempotencyRecord.scope == scope,
            IdempotencyRecord.idempotency_key == idempotency_key,
        )
    )
    existing = result.scalar_one_or_none()
    if not existing:
        return None
    if existing.request_hash != req_hash:
        raise ApiError(
            IDEMPOTENCY_CONFLICT,
            "Idempotency-Key reused with different request body",
            status_code=409,
        )
    return existing.response_snapshot


async def get_or_create_idempotency(
    db: AsyncSession,
    scope: str,
    idempotency_key: str,
    payload: dict,
    job_id: str,
) -> tuple[bool, dict | None]:
    """Returns (is_new, existing_response_if_replay)."""
    req_hash = _hash_request(payload)
    result = await db.execute(
        select(IdempotencyRecord).where(
            IdempotencyRecord.scope == scope,
            IdempotencyRecord.idempotency_key == idempotency_key,
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        if existing.request_hash != req_hash:
            raise ApiError(
                IDEMPOTENCY_CONFLICT,
                "Idempotency-Key reused with different request body",
                status_code=409,
            )
        return False, existing.response_snapshot
    record = IdempotencyRecord(
        scope=scope,
        idempotency_key=idempotency_key,
        request_hash=req_hash,
        job_id=job_id,
        response_snapshot={},
    )
    db.add(record)
    await db.flush()
    return True, None


async def store_idempotency_response(
    db: AsyncSession,
    scope: str,
    idempotency_key: str,
    response: dict,
) -> None:
    result = await db.execute(
        select(IdempotencyRecord).where(
            IdempotencyRecord.scope == scope,
            IdempotencyRecord.idempotency_key == idempotency_key,
        )
    )
    record = result.scalar_one_or_none()
    if record:
        record.response_snapshot = response
        await db.flush()
