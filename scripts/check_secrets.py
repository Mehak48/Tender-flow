#!/usr/bin/env python3
"""Scan the repository for files and patterns that look like committed secrets or private data.

Usage (from the repository root):  python scripts/check_secrets.py
Exit code 0 = nothing suspicious found, 1 = findings printed. A basic check, not a replacement for a full
secret scanner such as gitleaks.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "dist", "data", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
TEXT_SUFFIXES = {
    ".py", ".ts", ".tsx", ".js", ".cjs", ".mjs", ".json", ".md", ".txt", ".toml", ".yaml", ".yml", ".cfg", ".ini",
    ".env", ".example", ".html", ".css", ".csv", ".sh", ".ps1",
}
FORBIDDEN_FILES = {".env", "id_rsa", "id_ed25519", "credentials.json"}

PATTERNS = [
    ("private key block", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----")),
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("OpenAI/Anthropic-style key", re.compile(r"\bsk-(?:ant-)?[A-Za-z0-9_\-]{20,}\b")),
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b")),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b")),
    ("Slack token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b")),
    (
        "hard-coded secret assignment",
        re.compile(r"""(?i)\b(api[_-]?key|secret|password|token)\b\s*[:=]\s*["'][^"'\s]{16,}["']"""),
    ),
]
# Test files may contain obviously fake values; they are listed here explicitly.
ALLOWLIST = {("backend/tests/test_ai_adapter.py", "OpenAI/Anthropic-style key")}


def main() -> int:
    findings: list[str] = []
    for path in ROOT.rglob("*"):
        rel = path.relative_to(ROOT)
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        if path.is_file() and path.name in FORBIDDEN_FILES:
            findings.append(f"{rel}: file must not be committed")
            continue
        if not path.is_file() or (path.suffix not in TEXT_SUFFIXES and path.name not in {".env.example"}):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for name, rx in PATTERNS:
            for m in rx.finditer(text):
                if (rel.as_posix(), name) in ALLOWLIST:
                    continue
                line = text.count("\n", 0, m.start()) + 1
                findings.append(f"{rel}:{line}: possible {name}")
    if findings:
        print("Possible secrets found:")
        print("\n".join(f"  - {f}" for f in findings))
        return 1
    print("No secrets or forbidden files found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
