import time
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.registry import get_connector
from app.models.tables import CertificationRun, Destination
from app.schemas.common import Connection, DestinationRef, Rendition


async def run_certification(db: AsyncSession, destination: Destination) -> dict[str, Any]:
    started = time.perf_counter()
    connector = get_connector(destination.connector_key)
    dest_ref = DestinationRef(
        id=destination.id,
        name=destination.name,
        url=destination.url,
        platform_key=destination.platform_key,
        surface=destination.surface,
        connector_key=destination.connector_key,
        instance_params=destination.connection.get("instance_params", {}),
        rules={
            "disclosure_required": destination.disclosure_required,
            "self_promo_allowed": destination.self_promo_allowed,
        },
    )
    conn = Connection(**destination.connection.get("connection", {}))
    if not conn.credentials and destination.connection:
        conn.credentials = {k: v for k, v in destination.connection.items() if k not in ("instance_params", "connection")}

    test_rendition = Rendition(
        title="[CERT] IncuBrix connector test",
        body="Automated certification post — safe to delete. #cert-test",
        content_type="text",
        is_ai_generated=destination.disclosure_required,
    )
    idem = f"cert-{destination.id}-{int(time.time())}"

    evidence: dict[str, Any] = {"steps": []}
    try:
        validation = await connector.validate(test_rendition, dest_ref, conn)
        evidence["steps"].append({"step": "validate", "result": validation})

        publish_result = await connector.publish(test_rendition, dest_ref, conn, idem)
        evidence["steps"].append({"step": "publish", "result": publish_result})
        post_id = publish_result["platform_post_id"]

        status_result = await connector.get_status(post_id, conn)
        evidence["steps"].append({"step": "get_status", "result": status_result})

        delete_result = await connector.delete(post_id, conn)
        evidence["steps"].append({"step": "delete", "result": delete_result})

        duration = time.perf_counter() - started
        destination.last_certified_at = datetime.now(timezone.utc)
        destination.certified = True
        destination.level = "L3"
        run = CertificationRun(
            destination_id=destination.id,
            connector_key=destination.connector_key,
            status="passed",
            evidence=evidence,
            duration_s=duration,
        )
        db.add(run)
        await db.flush()
        return {
            "status": "passed",
            "duration_s": duration,
            "certification_run_id": run.id,
            "evidence": evidence,
        }
    except Exception as exc:
        duration = time.perf_counter() - started
        evidence["error"] = str(exc)
        run = CertificationRun(
            destination_id=destination.id,
            connector_key=destination.connector_key,
            status="failed",
            evidence=evidence,
            duration_s=duration,
        )
        db.add(run)
        destination.certified = False
        destination.level = "L0"
        await db.flush()
        return {
            "status": "failed",
            "duration_s": duration,
            "certification_run_id": run.id,
            "evidence": evidence,
        }
