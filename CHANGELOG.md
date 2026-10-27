# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/).

## [0.1.0] — 2026-10-27

First version, prepared for Hacktoberfest Hackathon NUST × NSTP 2026. There are no earlier releases.

### Added

- Upload of tender (PDF/DOCX), quotation template (DOCX/XLSX) and optional price list (XLSX/CSV) with validation.
- Page-aware PDF parsing and DOCX/XLSX/CSV parsing with source locations.
- Rule-based extraction of tender fields, line items and requirements, with conflict detection and an
  instruction-like-text (prompt-injection) detector.
- Extraction review with a verbatim source-evidence panel.
- Template analysis (placeholders, label blanks, items table) and confirmable field mapping.
- Quotation generation with Decimal arithmetic and price-list matching that never estimates prices.
- Three-panel editor with in-place editing, value-origin markers, a rule-based natural-language instruction
  parser with previews, confirmation of material changes, undo and history.
- Optional OpenAI-compatible AI adapter (off by default; unit-tested with a mocked transport only).
- 19 deterministic validation rules with acknowledgement and quick fixes.
- DOCX/XLSX export into the user's template with post-export verification; PDF export via LibreOffice when installed.
- Project list, template library, document library, activity log and settings (company, currency, tax, data deletion).
- Fictional sample documents and generator, 96 backend tests, 30 frontend tests and a 14-step Playwright
  end-to-end script (including the in-browser template and export previews).
- Project documentation in `docs/`.

### Security

- Content-Security-Policy, `X-Frame-Options`, `X-Content-Type-Options` and `Referrer-Policy` headers.
- Upload guards for zip bombs and XML entity ("billion laughs") bombs, with regression tests.
- The optional AI provider never receives company or personal details and cannot change them, derived values or
  the signature.
- Vite 8.3.4 (dev server advisories fixed in Vite > 8.1.5) and a dev-server file allow-list limited to the
  frontend folder and `branding.json`. `npm audit`: 0 known vulnerabilities at release.
