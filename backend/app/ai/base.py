"""AI provider interface and the deterministic guards applied to every AI response.

The AI is only ever asked to translate an edit instruction the rule parser did not understand into the
same structured operations the rules produce. Its output is validated (schema, allow-list, existing item
IDs, numbers must come from the user's instruction or the current data) and is always shown as a
proposal the user must apply. Arithmetic, extraction and validation never use the AI.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Protocol

from pydantic import TypeAdapter, ValidationError

from ..config import Settings
from ..models import (
    AI_ALLOWED_OPS,
    AddItemOp,
    AppSettings,
    EditOperation,
    SetFieldOp,
    SetItemOp,
    SetTaxOp,
)

_OP_ADAPTER: TypeAdapter[EditOperation] = TypeAdapter(EditOperation)
MAX_OPS = 10
_NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")


class AIUnavailable(Exception):
    """The provider is not configured, unreachable, or returned an unusable answer."""


@dataclass
class AIResult:
    ops: list[EditOperation]
    explanation: str
    rejected: list[str] = field(default_factory=list)


class AIProvider(Protocol):
    name: str
    model: str

    def complete_json(self, system: str, user: str) -> dict[str, Any]: ...


def provider_status(settings: Settings, app_settings: AppSettings) -> dict[str, Any]:
    """Public, secret-free description of the AI configuration (for the UI and /api/health)."""
    configured = settings.ai_configured
    return {
        "mode": "external" if configured and app_settings.use_external_ai else "local",
        "configured": configured,
        "enabled_in_settings": app_settings.use_external_ai,
        "provider": settings.ai_provider or None,
        "model": settings.ai_model or None,
        "base_url_host": _host(settings.ai_base_url) if configured else None,
        "api_key_present": bool(settings.ai_api_key),
    }


def _host(url: str) -> str | None:
    m = re.match(r"^[a-z]+://([^/:]+)", url or "", re.I)
    return m.group(1) if m else None


def get_provider(settings: Settings, app_settings: AppSettings) -> AIProvider | None:
    if not settings.ai_configured or not app_settings.use_external_ai:
        return None
    from .openai_compat import OpenAICompatibleProvider

    return OpenAICompatibleProvider(
        base_url=settings.ai_base_url,
        model=settings.ai_model,
        api_key=settings.ai_api_key,
        timeout_s=settings.ai_timeout_s,
    )


def _numbers(text: str) -> set[str]:
    out: set[str] = set()
    for m in _NUM.findall(text or ""):
        try:
            out.add(str(Decimal(m.replace(",", "")).normalize()))
        except ArithmeticError:
            continue
    return out


def validate_ai_operations(
    payload: dict[str, Any],
    instruction: str,
    context_text: str,
    item_ids: set[str],
    field_keys: set[str],
) -> AIResult:
    """Validate the provider's JSON. Unsafe or unverifiable operations are dropped, never repaired."""
    if not isinstance(payload, dict):
        raise AIUnavailable("The AI provider returned an unexpected response.")
    raw_ops = payload.get("operations", [])
    explanation = str(payload.get("explanation", ""))[:500]
    if not isinstance(raw_ops, list):
        raise AIUnavailable("The AI provider returned an unexpected response.")
    allowed_numbers = _numbers(instruction)
    context_numbers = _numbers(context_text) | allowed_numbers
    ops: list[EditOperation] = []
    rejected: list[str] = []
    for raw in raw_ops[:MAX_OPS]:
        try:
            op = _OP_ADAPTER.validate_python(raw)
        except ValidationError:
            rejected.append("An operation did not match the allowed format and was ignored.")
            continue
        if op.op not in AI_ALLOWED_OPS:
            rejected.append(f"Operation “{op.op}” is not allowed for AI suggestions and was ignored.")
            continue
        if isinstance(op, SetItemOp):
            if op.line_item_id not in item_ids:
                rejected.append("An operation referred to a line item that does not exist and was ignored.")
                continue
            numeric = op.attribute in ("quantity", "unit_price", "amount_override")
            if numeric and op.value is not None and _numbers(op.value) - allowed_numbers:
                rejected.append(
                    f"The AI proposed {op.attribute.replace('_', ' ')} “{op.value}”, which is not in your instruction. Ignored."
                )
                continue
        if isinstance(op, AddItemOp):
            nums = _numbers(op.quantity or "") | _numbers(op.unit_price or "")
            if nums - allowed_numbers:
                rejected.append("The AI proposed a quantity or price that is not in your instruction. Ignored.")
                continue
        if isinstance(op, SetTaxOp) and op.rate is not None and (_numbers(op.rate) - allowed_numbers):
            rejected.append("The AI proposed a tax rate that is not in your instruction. Ignored.")
            continue
        if isinstance(op, SetFieldOp):
            if op.field_key not in field_keys:
                rejected.append(f"Field “{op.field_key}” cannot be edited. Ignored.")
                continue
            if op.value and (_numbers(op.value) - context_numbers):
                rejected.append("Suggested text contained numbers that are not in your instruction or data. Ignored.")
                continue
        ops.append(op)
    return AIResult(ops=ops, explanation=explanation, rejected=rejected)
