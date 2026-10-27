"""Application services: the workflow operations used by the API routes.

Routes stay thin; everything here works on a loaded ``Project`` inside a store transaction.
"""

from __future__ import annotations

import json

from .config import Settings
from .editing import push_undo
from .errors import AppError
from .export import allowed_formats
from .extraction import extract_tender
from .fields import QUOTATION_FIELDS
from .ingestion import ROLE_LABELS, store_upload
from .mapping import auto_mapping, build_view
from .models import (
    REVIEWED_STATUSES,
    AppSettings,
    CompanyProfile,
    DocumentRecord,
    EditRecord,
    FieldStatus,
    Project,
    ProjectStage,
    ProjectSummary,
    ProjectView,
    QField,
    utcnow,
)
from .parsing import parse_document
from .pricing import parse_price_list
from .quotation import build_quotation, make_field
from .storage import ProjectStore, new_id
from .template_analysis import analyze_template
from .validation import validate


def company_for(project: Project, app_settings: AppSettings) -> CompanyProfile:
    return project.company if project.company is not None else app_settings.company


def document(project: Project, role: str) -> DocumentRecord | None:
    return next((d for d in project.documents if d.role == role), None)


def _remove_document(store: ProjectStore, project: Project, record: DocumentRecord) -> None:
    path = store.upload_path(project.id, record.id, record.format)
    path.unlink(missing_ok=True)
    project.documents = [d for d in project.documents if d.id != record.id]
    if record.role == "tender":
        project.extraction = None
    elif record.role == "template":
        project.template = None
        project.mapping = None
    elif record.role == "price_list":
        project.price_list = None


def process_upload(
    store: ProjectStore, settings: Settings, project: Project, role: str, filename: str | None, data: bytes
) -> DocumentRecord:
    record, _ = store_upload(store, project.id, role, filename, data, settings.max_upload_bytes)
    path = store.upload_path(project.id, record.id, record.format)
    try:
        if record.role == "template":
            analysis = analyze_template(path, record)
            record.block_count = len(analysis.fields)
            record.warnings = analysis.warnings
        else:
            parsed = parse_document(path, record.format)
            record.page_count = parsed.page_count
            record.block_count = len(parsed.blocks)
            record.table_count = len(parsed.tables)
            record.warnings = list(parsed.warnings)
    except AppError:
        path.unlink(missing_ok=True)
        raise
    except Exception as exc:
        path.unlink(missing_ok=True)
        raise AppError("unreadable_file", f"This {ROLE_LABELS[record.role].lower()} could not be read.", 422) from exc

    previous = document(project, record.role)
    if previous is not None:
        _remove_document(store, project, previous)
    project.documents.append(record)

    if record.role == "tender":
        project.extraction = extract_tender(parsed, record)
        n_fields = sum(1 for f in project.extraction.fields if f.value)
        store.add_event(
            project,
            "tender_parsed",
            f"Tender “{record.filename}” parsed: {n_fields} fields, {len(project.extraction.line_items)} line items",
        )
    elif record.role == "template":
        project.template = analysis
        project.mapping = auto_mapping(analysis)
        store.add_event(
            project,
            "template_analyzed",
            f"Template “{record.filename}” analysed: {len(analysis.fields)} destination fields"
            + (", items table found" if analysis.items_table else ", no items table"),
        )
    else:
        project.price_list = parse_price_list(parsed, record)
        record.warnings = record.warnings + project.price_list.warnings
        store.add_event(
            project,
            "price_list_parsed",
            f"Price list “{record.filename}” read: {len(project.price_list.rows)} priced rows",
        )
    return record


def remove_document(store: ProjectStore, project: Project, document_id: str) -> None:
    record = next((d for d in project.documents if d.id == document_id), None)
    if record is None:
        raise AppError("not_found", "Document was not found.", 404)
    _remove_document(store, project, record)
    store.add_event(project, "document_removed", f"{ROLE_LABELS[record.role]} “{record.filename}” removed")


def generate(project: Project, app_settings: AppSettings) -> None:
    if project.extraction is None:
        raise AppError("not_ready", "Upload a tender document first.", 409)
    if project.template is None or project.mapping is None:
        raise AppError("not_ready", "Upload a quotation template first.", 409)
    if not project.mapping.confirmed:
        raise AppError("mapping_not_confirmed", "Confirm the field mapping before generating the quotation.", 409)
    regenerating = project.quotation is not None
    if regenerating:
        push_undo(project, "Before: regenerate quotation")
    q = build_quotation(project, app_settings, company_for(project, app_settings))
    q.source_versions = _source_versions(project)
    if regenerating and project.quotation is not None:
        q.version = project.quotation.version + 1
    project.quotation = q
    for p in project.pending_edits:
        if p.status == "pending":
            p.status = "cancelled"
            p.resolved_at = utcnow()
    if regenerating:
        project.edit_history.append(
            EditRecord(
                id=new_id("rec"),
                kind="regenerate",
                summary="Quotation regenerated from the current inputs",
                engine="system",
            )
        )
    ProjectStore.add_event(
        project,
        "quotation_generated",
        f"Quotation {'re' if regenerating else ''}generated with {len(q.line_items)} line items",
    )


