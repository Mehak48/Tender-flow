"""Optional AI adapter: tested with a mocked HTTP transport and a fake provider (no live provider)."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from app.ai.base import AIUnavailable, get_provider, provider_status, validate_ai_operations
from app.ai.openai_compat import OpenAICompatibleProvider
from app.config import Settings
from app.models import AppSettings
from tests.conftest import ready_project


def _transport(payload: Any, status: int = 200) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/chat/completions")
        body = json.loads(request.content)
        assert body["temperature"] == 0 and body["messages"][0]["role"] == "system"
        content = payload if isinstance(payload, str) else json.dumps(payload)
        return httpx.Response(status, json={"choices": [{"message": {"content": content}}]})

    return httpx.MockTransport(handler)


def test_provider_parses_json_and_sends_key_only_in_header() -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("authorization", "")
        assert "sk-test" not in request.content.decode()
        return httpx.Response(
            200, json={"choices": [{"message": {"content": '{"operations": [], "explanation": "ok"}'}}]}
        )

    p = OpenAICompatibleProvider("http://llm.local/v1", "m", api_key="sk-test", transport=httpx.MockTransport(handler))
    assert p.complete_json("s", "u") == {"operations": [], "explanation": "ok"}
    assert seen["auth"] == "Bearer sk-test"


@pytest.mark.parametrize("payload,status", [("not json", 200), ('["a list"]', 200), ({"x": 1}, 500)])
def test_provider_errors_become_ai_unavailable(payload: Any, status: int) -> None:
    p = OpenAICompatibleProvider("http://llm.local/v1", "m", transport=_transport(payload, status))
    with pytest.raises(AIUnavailable):
        p.complete_json("s", "u")


def test_unreachable_provider() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down")

    p = OpenAICompatibleProvider("http://llm.local/v1", "m", transport=httpx.MockTransport(handler))
    with pytest.raises(AIUnavailable):
        p.complete_json("s", "u")


def test_guards_drop_invented_numbers_and_unknown_items() -> None:
    payload = {
        "operations": [
            {"op": "set_item", "line_item_id": "itm_aaaaaaaaaaaa", "attribute": "unit_price", "value": "99999"},
            {"op": "set_item", "line_item_id": "itm_bbbbbbbbbbbb", "attribute": "unit_price", "value": "5000"},
            {"op": "set_item", "line_item_id": "itm_aaaaaaaaaaaa", "attribute": "unit_price", "value": "5000"},
            {"op": "confirm_fields", "field_keys": ["delivery_terms"]},
            {"op": "set_field", "field_key": "total", "value": "1"},
            {"op": "delete_everything"},
            {"op": "set_field", "field_key": "payment_terms", "value": "Payment within 30 days of delivery."},
        ],
        "explanation": "test",
    }
    result = validate_ai_operations(
        payload,
        instruction="make the switch cost 5000",
        context_text='{"payment": "100% payment within 30 days"}',
        item_ids={"itm_aaaaaaaaaaaa"},
        field_keys={"payment_terms", "delivery_terms"},
    )
    kept = [(o.op, getattr(o, "value", None)) for o in result.ops]
    assert kept == [("set_item", "5000"), ("set_field", "Payment within 30 days of delivery.")]
    assert len(result.rejected) == 5


def test_status_never_exposes_the_key() -> None:
    cfg = Settings(
        data_dir=None,
        samples_dir=None,
        frontend_dist=None,
        max_upload_mb=1,  # type: ignore[arg-type]
        ai_provider="openai_compatible",
        ai_base_url="https://api.example.com/v1",
        ai_model="m",
        ai_api_key="sk-secret-value",
    )
    status = provider_status(cfg, AppSettings(use_external_ai=True))
    assert "sk-secret-value" not in json.dumps(status)
    assert status["mode"] == "external" and status["api_key_present"] is True
    assert status["base_url_host"] == "api.example.com"
    assert get_provider(cfg, AppSettings(use_external_ai=False)) is None  # opt-in in Settings too
    unconfigured = Settings(data_dir=None, samples_dir=None, frontend_dist=None, max_upload_mb=1)  # type: ignore[arg-type]
    assert get_provider(unconfigured, AppSettings(use_external_ai=True)) is None


class FakeProvider:
    name = "fake"
    model = "fake-model"

    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.calls: list[str] = []

    def complete_json(self, system: str, user: str) -> dict:
        self.calls.append(user)
        return self.payload


def test_ai_fallback_through_the_api(client, docs) -> None:  # type: ignore[no-untyped-def]
    company = {
        "name": "Fixture Supplier Ltd",
        "address": "1 Fixture Road",
        "phone": "+00 111 2222",
        "email": "sales@fixture.example",
        "registration": "FIX-REG-9",
        "prepared_by": "Fixture Person",
    }
    r = client.put("/api/settings", json={"company": company, "tax": {"enabled": False}})
    assert r.status_code == 200, r.text
    view = ready_project(client, docs)
    pid = view["id"]
    assert view["quotation"]["fields"]["company_email"]["value"] == "sales@fixture.example"
    fake = FakeProvider(
        {
            "operations": [
                {"op": "set_field", "field_key": "notes", "value": "Prices are valid for the tendered quantities only."}
            ],
            "explanation": "Add a clarifying note.",
        }
    )
    client.app.state.ai_provider_override = fake
    r = client.post(
        f"/api/projects/{pid}/quotation/edits",
        json={"instruction": "Please clarify that our prices depend on quantity"},
    )
    res = r.json()["response"]
    assert res["engine"] == "ai" and res["proposal"]["engine"] == "ai"
    # Document text reaches the provider only inside the delimited data block.
    assert "<quotation_data>" in fake.calls[0] and "Instruction: Please clarify" in fake.calls[0]
    # Company and personal details are not sent.
    for private in company.values():
        assert private not in fake.calls[0]
    r = client.post(f"/api/projects/{pid}/quotation/edits/{res['proposal']['id']}/apply", json={})
    notes = r.json()["quotation"]["fields"]["notes"]
    assert notes["origin"] == "ai_suggestion"
    assert any(i["id"] == "claims:ai:notes" for i in r.json()["validation"]["issues"])
    # Rules still win for supported instructions: the provider is not called.
    calls = len(fake.calls)
    client.post(f"/api/projects/{pid}/quotation/edits", json={"instruction": "Set currency to PKR"})
    assert len(fake.calls) == calls


def test_ai_cannot_change_company_personal_or_derived_fields(client, docs) -> None:  # type: ignore[no-untyped-def]
    pid = ready_project(client, docs)["id"]
    fake = FakeProvider(
        {
            "operations": [
                {"op": "set_field", "field_key": "company_name", "value": "Someone Else Ltd"},
                {"op": "set_field", "field_key": "prepared_by", "value": "Someone"},
                {"op": "set_field", "field_key": "total", "value": "1"},
                {"op": "set_field", "field_key": "signature", "value": "Signed"},
                {"op": "confirm_prices", "line_item_ids": []},
            ],
            "explanation": "Change company details.",
        }
    )
    client.app.state.ai_provider_override = fake
    r = client.post(f"/api/projects/{pid}/quotation/edits", json={"instruction": "Make us look like a bigger firm"})
    res = r.json()["response"]
    assert res["understood"] is False and res["proposal"] is None
    assert "cannot be edited" in res["message"] and "not allowed" in res["message"]
    sent = json.loads(fake.calls[0].split("<quotation_data>\n", 1)[1].split("\n</quotation_data>", 1)[0])
    assert not any(k.startswith("company_") or k in ("prepared_by", "signature", "total") for k in sent["fields"])
    assert not any(k.startswith("company_") or k == "prepared_by" for k in sent["editable_field_keys"])
