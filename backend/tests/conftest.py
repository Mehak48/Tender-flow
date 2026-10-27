"""Shared fixtures. Every test gets its own temporary data directory; nothing touches backend/data."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import REPO_ROOT, Settings
from app.main import create_app
from tools import sample_docs


@pytest.fixture()
def settings(tmp_path: Path) -> Settings:
    return Settings(
        data_dir=tmp_path / "data",
        samples_dir=REPO_ROOT / "samples",
        frontend_dist=tmp_path / "no-frontend",
        max_upload_mb=2,
        cors_origins=["http://localhost:5173"],
    )


@pytest.fixture()
def client(settings: Settings) -> Iterator[TestClient]:
    app = create_app(settings)
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def docs(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    """Fixture documents generated once per test session (all fictional sample data)."""
    d = tmp_path_factory.mktemp("fixtures")
    return {
        "tender_pdf": sample_docs.build_tender_pdf(d / "tender.pdf"),
        "tender_docx": sample_docs.build_tender_docx(d / "tender.docx"),
        "tender_no_deadline": sample_docs.build_tender_pdf(
            d / "no_deadline.pdf", sample_docs.tender_without_deadline()
        ),
        "tender_malicious": sample_docs.build_tender_pdf(d / "malicious.pdf", sample_docs.malicious_tender()),
        "tender_minimal": sample_docs.build_tender_pdf(d / "minimal.pdf", sample_docs.minimal_tender()),
        "blank_pdf": sample_docs.build_blank_pdf(d / "blank.pdf"),
        "scanned_pdf": sample_docs.build_scanned_pdf(d / "scanned.pdf"),
        "template_docx": sample_docs.build_template_docx(d / "template.docx"),
        "template_rows_docx": sample_docs.build_template_docx_placeholder_rows(d / "template_rows.docx"),
        "template_no_items": sample_docs.build_template_docx_without_items(d / "template_no_items.docx"),
        "template_xlsx": sample_docs.build_template_xlsx(d / "template.xlsx"),
        "prices_xlsx": sample_docs.build_price_list_xlsx(d / "prices.xlsx"),
        "prices_csv": sample_docs.build_price_list_csv(d / "prices.csv"),
    }


def upload(client: TestClient, project_id: str, role: str, path: Path, filename: str | None = None):  # type: ignore[no-untyped-def]
    with open(path, "rb") as fh:
        return client.post(
            f"/api/projects/{project_id}/documents",
            data={"role": role},
            files={"file": (filename or path.name, fh, "application/octet-stream")},
        )


def new_project(client: TestClient, name: str = "Test project") -> str:
    r = client.post("/api/projects", json={"name": name})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def ready_project(
    client: TestClient,
    docs: dict[str, Path],
    template: str = "template_docx",
    prices: str | None = "prices_xlsx",
    tender: str = "tender_pdf",
) -> dict:
    """Upload, resolve the deadline conflict, confirm, map and generate. Returns the project view."""
    pid = new_project(client)
    assert upload(client, pid, "tender", docs[tender]).status_code == 201
    assert upload(client, pid, "template", docs[template]).status_code == 201
    if prices:
        assert upload(client, pid, "price_list", docs[prices]).status_code == 201
    view = client.get(f"/api/projects/{pid}").json()
    deadline = next(f for f in view["extraction"]["fields"] if f["key"] == "submission_deadline")
    if deadline["status"] == "conflict":
        r = client.put(
            f"/api/projects/{pid}/extraction",
            json={"fields": [{"key": "submission_deadline", "action": "choose", "candidate_index": 0}]},
        )
        assert r.status_code == 200, r.text
    assert client.post(f"/api/projects/{pid}/extraction/confirm-all").status_code == 200
    assert client.put(f"/api/projects/{pid}/extraction", json={"mark_reviewed": True}).status_code == 200
    assert client.post(f"/api/projects/{pid}/mapping/confirm").status_code == 200
    r = client.post(f"/api/projects/{pid}/quotation/generate")
    assert r.status_code == 200, r.text
    return r.json()
