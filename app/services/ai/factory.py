from app.config import get_settings
from app.services.ai.base import RulesExtractionAdapter
from app.services.ai.mock_adapter import MockRulesExtractionAdapter


def get_rules_adapter() -> RulesExtractionAdapter:
    settings = get_settings()
    provider = (settings.ai_provider or "mock").lower()
    if provider == "mock":
        return MockRulesExtractionAdapter()
    # Swappable: add openai/anthropic adapters behind the same interface.
    return MockRulesExtractionAdapter()
