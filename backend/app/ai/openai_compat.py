"""Adapter for any OpenAI-compatible ``/chat/completions`` endpoint (e.g. a local Ollama or LM Studio
server, or a hosted provider). Configured only through environment variables; never logs content.

Status: implemented and unit-tested against a mocked HTTP transport. It has NOT been tested against a
live provider in this repository — see docs/KNOWN_LIMITATIONS.md.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from .base import AIUnavailable

logger = logging.getLogger("tenderflow.ai")


class OpenAICompatibleProvider:
    name = "openai_compatible"

    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str = "",
        timeout_s: int = 20,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._api_key = api_key
        self._timeout = timeout_s
        self._transport = transport

    def complete_json(self, system: str, user: str) -> dict[str, Any]:
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        body = {
            "model": self.model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        }
        try:
            with httpx.Client(timeout=self._timeout, transport=self._transport) as client:
                resp = client.post(f"{self.base_url}/chat/completions", headers=headers, json=body)
        except httpx.HTTPError as exc:
            logger.warning("AI provider request failed: %s", type(exc).__name__)
            raise AIUnavailable("The AI provider could not be reached.") from exc
        if resp.status_code != 200:
            logger.warning("AI provider returned HTTP %s", resp.status_code)
            raise AIUnavailable(f"The AI provider returned an error (HTTP {resp.status_code}).")
        try:
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            parsed = json.loads(content)
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise AIUnavailable("The AI provider's answer was not valid JSON.") from exc
        if not isinstance(parsed, dict):
            raise AIUnavailable("The AI provider's answer was not a JSON object.")
        return parsed
