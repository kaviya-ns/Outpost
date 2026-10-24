from app.connectors.assisted import AssistedConnector
from app.connectors.base import ConnectorBase
from app.connectors.devto import DevToConnector
from app.connectors.discourse import DiscourseConnector
from app.connectors.ghost import GhostConnector
from app.connectors.lemmy import LemmyConnector
from app.connectors.webhook import WebhookConnector

_CONNECTORS: dict[str, ConnectorBase] = {
    DiscourseConnector.key: DiscourseConnector(),
    LemmyConnector.key: LemmyConnector(),
    DevToConnector.key: DevToConnector(),
    GhostConnector.key: GhostConnector(),
    WebhookConnector.key: WebhookConnector(),
    AssistedConnector.key: AssistedConnector(),
}


def get_connector(key: str) -> ConnectorBase:
    if key not in _CONNECTORS:
        raise KeyError(f"Unknown connector: {key}")
    return _CONNECTORS[key]


def list_connectors() -> list[str]:
    return list(_CONNECTORS.keys())
