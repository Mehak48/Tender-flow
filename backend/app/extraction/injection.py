"""Detector for instruction-like text inside uploaded documents (prompt-injection heuristics).

This is a basic pattern check, not a guarantee. Its purpose is transparency: matching text is reported
to the user and is never acted upon. TenderFlow's behaviour does not depend on document text in any
case — extraction is rule-based and the optional AI adapter only ever returns validated edit operations.
"""

from __future__ import annotations

import re

PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "override_instructions",
        re.compile(
            r"\b(ignore|disregard|forget|override|bypass)\b[^.\n]{0,40}\b(previous|prior|above|earlier|all|any|"
            r"system|your|the)\b[^.\n]{0,30}\b(instructions?|rules|prompts?|guidelines|directions|policies)\b",
            re.IGNORECASE,
        ),
    ),
    ("role_change", re.compile(r"\b(you are now|act as an?|pretend to be|from now on you)\b", re.IGNORECASE)),
    (
        "role_marker",
        re.compile(
            r"(^|[\s\"'(])(system|assistant|developer)\s*:\s|<\s*/?\s*(system|assistant|prompt)\s*>", re.IGNORECASE
        ),
    ),
    (
        "addressed_to_ai",
        re.compile(
            r"\b(note|message|instructions?)\s+(to|for)\s+(the\s+)?(ai|assistant|chatbot|llm|language model|"
            r"automated\s+(processing\s+)?(tools?|systems?))\b",
            re.IGNORECASE,
        ),
    ),
    (
        "force_approval",
        re.compile(
            r"\b(approve|accept|mark|treat)\b[^.\n]{0,40}\b(as\s+)?(approved|compliant|confirmed|verified|accepted|"
            r"responsive)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "price_manipulation",
        re.compile(r"\bset\s+(all\s+)?(the\s+)?(prices?|totals?|amounts?|rates?|quantities)\s+to\b", re.IGNORECASE),
    ),
    (
        "concealment",
        re.compile(
            r"\bdo\s+not\s+(tell|inform|show|alert|notify)\s+(the\s+)?(user|buyer|human|reviewer)\b", re.IGNORECASE
        ),
    ),
]


def find_instruction_like(text: str) -> list[str]:
    """Return the names of the patterns that match ``text``."""
    return [name for name, rx in PATTERNS if rx.search(text or "")]