def _source_versions(project: Project) -> dict[str, str]:
    out: dict[str, str] = {}
    if project.extraction:
        out["extraction"] = project.extraction.updated_at.isoformat()
    for role in ("template", "price_list"):
        rec = document(project, role)
        out[role] = rec.id if rec else ""
    if project.mapping and project.mapping.confirmed_at:
        out["mapping"] = project.mapping.confirmed_at.isoformat()
    return out


def stale_reasons(project: Project) -> list[str]:
    q = project.quotation
    if q is None:
        return []
    current = _source_versions(project)
    reasons = []
    labels = {
        "extraction": "The reviewed tender data changed",
        "template": "The quotation template changed",
        "price_list": "The price list changed",
        "mapping": "The field mapping changed",
    }
    for key, label in labels.items():
        if q.source_versions.get(key, "") != current.get(key, ""):
            reasons.append(f"{label} after the quotation was generated.")
    if project.mapping is not None and not project.mapping.confirmed:
        reasons.append("The field mapping is not confirmed.")
    return reasons


def stage_of(project: Project) -> ProjectStage:
    if project.exports:
        return "export"
    if project.quotation is not None:
        return "editor"
    if document(project, "tender") is None or document(project, "template") is None:
        return "upload"
    if project.extraction is not None and not project.extraction.reviewed:
        return "extraction"
    return "mapping"


def project_view(project: Project, app_settings: AppSettings) -> ProjectView:
    mapping_view = None
    if project.template is not None and project.mapping is not None:
        values = project.quotation.fields if project.quotation is not None else _preview_fields(project, app_settings)
        mapping_view = build_view(project.mapping, project.template, values)
    return ProjectView(
        id=project.id,
        name=project.name,
        is_sample=project.is_sample,
        created_at=project.created_at,
        updated_at=project.updated_at,
        stage=stage_of(project),
        documents=project.documents,
        extraction=project.extraction,
        template=project.template,
        price_list=project.price_list,
        mapping=mapping_view,
        quotation=project.quotation,
        validation=validate(project),
        pending_edits=[p for p in project.pending_edits if p.status == "pending"],
        edit_history=list(reversed(project.edit_history[-50:])),
        undo_available=len(project.undo_stack),
        exports=list(reversed(project.exports)),
        events=list(reversed(project.events[-50:])),
        company_source="project_sample" if project.company is not None else "settings",
        stale_reasons=stale_reasons(project),
        export_formats=allowed_formats(project),
    )


def _preview_fields(project: Project, app_settings: AppSettings) -> dict[str, QField]:
    if project.extraction is None:
        return {k: make_field(k, None, "missing") for k in QUOTATION_FIELDS}
    return build_quotation(project, app_settings, company_for(project, app_settings)).fields


def project_summary(project: Project) -> ProjectSummary:
    tender = document(project, "tender")
    template = document(project, "template")
    report = validate(project)
    if project.quotation is None or report is None:
        status = "new" if not project.documents else "in_review"
    elif any(not e.draft for e in project.exports) and report.ready:
        status = "exported"
    elif report.ready:
        status = "ready"
    elif report.errors:
        status = "needs_attention"
    else:
        status = "draft"
    return ProjectSummary(
        id=project.id,
        name=project.name,
        is_sample=project.is_sample,
        created_at=project.created_at,
        updated_at=project.updated_at,
        tender_name=tender.filename if tender else None,
        template_name=template.filename if template else None,
        stage=stage_of(project),
        status=status,  # type: ignore[arg-type]
        errors=report.errors if report else None,
        warnings=report.unacknowledged_warnings if report else None,
        exports=len(project.exports),
    )


SAMPLE_FILES = {
    "tender": "sample_tender_network_equipment.pdf",
    "template": "sample_quotation_template.docx",
    "price_list": "sample_price_list.xlsx",
}


def load_sample_documents(store: ProjectStore, settings: Settings, project: Project) -> None:
    """Run the bundled sample files through the normal upload pipeline (nothing is pre-computed)."""
    for role, name in SAMPLE_FILES.items():
        path = settings.samples_dir / name
        if not path.is_file():
            raise AppError("samples_missing", "The sample files are missing from the samples/ folder.", 500)
        process_upload(store, settings, project, role, name, path.read_bytes())
    company_path = settings.samples_dir / "sample_company_profile.json"
    if company_path.is_file():
        data = json.loads(company_path.read_text(encoding="utf-8"))
        data.pop("_note", None)
        project.company = CompanyProfile.model_validate(data)
    project.is_sample = True
    store.add_event(project, "sample_loaded", "Sample documents loaded (fictional demo data)")


def mark_extraction_changed(project: Project) -> None:
    if project.extraction is not None:
        project.extraction.updated_at = utcnow()


def confirm_all_extracted(project: Project) -> int:
    ext = project.extraction
    if ext is None:
        raise AppError("no_extraction", "Upload a tender document first.", 409)
    count = 0
    for f in ext.fields:
        if f.status == FieldStatus.extracted and f.value:
            f.status = FieldStatus.confirmed
            count += 1
    for it in ext.line_items:
        if it.status == FieldStatus.extracted:
            it.status = FieldStatus.confirmed
            count += 1
    mark_extraction_changed(project)
    return count


def extraction_review_complete(project: Project) -> bool:
    ext = project.extraction
    if ext is None:
        return False
    open_fields = [f for f in ext.fields if f.required and f.status not in REVIEWED_STATUSES]
    return not open_fields
