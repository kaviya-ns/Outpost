from abc import ABC, abstractmethod
from typing import Any

from app.schemas.common import Connection, DestinationRef, Rendition


class ConnectorBase(ABC):
    key: str = ""

    @abstractmethod
    async def validate(
        self, rendition: Rendition, destination: DestinationRef, connection: Connection
    ) -> dict[str, Any]:
        ...

    @abstractmethod
    async def publish(
        self,
        rendition: Rendition,
        destination: DestinationRef,
        connection: Connection,
        idempotency_key: str,
    ) -> dict[str, Any]:
        ...

    @abstractmethod
    async def get_status(self, platform_post_id: str, connection: Connection) -> dict[str, Any]:
        ...

    @abstractmethod
    async def delete(self, platform_post_id: str, connection: Connection) -> dict[str, Any]:
        ...

    async def fetch_metrics(
        self, platform_post_id: str, connection: Connection, since: str | None = None
    ) -> dict[str, Any]:
        return {
            "views": 0,
            "likes": 0,
            "comments": 0,
            "shares": 0,
            "saves": 0,
            "watch_time_s": 0,
            "clicks": 0,
        }

    async def refresh_auth(self, connection: Connection) -> dict[str, Any]:
        return {"expires_at": None}

    async def build_assist_pack(self, rendition: Rendition, destination: DestinationRef) -> dict[str, Any]:
        raise NotImplementedError("build_assist_pack only on assisted connector")

    def map_platform_error(self, status_code: int | str, message: str = "") -> dict[str, Any]:
        from app.services.manifest_loader import manifest_loader

        manifest = manifest_loader.get(self.key) or {}
        error_map = manifest.get("error_map", {})
        code = error_map.get(str(status_code), "PLATFORM_UNAVAILABLE")
        retryable = code in ("PLATFORM_RATE_LIMIT", "PLATFORM_UNAVAILABLE", "PLATFORM_QUOTA_EXHAUSTED")
        return {"code": code, "message": message or str(status_code), "retryable": retryable}
