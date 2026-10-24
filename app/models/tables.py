import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    type: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(16), default="queued", index=True)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    manifest: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    callback_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"
    __table_args__ = (UniqueConstraint("scope", "idempotency_key", name="uq_idempotency_scope_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    scope: Mapped[str] = mapped_column(String(128), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(256), index=True)
    request_hash: Mapped[str] = mapped_column(String(64))
    job_id: Mapped[str] = mapped_column(String(36), index=True)
    response_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class Destination(Base):
    __tablename__ = "destinations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(256))
    url: Mapped[str] = mapped_column(String(512))
    platform_key: Mapped[str] = mapped_column(String(64), index=True)
    surface: Mapped[str] = mapped_column(String(64), default="default")
    category: Mapped[str | None] = mapped_column(String(128), nullable=True)
    audience_tags: Mapped[list] = mapped_column(JSON, default=list)
    language: Mapped[str] = mapped_column(String(16), default="en")
    geo: Mapped[str | None] = mapped_column(String(64), nullable=True)
    est_audience: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rules_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    frequency_cap: Mapped[dict] = mapped_column(JSON, default=lambda: {"count": 1, "window_days": 7})
    self_promo_allowed: Mapped[bool] = mapped_column(default=True)
    link_policy: Mapped[str] = mapped_column(String(32), default="allowed")
    disclosure_required: Mapped[bool] = mapped_column(default=False)
    automation_allowed: Mapped[bool] = mapped_column(default=True)
    connector_key: Mapped[str] = mapped_column(String(64), index=True)
    connection: Mapped[dict] = mapped_column(JSON, default=dict)
    relevance_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    relevance_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    level: Mapped[str] = mapped_column(String(8), default="L0")
    last_certified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    certified: Mapped[bool] = mapped_column(default=False)
    publish_enabled: Mapped[bool] = mapped_column(default=True)
    pending_rules: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class PostRecord(Base):
    __tablename__ = "post_records"
    __table_args__ = (UniqueConstraint("idempotency_key", name="uq_post_idempotency"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    destination_id: Mapped[str] = mapped_column(String(36), index=True)
    connector_key: Mapped[str] = mapped_column(String(64))
    platform_post_id: Mapped[str] = mapped_column(String(256), index=True)
    live_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="published")
    idempotency_key: Mapped[str] = mapped_column(String(256))
    is_test: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class RuleViolationLog(Base):
    __tablename__ = "rule_violation_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    destination_id: Mapped[str] = mapped_column(String(36), index=True)
    violation_type: Mapped[str] = mapped_column(String(64))
    message: Mapped[str] = mapped_column(Text)
    blocked: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class RuleProposal(Base):
    __tablename__ = "rule_proposals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    destination_id: Mapped[str] = mapped_column(String(36), index=True)
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    proposed_rules: Mapped[dict] = mapped_column(JSON, default=dict)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    confirmed_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RecertificationAlert(Base):
    __tablename__ = "recertification_alerts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    destination_id: Mapped[str] = mapped_column(String(36), index=True)
    severity: Mapped[str] = mapped_column(String(16), default="warning")
    message: Mapped[str] = mapped_column(Text)
    resolved: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class CertificationRun(Base):
    __tablename__ = "certification_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    destination_id: Mapped[str] = mapped_column(String(36), index=True)
    connector_key: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32))
    evidence: Mapped[dict] = mapped_column(JSON, default=dict)
    duration_s: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
