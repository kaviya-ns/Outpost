import io
import logging
from typing import Any
from uuid import uuid4

from minio import Minio
from minio.error import S3Error

from app.config import get_settings

logger = logging.getLogger(__name__)


class StorageService:
    def __init__(self) -> None:
        settings = get_settings()
        self._settings = settings
        self._client: Minio | None = None

    def _get_client(self) -> Minio:
        if self._client is None:
            s = self._settings
            self._client = Minio(
                s.s3_endpoint.replace("http://", "").replace("https://", ""),
                access_key=s.s3_access_key,
                secret_key=s.s3_secret_key,
                secure=s.s3_use_ssl,
            )
        return self._client

    def ensure_bucket(self) -> None:
        try:
            client = self._get_client()
            if not client.bucket_exists(self._settings.s3_bucket):
                client.make_bucket(self._settings.s3_bucket)
        except S3Error:
            logger.warning("minio_bucket_setup_skipped")

    def put_bytes(self, data: bytes, content_type: str = "application/octet-stream", prefix: str = "outputs") -> str:
        settings = get_settings()
        key = f"{prefix}/{uuid4().hex}"
        if not settings.s3_enabled:
            return f"{settings.public_base_url}/api/v1/files/local/{key}"
        try:
            client = self._get_client()
            self.ensure_bucket()
            client.put_object(
                settings.s3_bucket,
                key,
                io.BytesIO(data),
                length=len(data),
                content_type=content_type,
            )
            return f"{settings.s3_public_url.rstrip('/')}/{key}"
        except Exception:
            logger.warning("minio_unavailable_using_local_ref")
            return f"{settings.public_base_url}/api/v1/files/local/{key}"

    async def fetch_url_to_storage(self, url: str) -> str:
        import httpx

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            ct = resp.headers.get("content-type", "application/octet-stream")
            return self.put_bytes(resp.content, content_type=ct, prefix="inputs")


storage_service = StorageService()
