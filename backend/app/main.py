"""FastAPI application factory.

Run in development:  uvicorn app.main:app --reload --port 8000   (from backend/)
If ``frontend/dist`` exists (``npm run build``), the built UI is served at http://localhost:8000 too.
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .api import library, projects, system
from .config import APP_NAME, APP_VERSION, Settings, get_settings
from .errors import install_error_handlers
from .storage import ProjectStore, SettingsStore

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

# Everything the UI needs is served by this origin; template previews use data: URLs (docx-preview,
# useBase64URL). 'unsafe-inline' is limited to styles: docx-preview injects <style> elements and React
# sets style attributes. FastAPI's interactive /docs page loads its assets from a CDN, so it is exempt.
CONTENT_SECURITY_POLICY = (
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
    "font-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; form-action 'self'; "
    "frame-ancestors 'none'"
)
_CSP_EXEMPT = ("/docs", "/redoc")


def create_app(settings: Settings | None = None) -> FastAPI:
    cfg = settings or get_settings()
    app = FastAPI(
        title=f"{APP_NAME} API",
        version=APP_VERSION,
        description="Tender document → reviewable quotation draft. Local-first prototype.",
    )
    app.state.config = cfg
    app.state.store = ProjectStore(cfg.data_dir)
    app.state.settings_store = SettingsStore(cfg.data_dir)
    app.state.ai_provider_override = None

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cfg.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Content-Type"],
    )

    @app.middleware("http")
    async def security_headers(request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("X-Frame-Options", "DENY")
        if not request.url.path.startswith(_CSP_EXEMPT):
            response.headers.setdefault("Content-Security-Policy", CONTENT_SECURITY_POLICY)
        return response

    install_error_handlers(app)
    app.include_router(system.router)
    app.include_router(projects.router)
    app.include_router(library.router)

    @app.get("/api/{rest:path}", include_in_schema=False)
    def api_not_found(rest: str) -> JSONResponse:
        return JSONResponse(status_code=404, content={"error": {"code": "not_found", "message": "Unknown API route."}})

    _mount_frontend(app, cfg.frontend_dist)
    return app


def _mount_frontend(app: FastAPI, dist: Path) -> None:
    index = dist / "index.html"
    if not index.is_file():
        return
    assets = dist / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/{rest:path}", include_in_schema=False)
    def spa(rest: str) -> FileResponse:
        candidate = (dist / rest).resolve()
        if rest and candidate.is_file() and dist.resolve() in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(index)


app = create_app()
