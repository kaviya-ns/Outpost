import csv
import io
import re
import time
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.registry import list_connectors
from app.models.tables import Destination

_URL_RE = re.compile(r"^https?://", re.I)


def _normalize_url(url: str) -> str:
    parsed = urlparse(url.strip().lower())
    host = parsed.netloc.replace("www.", "")
    path = parsed.path.rstrip("/")
    return f"{parsed.scheme}://{host}{path}"


async def import_catalogue_csv(db: AsyncSession, raw_csv: str) -> dict[str, Any]:
    started = time.perf_counter()
    reader = csv.DictReader(io.StringIO(raw_csv))
    if not reader.fieldnames:
        return {"imported": 0, "errors": [{"row": 0, "message": "Missing CSV header"}], "duration_s": 0}

    required = {"name", "url", "platform_key", "connector_key"}
    missing_cols = required - set(reader.fieldnames)
    if missing_cols:
        return {
            "imported": 0,
            "errors": [{"row": 0, "message": f"Missing columns: {sorted(missing_cols)}"}],
            "duration_s": 0,
        }

    known_connectors = set(list_connectors())
    seen_urls: set[str] = set()
    errors: list[dict] = []
    imported = 0

    existing = await db.execute(select(Destination.url))
    for (url,) in existing.all():
        if url:
            seen_urls.add(_normalize_url(url))

    for idx, row in enumerate(reader, start=2):
        name = (row.get("name") or "").strip()
        url = (row.get("url") or "").strip()
        connector_key = (row.get("connector_key") or "").strip()
        platform_key = (row.get("platform_key") or "").strip()

        if not name or not url or not connector_key or not platform_key:
            errors.append({"row": idx, "message": "name, url, platform_key, connector_key required"})
            continue
        if not _URL_RE.match(url):
            errors.append({"row": idx, "message": f"Invalid URL: {url}"})
            continue
        if connector_key not in known_connectors:
            errors.append({"row": idx, "message": f"Unknown connector_key: {connector_key}"})
            continue

        norm = _normalize_url(url)
        if norm in seen_urls:
            errors.append({"row": idx, "message": f"Duplicate URL: {url}"})
            continue
        seen_urls.add(norm)

        dest = Destination(
            name=name,
            url=url,
            platform_key=platform_key,
            connector_key=connector_key,
            surface=(row.get("surface") or "default").strip(),
            language=(row.get("language") or "en").strip()[:16],
            category=(row.get("category") or None),
            relevance_score=int(row["relevance_score"]) if row.get("relevance_score") else None,
            relevance_reason=row.get("relevance_reason"),
            self_promo_allowed=(row.get("self_promo_allowed", "true").lower() != "false"),
            link_policy=(row.get("link_policy") or "allowed"),
            disclosure_required=(row.get("disclosure_required", "").lower() == "true"),
            automation_allowed=(row.get("automation_allowed", "true").lower() != "false"),
            connection={"instance_params": {"base_url": url}},
        )
        db.add(dest)
        imported += 1

    await db.flush()
    duration = time.perf_counter() - started
    return {
        "imported": imported,
        "duplicates": len([e for e in errors if "Duplicate" in e["message"]]),
        "errors": errors,
        "duration_s": round(duration, 3),
    }
