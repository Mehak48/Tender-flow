"""PDF export through LibreOffice (``soffice --headless --convert-to pdf``), only when it is installed.

If LibreOffice is not available the API reports PDF as unavailable instead of pretending; DOCX/XLSX
export keeps working.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from ..config import Settings
from ..errors import AppError

COMMON_PATHS = [
    r"C:\Program Files\LibreOffice\program\soffice.exe",
    r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
    "/Applications/LibreOffice.app/Contents/MacOS/soffice",
    "/usr/bin/soffice",
    "/usr/local/bin/soffice",
]


def find_soffice(settings: Settings) -> str | None:
    if settings.soffice_path and Path(settings.soffice_path).is_file():
        return settings.soffice_path
    for name in ("soffice", "libreoffice"):
        found = shutil.which(name)
        if found:
            return found
    for candidate in COMMON_PATHS:
        if Path(candidate).is_file():
            return candidate
    return None


def pdf_status(settings: Settings) -> dict[str, object]:
    path = find_soffice(settings)
    if path:
        return {"available": True, "reason": "LibreOffice found; PDF is converted from the generated document."}
    return {
        "available": False,
        "reason": "PDF export needs LibreOffice installed on the computer running the backend "
        "(or TENDERFLOW_SOFFICE_PATH). DOCX/XLSX export works without it.",
    }


def convert_to_pdf(source: Path, out_path: Path, settings: Settings, timeout_s: int = 120) -> Path:
    soffice = find_soffice(settings)
    if soffice is None:
        raise AppError("pdf_unavailable", str(pdf_status(settings)["reason"]), 422)
    with tempfile.TemporaryDirectory(prefix="tf-pdf-") as work, tempfile.TemporaryDirectory(prefix="tf-lo-") as profile:
        work_dir = Path(work)
        src_copy = work_dir / f"quotation{source.suffix}"
        shutil.copyfile(source, src_copy)
        cmd = [
            soffice,
            f"-env:UserInstallation={Path(profile).resolve().as_uri()}",
            "--headless",
            "--norestore",
            "--nolockcheck",
            "--convert-to",
            "pdf",
            "--outdir",
            str(work_dir),
            str(src_copy),
        ]
        env = {**os.environ, "HOME": profile}
        try:
            subprocess.run(cmd, capture_output=True, timeout=timeout_s, check=False, env=env)
        except (subprocess.TimeoutExpired, OSError) as exc:
            raise AppError(
                "pdf_failed", "PDF conversion did not finish. Use the DOCX/XLSX export instead.", 500
            ) from exc
        produced = work_dir / "quotation.pdf"
        if not produced.is_file() or produced.stat().st_size == 0:
            raise AppError("pdf_failed", "LibreOffice did not produce a PDF. Use the DOCX/XLSX export instead.", 500)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(produced), out_path)
    return out_path
