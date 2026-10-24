from pathlib import Path
from typing import Any

import yaml

from app.config import get_settings


class ManifestLoader:
    def __init__(self) -> None:
        self._cache: dict[str, dict[str, Any]] = {}

    def load_all(self) -> dict[str, dict[str, Any]]:
        if self._cache:
            return self._cache
        settings = get_settings()
        root = Path(settings.manifests_dir)
        if not root.is_absolute():
            root = Path(__file__).resolve().parents[2] / root
        if not root.exists():
            return {}
        for path in root.glob("*.yaml"):
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            if data and "key" in data:
                self._cache[data["key"]] = data
        return self._cache

    def get(self, connector_key: str) -> dict[str, Any] | None:
        return self.load_all().get(connector_key)


manifest_loader = ManifestLoader()
