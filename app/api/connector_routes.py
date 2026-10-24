from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.connectors.registry import get_connector, list_connectors
from app.db import get_db
from app.errors import CONNECTOR_DISABLED, ApiError, http_exception_from_api_error
from app.schemas.common import Connection, DestinationRef, Rendition

router = APIRouter(prefix="/connector/v1", tags=["connector-contract"])


class ConnectorMethodBody(BaseModel):
    rendition: Rendition | None = None
    destination: DestinationRef | None = None
    connection: Connection = Field(default_factory=Connection)
    idempotency_key: str | None = None
    platform_post_id: str | None = None
    since: str | None = None


@router.post("/{connector_key}/{method}")
async def invoke_connector_method(
    connector_key: str,
    method: str,
    body: ConnectorMethodBody,
) -> dict[str, Any]:
    settings = get_settings()
    if settings.connector_disabled:
        raise http_exception_from_api_error(
            ApiError(CONNECTOR_DISABLED, "Connector disabled", retryable=False, status_code=503)
        )
    if connector_key not in list_connectors():
        raise HTTPException(status_code=404, detail={"error": {"code": "CONNECTOR_NOT_FOUND", "message": connector_key}})

    connector = get_connector(connector_key)
    rendition = body.rendition or Rendition()
    destination = body.destination or DestinationRef(connector_key=connector_key)
    connection = body.connection

    try:
        if method == "validate":
            return await connector.validate(rendition, destination, connection)
        if method == "publish":
            if not body.idempotency_key:
                raise ApiError("VALIDATION_ERROR", "idempotency_key required", status_code=422)
            return await connector.publish(rendition, destination, connection, body.idempotency_key)
        if method == "get_status":
            if not body.platform_post_id:
                raise ApiError("VALIDATION_ERROR", "platform_post_id required", status_code=422)
            return await connector.get_status(body.platform_post_id, connection)
        if method == "delete":
            if not body.platform_post_id:
                raise ApiError("VALIDATION_ERROR", "platform_post_id required", status_code=422)
            return await connector.delete(body.platform_post_id, connection)
        if method == "fetch_metrics":
            if not body.platform_post_id:
                raise ApiError("VALIDATION_ERROR", "platform_post_id required", status_code=422)
            return await connector.fetch_metrics(body.platform_post_id, connection, body.since)
        if method == "refresh_auth":
            return await connector.refresh_auth(connection)
        if method == "build_assist_pack":
            return await connector.build_assist_pack(rendition, destination)
        raise ApiError("VALIDATION_ERROR", f"Unknown method: {method}", status_code=404)
    except ApiError as exc:
        raise http_exception_from_api_error(exc) from exc
    except NotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
