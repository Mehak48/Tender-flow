"""Optional external AI provider adapter. Off by default; see docs/AI_POLICY.md."""

from .base import AIProvider, AIResult, AIUnavailable, get_provider, provider_status

__all__ = ["AIProvider", "AIResult", "AIUnavailable", "get_provider", "provider_status"]
