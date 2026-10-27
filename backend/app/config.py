"""Runtime configuration, read from environment variables (see ../.env.example).

Nothing here is a secret by default. The optional AI API key is read from the environment and is never
returned by any API endpoint or written to logs.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent
APP_VERSION = "0.1.0"


def _load_branding() -> dict[str, str]:
    """Product name and tagline live in one place: ../branding.json (shared with the frontend)."""
    path = REPO_ROOT / "branding.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return {k: str(v) for k, v in data.items()}
    except (OSError, ValueError):
        return {"name": "TenderFlow", "tagline": "From tender documents to quotation-ready proposals."}


BRANDING = _load_branding()
APP_NAME = BRANDING.get("name", "TenderFlow")


def load_dotenv_files(paths: tuple[Path, ...] | None = None) -> list[Path]:
    """Load simple KEY=VALUE lines from .env files into os.environ without overriding real variables.

    Looks for ``.env`` at the repository root, then in ``backend/``. Lines starting with ``#`` and blank
    lines are ignored; values may be wrapped in single or double quotes. Only TENDERFLOW_* keys are read.
    """
    loaded: list[Path] = []
    for path in paths or (REPO_ROOT / ".env", BACKEND_DIR / ".env"):
        if not path.is_file():
            continue
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip().removeprefix("export ").strip()
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
                value = value[1:-1]
            if key.startswith("TENDERFLOW_") and key not in os.environ:
                os.environ[key] = value
        loaded.append(path)
    return loaded


def _env_path(name: str, default: Path) -> Path:
    value = os.environ.get(name, "").strip()
    return Path(value).expanduser().resolve() if value else default


def _env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return max(minimum, min(maximum, int(raw)))
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    samples_dir: Path
    frontend_dist: Path
    max_upload_mb: int
    cors_origins: list[str] = field(default_factory=list)
    ai_provider: str = ""  # "" (local rules only) or "openai_compatible"
    ai_base_url: str = ""
    ai_model: str = ""
    ai_api_key: str = field(default="", repr=False)
    ai_timeout_s: int = 20
    soffice_path: str = ""

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def ai_configured(self) -> bool:
        return self.ai_provider == "openai_compatible" and bool(self.ai_base_url) and bool(self.ai_model)


def load_settings() -> Settings:
    load_dotenv_files()
    origins = os.environ.get("TENDERFLOW_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    return Settings(
        data_dir=_env_path("TENDERFLOW_DATA_DIR", BACKEND_DIR / "data"),
        samples_dir=_env_path("TENDERFLOW_SAMPLES_DIR", REPO_ROOT / "samples"),
        frontend_dist=_env_path("TENDERFLOW_FRONTEND_DIST", REPO_ROOT / "frontend" / "dist"),
        max_upload_mb=_env_int("TENDERFLOW_MAX_UPLOAD_MB", 25, 1, 200),
        cors_origins=[o.strip() for o in origins.split(",") if o.strip()],
        ai_provider=os.environ.get("TENDERFLOW_AI_PROVIDER", "").strip().lower(),
        ai_base_url=os.environ.get("TENDERFLOW_AI_BASE_URL", "").strip().rstrip("/"),
        ai_model=os.environ.get("TENDERFLOW_AI_MODEL", "").strip(),
        ai_api_key=os.environ.get("TENDERFLOW_AI_API_KEY", "").strip(),
        ai_timeout_s=_env_int("TENDERFLOW_AI_TIMEOUT_S", 20, 2, 120),
        soffice_path=os.environ.get("TENDERFLOW_SOFFICE_PATH", "").strip(),
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return load_settings()
