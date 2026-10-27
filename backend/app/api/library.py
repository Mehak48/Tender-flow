"""Cross-project listings: templates, documents (uploads and exports) and activity."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends

from ..models import ActivityEvent, DocumentRecord, ExportArtifact, Model, TemplateAnalysis
from ..storage import ProjectStore
from . import deps

router = APIRouter(prefix="/api/library", tags=["library"])


class TemplateEntry(Model):
    project_id: str
    project_name: str
    document: DocumentRecord
    analysis: TemplateAnalysis | None


class LibraryDocument(Model):
    project_id: str
    project_name: str
    kind: Literal["tender", "template", "price_list", "export"]
    id: str
    filename: str
    format: str
    size_bytes: int
    created_at: datetime
    status: str
    download_url: str


class ActivityEntry(Model):
    project_id: str
    project_name: str
    event: ActivityEvent


@router.get("/templates", response_model=list[TemplateEntry])
def templates(store: ProjectStore = Depends(deps.store)) -> list[TemplateEntry]:
    out: list[TemplateEntry] = []
    for p in store.list():
        for d in p.documents:
            if d.role == "template":
                out.append(TemplateEntry(project_id=p.id, project_name=p.name, document=d, analysis=p.template))
    return out


@router.get("/documents", response_model=list[LibraryDocument])
def documents(store: ProjectStore = Depends(deps.store)) -> list[LibraryDocument]:
    out: list[LibraryDocument] = []
    for p in store.list():
        for d in p.documents:
            out.append(
                LibraryDocument(
                    project_id=p.id,
                    project_name=p.name,
                    kind=d.role,
                    id=d.id,
                    filename=d.filename,
                    format=d.format,
                    size_bytes=d.size_bytes,
                    created_at=d.uploaded_at,
                    status="Read with warnings" if d.warnings else "Read",
                    download_url=f"/api/projects/{p.id}/documents/{d.id}/download",
                )
            )
        for e in p.exports:
            out.append(_export_entry(p.id, p.name, e))
    out.sort(key=lambda x: x.created_at, reverse=True)
    return out


def _export_entry(project_id: str, project_name: str, e: ExportArtifact) -> LibraryDocument:
    return LibraryDocument(
        project_id=project_id,
        project_name=project_name,
        kind="export",
        id=e.id,
        filename=e.filename,
        format=e.format,
        size_bytes=e.size_bytes,
        created_at=e.created_at,
        status="Draft" if e.draft else "Final",
        download_url=f"/api/projects/{project_id}/exports/{e.id}/download",
    )


@router.get("/activity", response_model=list[ActivityEntry])
def activity(store: ProjectStore = Depends(deps.store)) -> list[ActivityEntry]:
    entries = [ActivityEntry(project_id=p.id, project_name=p.name, event=e) for p in store.list() for e in p.events]
    entries.sort(key=lambda x: x.event.created_at, reverse=True)
    return entries[:200]
