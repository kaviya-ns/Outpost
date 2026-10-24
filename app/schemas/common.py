from typing import Any, Literal

from pydantic import BaseModel, Field


class Rendition(BaseModel):
    title: str = ""
    body: str = ""
    content_type: Literal["text", "image", "video_link"] = "text"
    media_urls: list[str] = Field(default_factory=list)
    canonical_url: str | None = None
    is_ai_generated: bool = False
    is_promotional: bool = False
    hashtags: list[str] = Field(default_factory=list)


class DestinationRef(BaseModel):
    id: str | None = None
    name: str = ""
    url: str = ""
    platform_key: str = ""
    surface: str = "default"
    connector_key: str = ""
    instance_params: dict[str, Any] = Field(default_factory=dict)
    rules: dict[str, Any] = Field(default_factory=dict)


class Connection(BaseModel):
    auth_type: str = "api_key"
    credentials: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class OutputManifest(BaseModel):
    service: str = "incubrix-longtail-distribution"
    version: str = "0.1.0"
    models: list[dict[str, Any]] = Field(default_factory=list)
    settings: dict[str, Any] = Field(default_factory=dict)
    seed: int | None = None
    timings_ms: dict[str, float] = Field(default_factory=dict)
    cost_estimate_usd: float = 0.0
    warnings: list[str] = Field(default_factory=list)
    licence_rights: dict[str, Any] = Field(default_factory=dict)
    ai_generated_labels: list[str] = Field(default_factory=list)


class JobResponse(BaseModel):
    job_id: str
    status: Literal["queued", "running", "succeeded", "failed"]
    progress: int = 0
    result: dict[str, Any] | None = None
    result_links: list[str] = Field(default_factory=list)
    error: dict[str, Any] | None = None
    manifest: dict[str, Any] | None = None


class PublishRequest(BaseModel):
    rendition: Rendition
    destination_id: str
    connection: Connection | None = None
    idempotency_key: str | None = None
    is_test: bool = False
    callback_url: str | None = None
    tailor: bool | None = None


class TailorRequest(BaseModel):
    rendition: Rendition
    destination_id: str


class MetricsFetchRequest(BaseModel):
    destination_id: str
    platform_post_id: str
    since: str | None = None


class RuleProposalConfirm(BaseModel):
    confirmed_by: str = "reviewer"
    accept: bool = True


class ValidateRequest(BaseModel):
    rendition: Rendition
    destination_id: str
    connection: Connection | None = None


class RecommendRequest(BaseModel):
    rendition: Rendition
    limit: int = 20
    certified_only: bool = False
