"""Layer 1 — Input validation and sanitization.

Validates and sanitises user-supplied campaign fields *before* they reach
any LLM or tool.  Keeps logic minimal: length limits, character filtering,
and lightweight format checks for structured fields.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Limits
# ---------------------------------------------------------------------------
_MAX_SHORT_FIELD = 200      # campaign_type, target_industry, budget, timeline
_MAX_GOALS_FIELD = 1_000    # goals / free-text KPI list
_MAX_CHAT_MESSAGE = 2_000   # individual chat message


class InputValidationError(Exception):
    """Raised when user input fails validation."""


# ---------------------------------------------------------------------------
# Dangerous character patterns
# ---------------------------------------------------------------------------
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")  # null bytes, control chars (keep \n \r \t)
_EXCESSIVE_NEWLINES = re.compile(r"\n{4,}")                          # 4+ consecutive newlines → 2


@dataclass(frozen=True)
class InputValidator:
    """Stateless validator — call ``validate_campaign`` or ``validate_chat``."""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def validate_campaign(
        self,
        *,
        campaign_type: str,
        target_industry: str,
        budget: str,
        timeline: str,
        goals: str,
    ) -> dict[str, str]:
        """Return a dict of sanitised field values or raise ``InputValidationError``."""
        return {
            "campaign_type": self._clean_short("campaign_type", campaign_type),
            "target_industry": self._clean_short("target_industry", target_industry),
            "budget": self._clean_budget(budget),
            "timeline": self._clean_short("timeline", timeline),
            "goals": self._clean_text("goals", goals, _MAX_GOALS_FIELD),
        }

    def validate_chat(self, *, user_message: str, current_report: str) -> dict[str, str]:
        """Return sanitised chat fields or raise ``InputValidationError``."""
        return {
            "user_message": self._clean_text("user_message", user_message, _MAX_CHAT_MESSAGE),
            "current_report": current_report,  # report is system-generated, just pass through
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _strip_dangerous(text: str) -> str:
        text = _CONTROL_CHARS.sub("", text)
        text = _EXCESSIVE_NEWLINES.sub("\n\n", text)
        return text.strip()

    def _clean_short(self, name: str, value: str) -> str:
        value = self._strip_dangerous(value)
        if not value:
            raise InputValidationError(f"{name} must not be empty.")
        if len(value) > _MAX_SHORT_FIELD:
            raise InputValidationError(
                f"{name} exceeds maximum length ({_MAX_SHORT_FIELD} chars)."
            )
        return value

    def _clean_text(self, name: str, value: str, limit: int) -> str:
        value = self._strip_dangerous(value)
        if not value:
            raise InputValidationError(f"{name} must not be empty.")
        if len(value) > limit:
            raise InputValidationError(
                f"{name} exceeds maximum length ({limit} chars)."
            )
        return value

    @staticmethod
    def _clean_budget(value: str) -> str:
        value = _CONTROL_CHARS.sub("", value).strip()
        if not value:
            raise InputValidationError("budget must not be empty.")
        if len(value) > _MAX_SHORT_FIELD:
            raise InputValidationError(
                f"budget exceeds maximum length ({_MAX_SHORT_FIELD} chars)."
            )
        # Allow digits, currency symbols, commas, dots, spaces, and common words like "k", "K", "million"
        if not re.match(
            r'^[\d\s,.\-$€£¥₹]+(?:\s*(?:k|K|M|m|million|billion|thousand|hundred|USD|EUR|GBP|INR))?$',
            value,
        ):
            raise InputValidationError(
                "budget must be a numeric value (e.g. '100000', '$50,000', '100k')."
            )
        return value
