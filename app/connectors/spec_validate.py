from app.errors import DEST_SPEC_VIOLATION, ApiError
from app.schemas.common import DestinationRef, Rendition
from app.services.manifest_loader import manifest_loader


def validate_against_manifest(
    connector_key: str,
    rendition: Rendition,
    destination: DestinationRef,
) -> dict:
    manifest = manifest_loader.get(connector_key)
    if not manifest:
        return {"ok": True, "violations": []}

    violations: list[dict] = []
    surfaces = manifest.get("surfaces", [])
    surface_key = destination.surface or (surfaces[0]["key"] if surfaces else "default")
    spec = {}
    for s in surfaces:
        if s.get("key") == surface_key:
            spec = s.get("spec", {})
            break
    if not spec and surfaces:
        spec = surfaces[0].get("spec", {})

    title_max = spec.get("title_max_chars")
    if title_max is not None and len(rendition.title) > title_max:
        violations.append(
            {"field": "title", "message": f"Title exceeds {title_max} characters", "code": DEST_SPEC_VIOLATION}
        )

    body_max = spec.get("body_max_chars")
    if body_max is not None and len(rendition.body) > body_max:
        violations.append(
            {"field": "body", "message": f"Body exceeds {body_max} characters", "code": DEST_SPEC_VIOLATION}
        )

    if spec.get("links_allowed") is False and (
        rendition.canonical_url or "http://" in rendition.body or "https://" in rendition.body
    ):
        violations.append({"field": "body", "message": "Links not allowed for this surface", "code": DEST_SPEC_VIOLATION})

    allowed_types = None
    for s in surfaces:
        if s.get("key") == surface_key:
            allowed_types = s.get("content_types")
            break
    if allowed_types and rendition.content_type not in allowed_types:
        violations.append(
            {
                "field": "content_type",
                "message": f"Content type {rendition.content_type} not supported",
                "code": DEST_SPEC_VIOLATION,
            }
        )

    if violations:
        return {"ok": False, "violations": violations}
    return {"ok": True, "violations": []}


def raise_if_spec_violations(result: dict) -> None:
    if not result.get("ok"):
        raise ApiError(
            DEST_SPEC_VIOLATION,
            "Content breaks destination format limits",
            retryable=False,
            status_code=422,
            details={"violations": result.get("violations", [])},
        )
