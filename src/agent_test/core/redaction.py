"""Redaction — strip sensitive values out of a cassette before it's written.

Cassettes get committed to git. A tool argument or LLM response that happens
to contain an API key, an email address, or a credit-card-looking number
shouldn't sit in plaintext in a repo's history forever just because it
passed through an agent run once. Applied at record time (see
`adapters.langgraph.LangGraphRecorder`'s `redactor` param), not at
replay/assertion time — the point is that the sensitive value never reaches
disk in the first place.

Opt-in, not automatic: passing `redactor=None` (the default) records
exactly what happened, byte for byte, matching every cassette this project
already ships. Pass a `Redactor()` explicitly to turn this on.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

TextPattern = Callable[[str], str]


def _regex_pattern(pattern: re.Pattern[str], placeholder: str) -> TextPattern:
    def _redact(text: str) -> str:
        return pattern.sub(placeholder, text)

    return _redact


redact_emails = _regex_pattern(
    re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),
    "[REDACTED_EMAIL]",
)
redact_api_keys = _regex_pattern(
    # common provider key prefixes (OpenAI/Anthropic, PyPI, GitHub, AWS, ...)
    # followed by a long token-looking suffix
    re.compile(r"\b(?:sk|pypi|ghp|gho|ghu|ghs|ghr|xox[abps]|AKIA)-?[A-Za-z0-9_-]{10,}\b"),
    "[REDACTED_API_KEY]",
)
redact_credit_cards = _regex_pattern(
    re.compile(r"\b(?:\d[ -]?){13,16}\b"),
    "[REDACTED_CARD_NUMBER]",
)

DEFAULT_PATTERNS: tuple[TextPattern, ...] = (
    redact_emails,
    redact_api_keys,
    redact_credit_cards,
)
DEFAULT_KEYS: tuple[str, ...] = (
    "api_key",
    "apikey",
    "authorization",
    "password",
    "secret",
    "token",
)


@dataclass
class Redactor:
    """Recursively redacts sensitive values out of dicts/lists/strings.

    Two independent mechanisms, both applied: `patterns` scan every string
    value for known-sensitive shapes (an email, an API key, ...) regardless
    of which field they're in; `keys` blanks out any dict value whose key
    matches by name (case-insensitive), regardless of what the value looks
    like — for secrets that don't have a recognizable shape (a random
    session token, an internal password).
    """

    patterns: tuple[TextPattern, ...] = field(default_factory=lambda: DEFAULT_PATTERNS)
    keys: tuple[str, ...] = field(default_factory=lambda: DEFAULT_KEYS)
    key_placeholder: str = "[REDACTED]"

    def redact_text(self, text: str) -> str:
        for pattern in self.patterns:
            text = pattern(text)
        return text

    def redact(self, value: Any) -> Any:
        if isinstance(value, str):
            return self.redact_text(value)
        if isinstance(value, dict):
            return {
                key: (
                    self.key_placeholder
                    if isinstance(key, str) and key.lower() in self.keys
                    else self.redact(val)
                )
                for key, val in value.items()
            }
        if isinstance(value, list):
            return [self.redact(item) for item in value]
        return value
