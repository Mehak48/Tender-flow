"""Project workflow routes: upload → extraction review → mapping → generate → edit → validate → export."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, Response

from .. import editing, services
from ..ai.base import AIProvider
from ..config import Settings
from ..editing import EditResponse
from ..errors import AppError, not_found
from ..evidence import evidence
from ..export import preview_docx_bytes, preview_xlsx_grid, run_export
from ..fields import COMMITMENT_FIELDS
from ..mapping import apply_mapping_update, confirm_mapping
from ..models import (
    ColumnMappingRow,
    ConfirmFieldsOp,
    ConfirmPricesOp,
    EditOperation,
    EvidenceResponse,
    ExportArtifact,
    ExportFormat,
    FieldMappingRow,
    Model,
    ProjectSummary,
    ProjectView,
    SetCurrencyOp,
    SetItemOp,
)
from ..review import ExtractionUpdate, apply_review
from ..storage import ProjectStore, SettingsStore, check_id
from ..validation import validate
from . import deps

router = APIRouter(prefix="/api/projects", tags=["projects"])

MEDIA_TYPES = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "csv": "text/csv",
}


class CreateProject(Model):
    name: str | None = None


class RenameProject(Model):
    name: str


class MappingUpdate(Model):
    fields: list[FieldMappingRow] = []
    columns: list[ColumnMappingRow] = []


class QuotationUpdate(Model):
    operations: list[EditOperation]
    summary: str | None = None


class InstructionRequest(Model):
    instruction: str


class ApplyRequest(Model):
    confirm_material: bool = False


class AcknowledgeRequest(Model):
    issue_id: str
    acknowledged: bool = True


class FixRequest(Model):
    fix: str


class ExportRequest(Model):
    format: ExportFormat
    draft: bool = False


class ExportResponse(Model):
    artifact: ExportArtifact
    project: ProjectView


class EditResult(Model):
    response: EditResponse
    project: ProjectView


def _clean_name(name: str | None, default: str) -> str:
    value = " ".join((name or "").split())[:120]
    return value or default


def _view(store: ProjectStore, sstore: SettingsStore, project_id: str) -> ProjectView:
    return services.project_view(store.load(project_id), sstore.load())


@router.get("", response_model=list[ProjectSummary])
def list_projects(store: ProjectStore = Depends(deps.store)) -> list[ProjectSummary]:
    return [services.project_summary(p) for p in store.list()]


@router.post("", response_model=ProjectView, status_code=201)
def create_project(
    body: CreateProject, store: ProjectStore = Depends(deps.store), sstore: SettingsStore = Depends(deps.settings_store)
) -> ProjectView:
    project = store.create(_clean_name(body.name, "Untitled quotation"))
    return services.project_view(project, sstore.load())


@router.get("/{project_id}", response_model=ProjectView)
def get_project(
    project_id: str, store: ProjectStore = Depends(deps.store), sstore: SettingsStore = Depends(deps.settings_store)
) -> ProjectView:
    return _view(store, sstore, project_id)


@router.patch("/{project_id}", response_model=ProjectView)
def rename_project(
    project_id: str,
    body: RenameProject,
    store: ProjectStore = Depends(deps.store),
    sstore: SettingsStore = Depends(deps.settings_store),
) -> ProjectView:
    with store.transaction(project_id) as project:
        project.name = _clean_name(body.name, project.name)
    return _view(store, sstore, project_id)


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: str, store: ProjectStore = Depends(deps.store)) -> Response:
    store.delete(project_id)
    return Response(status_code=204)


# --- documents ---------------------------------------------------------------


@router.post("/{project_id}/documents", response_model=ProjectView, status_code=201)
def upload_document(
    project_id: str,
    request: Request,
    role: str = Form(...),
    file: UploadFile = File(...),
    store: ProjectStore = Depends(deps.store),
    sstore: SettingsStore = Depends(deps.settings_store),
    cfg: Settings = Depends(deps.config),
) -> ProjectView:
    length = request.headers.get("content-length")
    if length and length.isdigit() and int(length) > cfg.max_upload_bytes + 1024 * 1024:
        raise AppError("file_too_large", f"The file is larger than the {cfg.max_upload_mb} MB limit.", 413)
    data = file.file.read(cfg.max_upload_bytes + 1)
    with store.transaction(project_id) as project:
        services.process_upload(store, cfg, project, role, file.filename, data)
        if project.quotation is None and project.name == "Untitled quotation":
            tender = services.document(project, "tender")
            title = next(
                (
                    f.value
                    for f in (project.extraction.fields if project.extraction else [])
                    if f.key == "tender_title" and f.value
                ),
                None,
            )
            if tender and title:
                project.name = _clean_name(title, project.name)
    return _view(store, sstore, project_id)


@router.post("/{project_id}/samples", response_model=ProjectView)
def load_samples(
    project_id: str,
    store: ProjectStore = Depends(deps.store),
    sstore: SettingsStore = Depends(deps.settings_store),
    cfg: Settings = Depends(deps.config),
) -> ProjectView:
    with store.transaction(project_id) as project:
        services.load_sample_documents(store, cfg, project)
        if project.name == "Untitled quotation":
            project.name = "Sample: IT network equipment tender"
    return _view(store, sstore, project_id)


@router.delete("/{project_id}/documents/{document_id}", response_model=ProjectView)
def delete_document(
    project_id: str,
    document_id: str,
    store: ProjectStore = Depends(deps.store),
    sstore: SettingsStore = Depends(deps.settings_store),
) -> ProjectView:
    check_id(document_id, "doc", "Document")
    with store.transaction(project_id) as project:
        services.remove_document(store, project, document_id)
    return _view(store, sstore, project_id)


@router.get("/{project_id}/documents/{document_id}/download")
def download_document(project_id: str, document_id: str, store: ProjectStore = Depends(deps.store)) -> FileResponse:
    check_id(document_id, "doc", "Document")
    project = store.load(project_id)
    record = next((d for d in project.documents if d.id == document_id), None)
    if record is None:
        raise not_found("Document")
    path = store.upload_path(project_id, record.id, record.format)
    if not path.is_file():
        raise not_found("Document file")
    return FileResponse(path, media_type=MEDIA_TYPES[record.format], filename=record.filename)


@router.get("/{project_id}/documents/{document_id}/evidence", response_model=EvidenceResponse)
def document_evidence(
    project_id: str,
    document_id: str,
    block_id: str | None = None,
    page: int | None = None,
    store: ProjectStore = Depends(deps.store),
) -> EvidenceResponse:
    check_id(document_id, "doc", "Document")
    project = store.load(project_id)
    record = next((d for d in project.documents if d.id == document_id), None)
    if record is None:
        raise not_found("Document")
    if block_id is not None and (len(block_id) > 40 or not all(ch.isalnum() or ch == "-" for ch in block_id)):
        raise AppError("invalid_request", "Invalid source reference.")
    if page is not None and not (1 <= page <= 1000):
        raise AppError("invalid_request", "Invalid page number.")
    return evidence(store.upload_path(project_id, record.id, record.format), record, block_id, page)


@router.post("/{project_id}/documents/{document_id}/reuse", response_model=ProjectView, status_code=201)
def reuse_template(
    project_id: str,
    document_id: str,
    store: ProjectStore = Depends(deps.store),
    sstore: SettingsStore = Depends(deps.settings_store),
    cfg: Settings = Depends(deps.config),
) -> ProjectView:
    check_id(document_id, "doc", "Document")
    source = store.load(project_id)
    record = next((d for d in source.documents if d.id == document_id and d.role == "template"), None)
    if record is None:
        raise not_found("Template")
    data = store.upload_path(project_id, record.id, record.format).read_bytes()
    new_project = store.create("Untitled quotation")
    with store.transaction(new_project.id) as project:
        services.process_upload(store, cfg, project, "template", record.filename, data)
        store.add_event(project, "template_reused", f"Template “{record.filename}” reused from “{source.name}”")
    return _view(store, sstore, new_project.id)


# --- extraction review ---------------------------------------------------------


@router.put("/{project_id}/extraction", response_model=ProjectView)
def update_extraction(
    project_id: str,
    body: ExtractionUpdate,
    store: ProjectStore = Depends(deps.store),
    sstore: SettingsStore = Depends(deps.settings_store),
) -> ProjectView:
    with store.transaction(project_id) as project:
        if project.extraction is None:
            raise AppError("no_extraction", "Upload a tender document first.", 409)
        apply_review(project.extraction, body)
        if body.mark_reviewed:
            store.add_event(project, "extraction_reviewed", "Extracted tender data reviewed")
    return _view(store, sstore, project_id)


@router.post("/{project_id}/extraction/confirm-all", response_model=ProjectView)
def confirm_all(
    project_id: str, store: ProjectStore = Depends(deps.store), sstore: SettingsStore = Depends(deps.settings_store)
) -> ProjectView:
    with store.transaction(project_id) as project:
        count = services.confirm_all_extracted(project)
        store.add_event(project, "extraction_confirmed", f"{count} extracted values confirmed")
    return _view(store, sstore, project_id)


# --- mapping ---------------------------------------------------------------------


@router.put("/{project_id}/mapping", response_model=ProjectView)
def update_mapping(
    project_id: str,
    body: MappingUpdate,
    store: ProjectStore = Depends(deps.store),
    sstore: SettingsStore = Depends(deps.settings_store),
) -> ProjectView:
    with store.transaction(project_id) as project:
        if project.template is None or project.mapping is None:
            raise AppError("no_template", "Upload a quotation template first.", 409)
        apply_mapping_update(project.mapping, project.template, body.fields, body.columns)
    return _view(store, sstore, project_id)


@router.post("/{project_id}/mapping/confirm", response_model=ProjectView)
def confirm_mapping_route(
    project_id: str, store: ProjectStore = Depends(deps.store), sstore: SettingsStore = Depends(deps.settings_store)
) -> ProjectView:
    with store.transaction(project_id) as project:
        if project.template is None or project.mapping is None:
            raise AppError("no_template", "Upload a quotation template first.", 409)
        confirm_mapping(project.mapping)
        store.add_event(project, "mapping_confirmed", f"Field mapping confirmed ({len(project.mapping.fields)} fields)")
    return _view(store, sstore, project_id)


# --- quotation -------------------------------------------------------------------


@router.post("/{project_id}/quotation/generate", response_model=ProjectView)
def generate_quotation(
    project_id: str, store: ProjectStore = Depends(deps.store), sstore: SettingsStore = Depends(deps.settings_store)
) -> ProjectView:
    app_settings = sstore.load()
    with store.transaction(project_id) as project:
        services.generate(project, app_settings)
    return _view(store, sstore, project_id)


@router.put("/{project_id}/quotation", response_model=ProjectView)
def update_quotation(
    project_id: str,
    body: QuotationUpdate,
    store: ProjectStore = Depends(deps.store),
    sstore: SettingsStore = Depends(deps.settings_store),
) -> ProjectView:
    if not body.operations:
        raise AppError("invalid_request", "No changes were sent.")
    if len(body.operations) > 50:
        raise AppError("invalid_request", "Too many changes in one request.")
    with store.transaction(project_id) as project:
        editing.apply_manual(project, body.operations, (body.summary or "Edited in the preview")[:160])
    return _view(store, sstore, project_id)


@router.post("/{project_id}/quotation/undo", response_model=ProjectView)
def undo(
    project_id: str, store: ProjectStore = Depends(deps.store), sstore: SettingsStore = Depends(deps.settings_store)
) -> ProjectView:
    with store.transaction(project_id) as project:
        summary = editing.undo(project)
        store.add_event(project, "undo", summary)
    return _view(store, sstore, project_id)


@router.post("/{project_id}/quotation/edits", response_model=EditResult)
def propose_edit(
    project_id: str,
    body: InstructionRequest,
    store: ProjectStore = Depends(deps.store),
    sstore: SettingsStore = Depends(deps.settings_store),
    provider: AIProvider | None = Depends(deps.ai_provider),
) -> EditResult:
    app_settings = sstore.load()
    with store.transaction(project_id) as project:
        response = editing.propose(project, services.company_for(project, app_settings), body.instruction, provider)
    return EditResult(response=response, project=_view(store, sstore, project_id))


@router.post("/{project_id}/quotation/edits/{edit_id}/apply", response_model=ProjectView)
def apply_edit(
    project_id: str,
    edit_id: str,
    body: ApplyRequest,
    store: ProjectStore = Depends(deps.store),
    sstore: SettingsStore = Depends(deps.settings_store),
) -> ProjectView:
    check_id(edit_id, "edt", "Proposed change")
    with store.transaction(project_id) as project:
        proposal = editing.apply_proposal(project, edit_id, body.confirm_material)
        if not proposal.ui_only:
            store.add_event(project, "edit_applied", f"Instruction applied: {proposal.interpreted_as}")
    return _view(store, sstore, project_id)


@router.post("/{project_id}/quotation/edits/{edit_id}/cancel", response_model=ProjectView)
def cancel_edit(
    project_id: str,
    edit_id: str,
    store: ProjectStore = Depends(deps.store),
    sstore: SettingsStore = Depends(deps.settings_store),
) -> ProjectView:
    check_id(edit_id, "edt", "Proposed change")
    with store.transaction(project_id) as project:
        editing.cancel_proposal(project, edit_id)
    return _view(store, sstore, project_id)


@router.post("/{project_id}/quotation/fix", response_model=ProjectView)
def quick_fix(
    project_id: str,
    body: FixRequest,
    store: ProjectStore = Depends(deps.store),
    sstore: SettingsStore = Depends(deps.settings_store),
) -> ProjectView:
    fix = body.fix.strip()
    with store.transaction(project_id) as project:
        q = project.quotation
        if fix == "confirm_mapping":
            if project.mapping is None:
                raise AppError("no_template", "Upload a quotation template first.", 409)
            confirm_mapping(project.mapping)
            store.add_event(project, "mapping_confirmed", "Field mapping confirmed")
        else:
            if q is None:
                raise AppError("no_quotation", "Generate the quotation first.", 409)
            ops: list[EditOperation]
            if fix.startswith("set_currency:"):
                ops = [SetCurrencyOp(currency=fix.split(":", 1)[1])]
                summary = f"Currency set to {fix.split(':', 1)[1]}"
            elif fix.startswith("use_calculated_amount:"):
                item_id = fix.split(":", 1)[1]
                ops = [SetItemOp(line_item_id=item_id, attribute="amount_override", value=None)]
                summary = "Used the calculated amount"
            elif fix == "confirm_prices":
                ids = [it.id for it in q.line_items if not it.price_confirmed]
                ops = [ConfirmPricesOp(line_item_ids=ids)]
                summary = f"Confirmed {len(ids)} matched price(s)"
            elif fix == "confirm_terms":
                keys = [
                    k for k in COMMITMENT_FIELDS if k in q.fields and q.fields[k].value and not q.fields[k].confirmed
                ]
                ops = [ConfirmFieldsOp(field_keys=keys)]
                summary = "Confirmed the commercial terms"
            else:
                raise AppError("unknown_fix", "Unknown quick fix.")
            editing.apply_manual(project, ops, summary, kind="quick_fix")
            store.add_event(project, "quick_fix", summary)
    return _view(store, sstore, project_id)


@router.post("/{project_id}/validation/acknowledge", response_model=ProjectView)
def acknowledge(
    project_id: str,
    body: AcknowledgeRequest,
    store: ProjectStore = Depends(deps.store),
    sstore: SettingsStore = Depends(deps.settings_store),
) -> ProjectView:
    with store.transaction(project_id) as project:
        report = validate(project)
        if report is None or project.quotation is None:
            raise AppError("no_quotation", "Generate the quotation first.", 409)
        issue = next((i for i in report.issues if i.id == body.issue_id), None)
        if issue is None:
            raise AppError("not_found", "That finding no longer applies.", 404)
        if not issue.acknowledgeable:
            raise AppError("not_acknowledgeable", "Errors cannot be acknowledged; they must be resolved.")
        ids = set(project.quotation.acknowledged_issue_ids)
        if body.acknowledged:
            ids.add(issue.id)
        else:
            ids.discard(issue.id)
        project.quotation.acknowledged_issue_ids = sorted(ids)
        store.add_event(
            project,
            "warning_acknowledged" if body.acknowledged else "warning_reopened",
            f"{'Acknowledged' if body.acknowledged else 'Re-opened'}: {issue.title}",
        )
    return _view(store, sstore, project_id)


# --- export -----------------------------------------------------------------------


@router.post("/{project_id}/export", response_model=ExportResponse)
def export(
    project_id: str,
    body: ExportRequest,
    store: ProjectStore = Depends(deps.store),
    sstore: SettingsStore = Depends(deps.settings_store),
    cfg: Settings = Depends(deps.config),
) -> ExportResponse:
    with store.transaction(project_id) as project:
        report = validate(project)
        if report is None:
            raise AppError("no_quotation", "Generate the quotation first.", 409)
        artifact = run_export(store, cfg, project, body.format, body.draft, report)
        project.exports.append(artifact)
        store.add_event(project, "exported", f"Exported {artifact.filename} ({'draft' if artifact.draft else 'final'})")
    return ExportResponse(artifact=artifact, project=_view(store, sstore, project_id))


@router.get("/{project_id}/exports/{export_id}/download")
def download_export(project_id: str, export_id: str, store: ProjectStore = Depends(deps.store)) -> FileResponse:
    check_id(export_id, "exp", "Export")
    project = store.load(project_id)
    artifact = next((e for e in project.exports if e.id == export_id), None)
    if artifact is None:
        raise not_found("Export")
    path = store.export_path(project_id, artifact.id, artifact.format)
    if not path.is_file():
        raise not_found("Export file")
    return FileResponse(path, media_type=MEDIA_TYPES[artifact.format], filename=artifact.filename)


@router.delete("/{project_id}/exports/{export_id}", response_model=ProjectView)
def delete_export(
    project_id: str,
    export_id: str,
    store: ProjectStore = Depends(deps.store),
    sstore: SettingsStore = Depends(deps.settings_store),
) -> ProjectView:
    check_id(export_id, "exp", "Export")
    with store.transaction(project_id) as project:
        artifact = next((e for e in project.exports if e.id == export_id), None)
        if artifact is None:
            raise not_found("Export")
        store.export_path(project_id, artifact.id, artifact.format).unlink(missing_ok=True)
        project.exports = [e for e in project.exports if e.id != export_id]
        store.add_event(project, "export_deleted", f"Deleted export {artifact.filename}")
    return _view(store, sstore, project_id)


@router.get("/{project_id}/preview/docx")
def preview_docx(
    project_id: str, store: ProjectStore = Depends(deps.store), cfg: Settings = Depends(deps.config)
) -> Response:
    project = store.load(project_id)
    data = preview_docx_bytes(store, cfg, project)
    return Response(content=data, media_type=MEDIA_TYPES["docx"], headers={"Cache-Control": "no-store"})


@router.get("/{project_id}/preview/xlsx")
def preview_xlsx(
    project_id: str, store: ProjectStore = Depends(deps.store), cfg: Settings = Depends(deps.config)
) -> dict:
    project = store.load(project_id)
    return preview_xlsx_grid(store, cfg, project)
