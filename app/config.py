from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


from app.database_url import normalize_database_url

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "incubrix-longtail-distribution"
    app_env: str = "development"
    log_level: str = "INFO"
    api_prefix: str = "/api/v1"
    simulation_mode: bool = True
    connector_disabled: bool = False

    host: str = "0.0.0.0"
    port: int = 8000
    public_base_url: str = "http://localhost:8000"

    demo_api_key: str = ""
    rate_limit_per_minute: int = 120

    database_url: str = "sqlite+aiosqlite:///./data/outpost.db"

    @field_validator("database_url", mode="before")
    @classmethod
    def _normalize_db_url(cls, value: str) -> str:
        if isinstance(value, str):
            return normalize_database_url(value)
        return value

    s3_endpoint: str = "http://localhost:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_bucket: str = "outpost"
    s3_public_url: str = "http://localhost:9000/outpost"
    s3_use_ssl: bool = False
    s3_enabled: bool = True

    callback_hmac_secret: str = "change-me-in-production"

    ai_provider: str = "mock"
    openai_api_key: str = ""
    anthropic_api_key: str = ""

    discourse_mock_url: str = "http://localhost:8081"
    devto_mock_url: str = "http://localhost:8082"
    webhook_partner_url: str = "http://localhost:8083"
    lemmy_base_url: str = "http://localhost:8536"
    lemmy_jwt: str = ""
    lemmy_community_id: int = 1
    ghost_url: str = "http://localhost:2368"
    ghost_admin_api_key: str = ""

    cert_test_post_ttl_minutes: int = 10
    certification_max_age_days: int = 30
    recert_lead_days: int = 5
    recert_check_interval_seconds: int = 3600
    recert_scheduler_enabled: bool = True
    tailor_on_publish: bool = True

    manifests_dir: str = "connectors/manifests"
    mock_rules_page_url: str = "http://localhost:8080/rules/community-guidelines.txt"
    evaluation_labelled_path: str = "catalogue/evaluation_labelled.json"


@lru_cache
def get_settings() -> Settings:
    return Settings()
