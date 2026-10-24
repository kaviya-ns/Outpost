from abc import ABC, abstractmethod
from typing import Any


class RulesExtractionAdapter(ABC):
    provider_name: str = "base"

    @abstractmethod
    async def propose_posting_rules(self, rules_page_text: str, destination_name: str) -> dict[str, Any]:
        """Return proposed rules + explanation for human review."""
