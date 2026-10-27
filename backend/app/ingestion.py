"""Upload validation and safe storage (pipeline stage 1: ingestion).

Checks, in order: role, extension allow-list, size limit, non-empty, magic bytes / container structure
(including a zip-bomb guard for DOCX/XLSX), then stores the bytes under a generated ID. The original
filename is sanitised and kept only as display metadata.
"""

from __future__ import annotations

import hashlib
import io
import re
import unicodedata
import zipfile
from pathlib import PurePosixPath, PureWindowsPath

from .errors import AppError
from .models import DocumentFormat, DocumentRecord, DocumentRole
from .storage import ProjectStore, new_id

ALLOWED_FORMATS: dict[DocumentRole, tuple[DocumentFormat, ...]] = {
    "tender": ("pdf", "docx"),
    "template": ("docx", "xlsx"),
    "price_list": ("xlsx", "csv"),
}

ROLE_LABELS: dict[DocumentRole, str] = {
    "tender": "Tender document",
    "template": "Quotation template",
    "price_list": "Price list",
}

LEGACY_HINTS = {
    "doc": "Legacy .doc files are not supported. Save the file as .docx and upload it again.",
    "xls": "Legacy .xls files are not supported. Save the file as .xlsx and upload it again.",
    "rtf": "RTF files are not supported. Save the file as .docx and upload it again.",
    "odt": "OpenDocument files are not supported. Save the file as .docx and upload it again.",
    "png": "Images are not supported. TenderFlow does not perform OCR in this prototype.",
    "jpg": "Images are not supported. TenderFlow does not perform OCR in this prototype.",
    "jpeg": "Images are not supported. TenderFlow does not perform OCR in this prototype.",
}

MAX_ZIP_ENTRIES = 5000
MAX_ZIP_UNCOMPRESSED = 300 * 1024 * 1024  # 300 MB uncompressed: generous for office files, blocks zip bombs


def sanitize_filename(name: str | None) -> str:
    """Return a display-safe filename: basename only, no control characters, bounded length."""
    raw = (name or "").strip()
    # Strip any directory part, whichever separator style the client used.
    raw = PureWindowsPath(PurePosixPath(raw).name).name
    raw = unicodedata.normalize("NFKC", raw)
    raw = "".join(ch for ch in raw if unicodedata.category(ch)[0] != "C")
    raw = re.sub(r"[^\w\s.\-()&,+@]", "_", raw, flags=re.UNICODE)
    raw = re.sub(r"\s+", " ", raw).strip(" .")
    if not raw:
        raw = "document"
    if len(raw) > 120:
        stem, dot, ext = raw.rpartition(".")
        raw = (stem[:110] + dot + ext[:8]) if dot else raw[:120]
    return raw


def detect_extension(filename: str) -> str:
    suffix = PurePosixPath(filename).suffix.lower().lstrip(".")
    return suffix


def _check_zip_container(data: bytes, required_member: str, label: str) -> None:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            infos = zf.infolist()
            if len(infos) > MAX_ZIP_ENTRIES:
                raise AppError("unsafe_file", f"This {label} file has an unusual structure and was rejected.")
            total = sum(i.file_size for i in infos)
            if total > MAX_ZIP_UNCOMPRESSED:
                raise AppError("unsafe_file", f"This {label} file expands to an unsafe size and was rejected.")
            names = {i.filename for i in infos}
    except zipfile.BadZipFile as exc:
        raise AppError("malformed_file", f"This file is not a valid {label} document (it may be corrupted).") from exc
    if "[Content_Types].xml" not in names or required_member not in names:
        raise AppError("malformed_file", f"This file is not a valid {label} document.")


def validate_content(fmt: DocumentFormat, data: bytes) -> None:
    if fmt == "pdf":
        if not data[:1024].lstrip().startswith(b"%PDF-"):
            raise AppError("malformed_file", "This file does not look like a PDF (missing PDF header).")
    elif fmt == "docx":
        _check_zip_container(data, "word/document.xml", "Word (.docx)")
    elif fmt == "xlsx":
        _check_zip_container(data, "xl/workbook.xml", "Excel (.xlsx)")
    elif fmt == "csv":
        if b"\x00" in data[:65536]:
            raise AppError("malformed_file", "This CSV file contains binary data.")
        try:
            data.decode("utf-8-sig")
        except UnicodeDecodeError:
            try:
                data.decode("cp1252")
            except UnicodeDecodeError as exc:
                raise AppError("malformed_file", "This CSV file is not valid UTF-8 or Windows-1252 text.") from exc


def validate_upload(
    role: str, filename: str | None, data: bytes, max_bytes: int
) -> tuple[DocumentRole, str, DocumentFormat]:
    if role not in ALLOWED_FORMATS:
        raise AppError("invalid_role", "Unknown document role. Use tender, template or price_list.")
    doc_role: DocumentRole = role
    safe_name = sanitize_filename(filename)
    ext = detect_extension(safe_name)
    allowed = ALLOWED_FORMATS[doc_role]
    if ext not in allowed:
        hint = LEGACY_HINTS.get(ext)
        allowed_text = ", ".join(f".{a}" for a in allowed)
        message = hint or f"{ROLE_LABELS[doc_role]} must be one of: {allowed_text}."
        raise AppError("unsupported_format", message, 415)
    if len(data) > max_bytes:
        raise AppError("file_too_large", f"The file is larger than the {max_bytes // (1024 * 1024)} MB limit.", 413)
    if len(data) == 0:
        raise AppError("empty_file", "The file is empty.")
    fmt: DocumentFormat = ext
    validate_content(fmt, data)
    return doc_role, safe_name, fmt


def store_upload(
    store: ProjectStore, project_id: str, role: str, filename: str | None, data: bytes, max_bytes: int
) -> tuple[DocumentRecord, bytes]:
    doc_role, safe_name, fmt = validate_upload(role, filename, data, max_bytes)
    record = DocumentRecord(
        id=new_id("doc"),
        role=doc_role,
        filename=safe_name,
        format=fmt,
        size_bytes=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
    )
    path = store.upload_path(project_id, record.id, fmt)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "xb") as fh:  # "x": never overwrite an existing file
        fh.write(data)
    return record, data
