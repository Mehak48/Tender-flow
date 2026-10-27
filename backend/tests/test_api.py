"""API-level behaviour: health, settings, sample project, library, deletion, evidence."""

from __future__ import annotations

import json

from tests.conftest import new_project, ready_project, upload


def test_health_reports_capabilities_without_secrets(client, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    r = client.get("/api/health")
    body = r.json()
    assert r.status_code == 200 and body["status"] == "ok" and body["app_name"] == "TenderFlow"
    assert body["ai"]["mode"] == "local" and body["ocr"] is False
    assert set(body["limits"]["formats"]) == {"tender", "template", "price_list"}
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    csp = r.headers["content-security-policy"]
    assert "default-src 'self'" in csp and "script-src 'self'" in csp and "frame-ancestors 'none'" in csp
    assert "unsafe-eval" not in csp and "script-src 'self' 'unsafe-inline'" not in csp
    # FastAPI's interactive docs load assets from a CDN and are exempt.
    assert "content-security-policy" not in client.get("/docs").headers


def test_unknown_api_route_is_json_404(client) -> None:  # type: ignore[no-untyped-def]
    r = client.get("/api/nope")
    assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"


def test_settings_validation(client) -> None:  # type: ignore[no-untyped-def]
    base = {"company": {}, "tax": {"enabled": False}, "quotation_prefix": "QTN"}
    assert client.put("/api/settings", json={**base, "default_currency": "ABC"}).status_code == 400
    assert client.put("/api/settings", json={**base, "tax": {"enabled": True}}).status_code == 400
    assert client.put("/api/settings", json={**base, "tax": {"enabled": True, "rate": "120"}}).status_code == 400
    assert client.put("/api/settings", json={**base, "quotation_prefix": "../x"}).status_code == 400
    r = client.put(
        "/api/settings",
        json={**base, "default_currency": "pkr", "tax": {"enabled": True, "rate": "17", "label": "GST"}},
    )
    assert r.status_code == 200
    s = client.get("/api/settings").json()["settings"]
    assert s["default_currency"] == "PKR" and s["tax"]["rate"] == "17"


def test_sample_project_runs_the_real_pipeline(client) -> None:  # type: ignore[no-untyped-def]
    r = client.post("/api/demo/project")
    assert r.status_code == 201, r.text
    view = r.json()
    assert view["is_sample"] is True and view["company_source"] == "project_sample"
    assert {d["role"] for d in view["documents"]} == {"tender", "template", "price_list"}
    assert len(view["extraction"]["line_items"]) == 5
    assert view["stage"] == "extraction"
    names = [p["name"] for p in client.get("/api/projects").json()]
    assert "Sample: IT network equipment tender" in names


def test_evidence_returns_verbatim_source_text(client, docs) -> None:  # type: ignore[no-untyped-def]
    pid = new_project(client)
    view = upload(client, pid, "tender", docs["tender_pdf"]).json()
    doc_id = view["documents"][0]["id"]
    ref = next(f for f in view["extraction"]["fields"] if f["key"] == "delivery_period")["sources"][0]
    r = client.get(f"/api/projects/{pid}/documents/{doc_id}/evidence", params={"block_id": ref["block_id"]})
    ev = r.json()
    assert ev["page"] == 3 and ev["focus_block_id"] == ref["block_id"]
    focus = next(b for b in ev["blocks"] if b["id"] == ref["block_id"])
    assert "Within 45 days" in focus["text"]
    assert (
        client.get(f"/api/projects/{pid}/documents/{doc_id}/evidence", params={"block_id": "../../x"}).status_code
        == 400
    )


def test_extraction_review_actions(client, docs) -> None:  # type: ignore[no-untyped-def]
    pid = new_project(client)
    upload(client, pid, "tender", docs["tender_pdf"])
    url = f"/api/projects/{pid}/extraction"
    r = client.put(url, json={"fields": [{"key": "submission_deadline", "action": "confirm"}]})
    assert r.status_code == 400  # a conflict must be resolved by choosing a value first
    r = client.put(url, json={"fields": [{"key": "submission_deadline", "action": "choose", "candidate_index": 1}]})
    deadline = next(f for f in r.json()["extraction"]["fields"] if f["key"] == "submission_deadline")
    assert deadline["status"] == "confirmed" and deadline["value"] == "14 November 2026, 11:30 AM"
    r = client.put(url, json={"fields": [{"key": "tender_title", "action": "edit", "value": "  Network kit  "}]})
    title = next(f for f in r.json()["extraction"]["fields"] if f["key"] == "tender_title")
    assert title["status"] == "edited" and title["value"] == "Network kit"
    items = r.json()["extraction"]["line_items"]
    r = client.put(
        url,
        json={
            "line_items": [
                {"id": items[0]["id"], "action": "edit", "quantity": "10"},
                {"id": items[1]["id"], "action": "delete"},
                {"action": "add", "description": "Patch panel", "quantity": "2 Nos"},
            ]
        },
    )
    new_items = r.json()["extraction"]["line_items"]
    assert new_items[0]["quantity"] == "10" and new_items[0]["status"] == "edited"
    assert len(new_items) == 5 and new_items[-1]["unit"] == "Nos"
    r = client.put(url, json={"line_items": [{"id": items[2]["id"], "action": "edit", "quantity": "lots"}]})
    assert r.status_code == 400


def test_stale_quotation_is_reported(client, docs) -> None:  # type: ignore[no-untyped-def]
    view = ready_project(client, docs)
    pid = view["id"]
    assert view["stale_reasons"] == []
    r = client.put(
        f"/api/projects/{pid}/extraction", json={"fields": [{"key": "tender_title", "action": "edit", "value": "X"}]}
    )
    assert any("tender data changed" in s for s in r.json()["stale_reasons"])
    r = client.post(f"/api/projects/{pid}/quotation/generate")
    assert r.json()["stale_reasons"] == [] and r.json()["edit_history"][0]["kind"] == "regenerate"
    assert r.json()["undo_available"] == 1


def test_library_listings(client, docs) -> None:  # type: ignore[no-untyped-def]
    view = ready_project(client, docs)
    client.post(f"/api/projects/{view['id']}/export", json={"format": "docx", "draft": True})
    templates = client.get("/api/library/templates").json()
    assert len(templates) == 1 and templates[0]["analysis"]["items_table"] is not None
    documents = client.get("/api/library/documents").json()
    assert {d["kind"] for d in documents} == {"tender", "template", "price_list", "export"}
    activity = client.get("/api/library/activity").json()
    kinds = {a["event"]["kind"] for a in activity}
    assert {"tender_parsed", "mapping_confirmed", "quotation_generated", "exported"} <= kinds
    # Reusing a template creates a new project with the same template.
    tpl = templates[0]
    r = client.post(f"/api/projects/{tpl['project_id']}/documents/{tpl['document']['id']}/reuse")
    assert r.status_code == 201 and r.json()["template"] is not None


def test_deleting_projects_and_all_data(client, docs, settings) -> None:  # type: ignore[no-untyped-def]
    view = ready_project(client, docs)
    pid = view["id"]
    project_dir = settings.data_dir / "projects" / pid
    assert project_dir.is_dir()
    assert client.delete(f"/api/projects/{pid}").status_code == 204
    assert not project_dir.exists()
    assert client.get(f"/api/projects/{pid}").status_code == 404
    new_project(client)
    assert client.delete("/api/data").status_code == 400  # needs explicit confirmation
    assert client.delete("/api/data", params={"confirm": "DELETE"}).status_code == 204
    assert client.get("/api/projects").json() == []


def test_project_summary_status(client, docs) -> None:  # type: ignore[no-untyped-def]
    view = ready_project(client, docs)
    summary = next(p for p in client.get("/api/projects").json() if p["id"] == view["id"])
    assert summary["status"] == "needs_attention" and summary["errors"] > 0
    assert summary["tender_name"] == "tender.pdf" and summary["stage"] == "editor"
    assert json.dumps(summary)


def test_dotenv_loader_does_not_override_real_environment(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from app.config import load_dotenv_files

    env = tmp_path / ".env"
    env.write_text(
        "# comment\nTENDERFLOW_AI_MODEL='local-model'\nTENDERFLOW_MAX_UPLOAD_MB=5\nOTHER_SECRET=x\n", encoding="utf-8"
    )
    monkeypatch.delenv("TENDERFLOW_AI_MODEL", raising=False)
    monkeypatch.setenv("TENDERFLOW_MAX_UPLOAD_MB", "9")
    monkeypatch.delenv("OTHER_SECRET", raising=False)
    assert load_dotenv_files((env,)) == [env]
    import os

    assert os.environ["TENDERFLOW_AI_MODEL"] == "local-model"
    assert os.environ["TENDERFLOW_MAX_UPLOAD_MB"] == "9"  # real environment wins
    assert "OTHER_SECRET" not in os.environ  # only TENDERFLOW_* keys are read
    monkeypatch.delenv("TENDERFLOW_AI_MODEL", raising=False)
