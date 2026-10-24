import re

from app.models.tables import Destination
from app.schemas.common import Rendition
from app.services.manifest_loader import manifest_loader


def _truncate_words(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    cut = text[: max_chars + 1]
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    return cut.rstrip() + "…"


def _surface_spec(connector_key: str, surface: str) -> dict:
    manifest = manifest_loader.get(connector_key) or {}
    for s in manifest.get("surfaces", []):
        if s.get("key") == surface:
            return s.get("spec", {})
    surfaces = manifest.get("surfaces", [])
    return surfaces[0].get("spec", {}) if surfaces else {}


def tailor_rendition(destination: Destination, rendition: Rendition) -> tuple[Rendition, list[str]]:
    warnings: list[str] = []
    spec = _surface_spec(destination.connector_key, destination.surface)
    title_max = spec.get("title_max_chars")
    body_max = spec.get("body_max_chars")

    title = rendition.title
    body = rendition.body
    hashtags = list(rendition.hashtags)

    platform = destination.connector_key
    if platform in ("discourse", "lemmy"):
        if title and not title.lower().startswith(("question:", "thought:", "curious")):
            title = f"Thought: {title}"
            warnings.append("discussion_first_title")
        if rendition.canonical_url and rendition.canonical_url not in body:
            body = f"{body}\n\nLink: {rendition.canonical_url}".strip()
    elif platform in ("devto", "ghost"):
        if rendition.canonical_url:
            body = f"{body}\n\n<!-- canonical: {rendition.canonical_url} -->".strip()
            warnings.append("canonical_url_embedded")
        if platform == "devto" and hashtags:
            tag_line = " ".join(f"#{t.lstrip('#')}" for t in hashtags[:4])
            body = f"{body}\n\n{tag_line}".strip()
            warnings.append("devto_hashtags_appended")

    if rendition.is_ai_generated and destination.disclosure_required:
        if "ai-generated" not in body.lower():
            body = f"{body}\n\n_(AI-generated content.)_".strip()
            warnings.append("ai_disclosure_appended")

    if title_max:
        title = _truncate_words(title, int(title_max))
    if body_max:
        body = _truncate_words(body, int(body_max))

    body = re.sub(r"@(\w+)", r"@\1", body)

    tailored = rendition.model_copy(
        update={
            "title": title,
            "body": body,
            "hashtags": hashtags,
        }
    )
    return tailored, warnings
