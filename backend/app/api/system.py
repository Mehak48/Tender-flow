"""Health, settings, sample project and local data deletion."""

from __future__ import annotations

import re

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response

from .. import services
from ..ai import provider_status
from ..config import APP_NAME, APP_VERSION, BRANDING, Settings
from ..errors import AppError
from ..export.pdf_export import pdf_status
from ..extraction.normalize import SUPPORTED_CURRENCIES
from ..ingestion import ALLOWED_FORMATS
from ..models import AppSettings, CompanyProfile, Model, ProjectView, TaxSettings
from ..storage import ProjectStore, SettingsStore
from . import deps

router = APIRouter(prefix="/api", tags=["system"])


class SettingsUpdate(Model):
    company: CompanyProfile
    default_currency: str | None = None
    tax: TaxSettings
    quotation_prefix: str = "QTN"
    use_external_ai: bool = False


class SettingsView(Model):
    settings: AppSettings
    supported_currencies: list[str]
    ai: dict
    pdf_export: dict


@router.get("/health")
def health(cfg: Settings = Depends(deps.config), sstore: SettingsStore = Depends(deps.settings_store)) -> dict:
    app_settings = sstore.load()
    return {
        "status": "ok",
        "app_name": APP_NAME,
        "tagline": BRANDING.get("tagline"),
        "version": APP_VERSION,
        "ai": provider_status(cfg, app_settings),
        "pdf_export": pdf_status(cfg),
        "limits": {
            "max_upload_mb": cfg.max_upload_mb,
            "formats": {role: list(fmts) for role, fmts in ALLOWED_FORMATS.items()},
        },
        "currencies": list(SUPPORTED_CURRENCIES),
        "ocr": False,
        "storage": "local filesystem (backend data folder)",
    }


@router.get("/settings", response_model=SettingsView)
def get_settings(
    cfg: Settings = Depends(deps.config), sstore: SettingsStore = Depends(deps.settings_store)
) -> SettingsView:
    s = sstore.load()
    return SettingsView(
        settings=s,
        supported_currencies=list(SUPPORTED_CURRENCIES),
        ai=provider_status(cfg, s),
        pdf_export=pdf_status(cfg),
    )


def _clean(value: str | None, limit: int = 300) -> str | None:
    if value is None:
        return None
    v = " ".join(str(value).replace("\r", "").split(" ")).strip()
    return v[:limit] or None


@router.put("/settings", response_model=SettingsView)
def put_settings(
    body: SettingsUpdate, cfg: Settings = Depends(deps.config), sstore: SettingsStore = Depends(deps.settings_store)
) -> SettingsView:
    currency = (body.default_currency or "").strip().upper() or None
    if currency is not None and currency not in SUPPORTED_CURRENCIES:
        raise AppError("invalid_currency", "Choose one of the supported currencies.")
    if body.tax.rate is not None and not (0 <= body.tax.rate <= 100):
        raise AppError("invalid_number", "Tax rate must be between 0 and 100 percent.")
    if body.tax.enabled and body.tax.rate is None:
        raise AppError("invalid_tax", "Enter a tax rate, or turn tax off.")
    prefix = body.quotation_prefix.strip() or "QTN"
    if not re.fullmatch(r"[A-Za-z0-9-]{1,12}", prefix):
        raise AppError("invalid_prefix", "The quotation prefix may contain letters, digits and hyphens (max 12).")
    company = CompanyProfile(**{k: _clean(v) for k, v in body.company.model_dump().items()})
    tax = TaxSettings(
        enabled=body.tax.enabled, label=_clean(body.tax.label, 40), rate=body.tax.rate if body.tax.enabled else None
    )
    saved = sstore.save(
        AppSettings(
            company=company,
            default_currency=currency,
            tax=tax,
            quotation_prefix=prefix,
            use_external_ai=body.use_external_ai,
        )
    )
    return SettingsView(
        settings=saved,
        supported_currencies=list(SUPPORTED_CURRENCIES),
        ai=provider_status(cfg, saved),
        pdf_export=pdf_status(cfg),
    )


@router.post("/demo/project", response_model=ProjectView, status_code=201)
def create_sample_project(
    store: ProjectStore = Depends(deps.store),
    sstore: SettingsStore = Depends(deps.settings_store),
    cfg: Settings = Depends(deps.config),
) -> ProjectView:
    project = store.create("Sample: IT network equipment tender", is_sample=True)
    try:
        with store.transaction(project.id) as p:
            services.load_sample_documents(store, cfg, p)
    except AppError:
        store.delete(project.id)
        raise
    return services.project_view(store.load(project.id), sstore.load())


@router.delete("/data", status_code=204)
def delete_all_data(
    confirm: str = Query(""),
    store: ProjectStore = Depends(deps.store),
    sstore: SettingsStore = Depends(deps.settings_store),
) -> Response:
    if confirm != "DELETE":
        raise AppError("confirmation_required", "Type DELETE to confirm deleting all local data.")
    store.delete_all()
    sstore.delete()
    return Response(status_code=204)
