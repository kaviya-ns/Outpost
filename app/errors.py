from typing import Any

from fastapi import HTTPException
from pydantic import BaseModel


class ErrorBody(BaseModel):
    code: str
    message: str
    retryable: bool
    details: dict[str, Any] | None = None


class ApiError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        retryable: bool = False,
        status_code: int = 400,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.retryable = retryable
        self.status_code = status_code
        self.details = details or {}

    def to_body(self) -> dict[str, Any]:
        return {
            "error": ErrorBody(
                code=self.code,
                message=self.message,
                retryable=self.retryable,
                details=self.details or None,
            ).model_dump()
        }


# Shared connector / platform error codes (Appendix A)
DEST_SPEC_VIOLATION = "DEST_SPEC_VIOLATION"
DEST_RULE_FREQUENCY_CAP = "DEST_RULE_FREQUENCY_CAP"
CONNECTION_AUTH_EXPIRED = "CONNECTION_AUTH_EXPIRED"
PLATFORM_RATE_LIMIT = "PLATFORM_RATE_LIMIT"
PLATFORM_QUOTA_EXHAUSTED = "PLATFORM_QUOTA_EXHAUSTED"
PLATFORM_CONTENT_REJECTED = "PLATFORM_CONTENT_REJECTED"
PLATFORM_UNAVAILABLE = "PLATFORM_UNAVAILABLE"
CONNECTOR_DISABLED = "CONNECTOR_DISABLED"

INTERNAL_ERROR = "INTERNAL_ERROR"
JOB_NOT_FOUND = "JOB_NOT_FOUND"
IDEMPOTENCY_CONFLICT = "IDEMPOTENCY_CONFLICT"
VALIDATION_ERROR = "VALIDATION_ERROR"


def http_exception_from_api_error(exc: ApiError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.to_body())
