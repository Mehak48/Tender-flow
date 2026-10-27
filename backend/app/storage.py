"""Local filesystem persistence.

Layout (under ``TENDERFLOW_DATA_DIR``, default ``backend/data``)::

    settings.json
    projects/<project_id>/project.json
    projects/<project_id>/uploads/<document_id>.<ext>
    projects/<project_id>/exports/<export_id>.<ext>

All paths are built from generated IDs that are validated against a strict pattern, so user input can
never be used to construct a path (no traversal, no overwriting unrelated files).
"""

from __future__ import annotations

import json
import os
import re
import secrets
import shutil
import tempfile
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from .errors import AppError, not_found
from .models import ActivityEvent, AppSettings, Project, utcnow

_ID_RE = {
    prefix: re.compile(rf"^{prefix}_[0-9a-f]{{12}}$") for prefix in ("prj", "doc", "exp", "edt", "evt", "itm", "rec")
}


def new_id(prefix: str) -> str:
    if prefix not in _ID_RE:
        raise ValueError(f"unknown id prefix {prefix}")
    return f"{prefix}_{secrets.token_hex(6)}"


def check_id(value: str, prefix: str, what: str) -> str:
    if not isinstance(value, str) or not _ID_RE[prefix].match(value):
        raise not_found(what)
    return value


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


class ProjectStore:
    MAX_EVENTS = 200

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.root = data_dir / "projects"
        self.root.mkdir(parents=True, exist_ok=True)
        self._locks: dict[str, threading.RLock] = {}
        self._locks_guard = threading.Lock()

    # -- paths ---------------------------------------------------------------
    def project_dir(self, project_id: str) -> Path:
        check_id(project_id, "prj", "Project")
        return self.root / project_id

    def upload_path(self, project_id: str, document_id: str, extension: str) -> Path:
        check_id(document_id, "doc", "Document")
        if not re.fullmatch(r"[a-z]{3,4}", extension):
            raise AppError("invalid_extension", "Unsupported file extension.")
        return self.project_dir(project_id) / "uploads" / f"{document_id}.{extension}"

    def export_path(self, project_id: str, export_id: str, extension: str) -> Path:
        check_id(export_id, "exp", "Export")
        if extension not in ("docx", "xlsx", "pdf"):
            raise AppError("invalid_extension", "Unsupported export format.")
        return self.project_dir(project_id) / "exports" / f"{export_id}.{extension}"

    # -- locking -------------------------------------------------------------
    def _lock_for(self, project_id: str) -> threading.RLock:
        with self._locks_guard:
            return self._locks.setdefault(project_id, threading.RLock())

    @contextmanager
    def transaction(self, project_id: str) -> Iterator[Project]:
        """Load a project under its lock, yield it for modification and save it afterwards."""
        lock = self._lock_for(check_id(project_id, "prj", "Project"))
        with lock:
            project = self.load(project_id)
            yield project
            project.updated_at = utcnow()
            self.save(project)

    # -- CRUD ----------------------------------------------------------------
    def create(self, name: str, is_sample: bool = False) -> Project:
        project = Project(id=new_id("prj"), name=name, is_sample=is_sample)
        (self.project_dir(project.id) / "uploads").mkdir(parents=True, exist_ok=True)
        (self.project_dir(project.id) / "exports").mkdir(parents=True, exist_ok=True)
        self.add_event(project, "project_created", f"Project “{name}” created")
        self.save(project)
        return project

    def load(self, project_id: str) -> Project:
        path = self.project_dir(project_id) / "project.json"
        if not path.is_file():
            raise not_found("Project")
        try:
            return Project.model_validate_json(path.read_text(encoding="utf-8"))
        except ValueError as exc:
            raise AppError("corrupt_project", "This project's data file could not be read.", 500) from exc

    def save(self, project: Project) -> None:
        path = self.project_dir(project.id) / "project.json"
        _atomic_write_text(path, project.model_dump_json(indent=1))

    def list(self) -> list[Project]:
        projects: list[Project] = []
        for child in sorted(self.root.iterdir()) if self.root.exists() else []:
            if not child.is_dir() or not _ID_RE["prj"].match(child.name):
                continue
            try:
                projects.append(self.load(child.name))
            except AppError:
                continue  # skip unreadable projects instead of failing the whole list
        projects.sort(key=lambda p: p.updated_at, reverse=True)
        return projects

    def delete(self, project_id: str) -> None:
        directory = self.project_dir(project_id)
        if not directory.is_dir():
            raise not_found("Project")
        with self._lock_for(project_id):
            shutil.rmtree(directory)

    def delete_all(self) -> int:
        count = 0
        for child in list(self.root.iterdir()) if self.root.exists() else []:
            if child.is_dir() and _ID_RE["prj"].match(child.name):
                shutil.rmtree(child)
                count += 1
        return count

    # -- helpers -------------------------------------------------------------
    @classmethod
    def add_event(cls, project: Project, kind: str, message: str) -> None:
        project.events.append(ActivityEvent(id=new_id("evt"), kind=kind, message=message))
        if len(project.events) > cls.MAX_EVENTS:
            project.events = project.events[-cls.MAX_EVENTS :]


class SettingsStore:
    def __init__(self, data_dir: Path) -> None:
        self.path = data_dir / "settings.json"
        self._lock = threading.Lock()

    def load(self) -> AppSettings:
        if not self.path.is_file():
            return AppSettings()
        try:
            return AppSettings.model_validate(json.loads(self.path.read_text(encoding="utf-8")))
        except ValueError:
            return AppSettings()

    def save(self, settings: AppSettings) -> AppSettings:
        with self._lock:
            settings.updated_at = utcnow()
            _atomic_write_text(self.path, settings.model_dump_json(indent=1))
        return settings

    def delete(self) -> None:
        with self._lock:
            self.path.unlink(missing_ok=True)
