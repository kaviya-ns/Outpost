import re
from typing import Any

from app.services.ai.base import RulesExtractionAdapter


class MockRulesExtractionAdapter(RulesExtractionAdapter):
    provider_name = "mock"

    async def propose_posting_rules(self, rules_page_text: str, destination_name: str) -> dict[str, Any]:
        text = rules_page_text.lower()
        self_promo = "no self-promotion" not in text and "self-promotion" not in text
        if "no self-promotion" in text or "self promotion is not allowed" in text:
            self_promo = False

        link_policy = "forbidden" if "no links" in text or "links are not allowed" in text else "allowed"

        disclosure = "ai" in text and ("disclosure" in text or "label" in text)

        freq_count = 1
        window_days = 7
        m = re.search(r"(\d+)\s+posts?\s+per\s+week", text)
        if m:
            freq_count = int(m.group(1))
            window_days = 7
        m2 = re.search(r"(\d+)\s+posts?\s+per\s+day", text)
        if m2:
            freq_count = int(m2.group(1))
            window_days = 1

        explanation = (
            f"Mock analysis for {destination_name}: "
            f"self_promo={self_promo}, links={link_policy}, disclosure={disclosure}, "
            f"cap={freq_count}/{window_days}d."
        )
        return {
            "frequency_cap": {"count": freq_count, "window_days": window_days},
            "self_promo_allowed": self_promo,
            "link_policy": link_policy,
            "disclosure_required": disclosure,
            "confidence": 0.82,
            "explanation": explanation,
        }
