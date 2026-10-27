# Decision log

Architecture decision records (ADRs) for TenderFlow 0.1.0. Each one gives the context, the decision and its
consequences. A new dependency or a reversed decision gets a new entry (see `CLAUDE.md`).

---

### ADR-001 — Modular monolith: one FastAPI backend + one React SPA
**Context:** Hackathon timeline, a single-user local tool, and judges who need to run and read the code quickly.
**Decision:** One Python process with one module per pipeline stage; one Vite-built SPA that the backend can also serve.
**Consequences:** Simple to run (`uvicorn` + `npm run dev`, or one port after `npm run build`). Long-running work
(large PDFs, LibreOffice conversion) blocks a request rather than going through a job queue — acceptable for
single-user documents of tender size.

### ADR-002 — Rule-based extraction; AI optional and limited to edit instructions
**Context:** The brief forbids invented tender data and requires source references. LLM extraction is
non-deterministic, needs keys and network access, and cannot point to a verifiable source by itself.
**Decision:** Field specs (label regexes + a few sentence rules), table-based line items and pattern-based
requirements, all with `SourceRef`s. Weak heuristics are marked *needs review*; disagreeing values become conflicts.
The optional AI adapter only translates unrecognised edit instructions ([AI_POLICY.md](AI_POLICY.md)).
**Consequences:** Deterministic, explainable, offline. Recall is limited to common English phrasings; unusual
tenders need manual entry, which the review step supports.

### ADR-003 — pdfplumber instead of PyMuPDF
**Context:** PyMuPDF is fast and capable but licensed AGPL-3.0, which would impose AGPL terms on distribution of the
whole project, conflicting with the MIT license chosen for the repository.
**Decision:** pdfplumber (MIT, on pdfminer.six, MIT) for text, word positions and ruled-table detection.
**Consequences:** Slower on large PDFs; 300-page limit. Scanned PDFs are detected but not OCR'd.

### ADR-004 — JSON files on disk instead of a database
**Context:** One user, small data, demo laptops, and a privacy story that should be easy to verify.
**Decision:** `backend/data/projects/<id>/project.json` + `uploads/` + `exports/`, and `settings.json`. Atomic
writes (temp file + `os.replace`) under a per-project lock. IDs validated by regex before any path is built.
**Consequences:** Inspectable and trivially deletable. Not designed for concurrent users or very large projects;
moving to SQLite/Postgres would mean replacing `ProjectStore` only.

### ADR-005 — Decimal arithmetic, ROUND_HALF_UP, totals only when every line is priced
**Context:** Quotations are financial documents; floats produce rounding errors, and a "total" of a partially
priced list is misleading.
**Decision:** `Decimal` everywhere (serialised as strings), rounding to 2 dp with ROUND_HALF_UP in one place
(`app/quotation.py`). Subtotal, tax and total stay `null` while any line amount is unknown.
**Consequences:** Exact, reproducible numbers. The UI shows "—" and validation explains why a total is missing.

### ADR-006 — Never assume currency, tax or commitments
**Context:** Currency and tax depend on the seller's registration and the buyer's rules; delivery, payment, warranty
and validity terms are commitments.
**Decision:** Currency only from Settings or the user; tax only when configured; tender-stated terms are proposed
but marked unconfirmed; the tender's currency is used only to warn about mismatches.
**Consequences:** A fresh install shows errors for currency until the user chooses one (one-click quick fix
offered) — deliberate friction instead of silent assumptions.

### ADR-007 — Destination-keyed field mapping with explicit confirmation
**Context:** Templates differ; a wrong mapping silently puts data in the wrong place.
**Decision:** One mapping row per template field ("what fills this blank?"), auto-filled only for exact canonical
keys or recognised labels, editable, and confirmed by the user before generation. Any change clears the confirmation.
**Consequences:** Unfilled template fields are visible; generation is blocked until the user has looked at the mapping.

### ADR-008 — One operation model for manual edits, instructions and AI
**Context:** Three ways to change a quotation (in-place editing, rule-based instructions, optional AI) must not
diverge in validation, history or undo.
**Decision:** Every change is a list of typed `EditOperation`s applied by `apply_operations`. Instructions produce a
proposal (computed on a copy, diffed, material changes flagged) bound to the quotation version; applying needs
explicit confirmation for material changes. Undo restores snapshots (max 30).
**Consequences:** One code path to test; AI cannot do anything a user could not do, and less (no confirmations).

### ADR-009 — `frontend/.npmrc` with `legacy-peer-deps=true`
**Context:** `npm install` (npm 10) crashed with *"Cannot read properties of null (reading 'edgesOut')"* while
resolving the optional peer dependencies of vite/vitest.
**Decision:** Disable automatic peer installation for this project and list every required peer explicitly
(exact versions) in `package.json`.
**Consequences:** Installs are reliable and reproducible with the committed `package-lock.json`. Peer conflicts are
not reported automatically, so dependency upgrades must be checked with `npm ls` and the test suite.

### ADR-010 — Hash router without a router library
**Context:** Six pages and one parameterised project route (`#/p/<id>/<step>`).
**Decision:** A 100-line hash router (`src/router.ts`) with unit tests.
**Consequences:** No dependency, refresh and back button work, and the backend's SPA fallback stays trivial. Not
suitable if the app grows nested layouts or data loaders.

### ADR-011 — docx-preview for "In your template" previews, loaded lazily
**Context:** Users must see the draft inside *their* template, not only in TenderFlow's own layout.
**Decision:** The backend fills the template exactly as for export (`GET …/preview/docx`); the browser renders it
with docx-preview (Apache-2.0; uses JSZip, MIT). XLSX templates get a simple cell grid. The library is a separate
chunk loaded on first use.
**Consequences:** Faithful content, approximate layout (stated in the UI). Main bundle stays smaller.

### ADR-012 — Bundled fonts (Fontsource) and lucide-react icons
**Context:** The Figma export loaded DM Sans and Manrope from Google Fonts and drew icons as inline SVG paths.
**Decision:** `@fontsource-variable/dm-sans` and `@fontsource-variable/manrope` (SIL OFL 1.1) are bundled;
icons come from lucide-react (ISC).
**Consequences:** No third-party requests (privacy, offline demos, strict CSP); consistent, accessible icons.

### ADR-013 — Replace the Figma export's Git LFS `.gitattributes`
**Context:** The Figma Make export routed many file types through Git LFS, which would break cloning for anyone
without LFS and is unnecessary for a small repository.
**Decision:** A plain `.gitattributes` (`* text=auto eol=lf`, binary types marked binary).
**Consequences:** Normal git workflow. Sample binaries (PDF/DOCX/XLSX) are small and committed directly.

### ADR-014 — Readable type sizes and AA contrast instead of the Figma values
**Context:** The Figma export used 5–11 px text in many places and `#77727E` secondary text, which measures 4.34:1
on the page background and 3.97:1 on lavender surfaces (below WCAG AA 4.5:1).
**Decision:** Keep the palette and layout but use a readable type scale: 14 px body, 12.5–13 px secondary text,
11.5 px badges and eyebrows. Micro-labels (keyboard hints, origin chips, evidence locations, column labels inside
the printed-quotation preview) are 10.5–11 px, and the miniature template thumbnail uses 10 px. The same elements
were 5–9 px in the export. Secondary text is darkened to `#6B6672` (≥ 4.7:1 on all light surfaces).
**Consequences:** Denser screens than the mock-up at small widths; responsive breakpoints (1500/1200/1050/760 px)
compensate.

### ADR-015 — Product name in one place (`branding.json`)
**Context:** The name may change before submission.
**Decision:** `branding.json` at the root holds name and taglines; the backend (`config.py`) and frontend
(`src/config.ts`) both read it.
**Consequences:** Renaming is a one-file change (plus prose in docs).

### ADR-016 — PDF export via LibreOffice when available
**Context:** Users need PDF, but no permissively licensed pure-Python library renders DOCX/XLSX to PDF faithfully.
**Decision:** Convert the filled DOCX/XLSX with `soffice --headless` (temporary profile, timeout) when LibreOffice
is found; otherwise the PDF option is disabled with an explanation (`/api/health` → `pdf_export`).
**Consequences:** PDF depends on a local install; the test for it runs only when `soffice` exists.

### ADR-017 — Minimal built-in `.env` loader instead of python-dotenv
**Context:** Only a handful of `TENDERFLOW_*` variables; every dependency needs a license and update check.
**Decision:** ~20 lines in `config.py`: reads `KEY=VALUE` lines from the root and `backend/` `.env`, only
`TENDERFLOW_*` keys, never overriding real environment variables. Unit-tested.
**Consequences:** No multi-line values or variable expansion — not needed here.

### ADR-018 — OpenAI-compatible adapter with deterministic guards and minimal context
**Context:** Some teams may want free-form instructions; the brief forbids sending documents without explicit
configuration and forbids invented numbers.
**Decision:** One adapter for any `/chat/completions` endpoint (hosted or local such as Ollama), enabled only by
environment configuration **and** a Settings switch. It receives a minimal context (no company or personal details,
no files) and its JSON passes allow-list, ID and number-provenance checks; results are proposals.
**Consequences:** Useful flexibility with bounded risk. Tested with a mocked transport only — see
[KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md).

### ADR-019 — Drafts are always allowed but labelled; final export requires *ready*
**Context:** Users need to share work in progress, but an unvalidated quotation must not look final.
**Decision:** Draft exports carry `_DRAFT` in the filename and a banner ("DRAFT - generated by TenderFlow for
internal review. Not for submission.") or XLSX print header; final exports are refused unless validation is ready.
**Consequences:** No silent submission of unchecked documents; users must remove nothing by hand for finals.

### ADR-020 — Node.js 22.22.2+ / 24.15+
**Context:** The pinned test stack (Vitest 5, jsdom 30.1.1) declares `node: ^22.22.2 || ^24.15.0 || >=26`.
**Decision:** Keep the current versions, state the requirement in the README and in `package.json` `engines`.
**Consequences:** Teams on older Node 22 releases must update Node to run `npm test` (build and dev server work
from 20.19+/22.12+).

### ADR-021 — Strict Content-Security-Policy
**Context:** The app renders text from untrusted documents and runs docx-preview on generated files.
**Decision:** `default-src 'self'; script-src 'self'; …` on every response except FastAPI's `/docs`;
`'unsafe-inline'` only for styles (docx-preview injects `<style>`, React sets style attributes); `data:` for
images/fonts (docx-preview `useBase64URL`). The E2E run fails on any console error, including CSP violations.
**Consequences:** Defence in depth against script injection; new third-party assets would need a policy change.

### ADR-022 — Rely on expat's amplification limits instead of adding defusedxml
**Context:** openpyxl only uses defusedxml if installed; uploads are untrusted.
**Decision:** Python's bundled expat (2.4.1+, 2.9.0 in testing) rejects entity amplification, and python-docx
disables entity resolution. A regression test uploads "billion laughs" XLSX and DOCX files.
**Consequences:** No extra dependency. If deployed on a Python built against an old system expat, add defusedxml.

### ADR-023 — Patched Vite and a narrow dev-server file allow-list
**Context:** `npm audit` flagged Vite 8.0.5 (dev server only) for file-serving and cross-origin advisories; the
dev config also allowed serving the whole repository (`fs.allow: ['..']`), which includes `backend/data`.
**Decision:** Vite 8.3.4 (latest patched release more than two weeks old at the time) and
`fs.allow: [frontend/, ../branding.json]`. Verified: the dev server returns 403 for backend files.
**Consequences:** `npm audit` reports 0 vulnerabilities (as of 2026-10-27). Keep Vite patched.

### ADR-024 — Remove the Figma export's simulated data and controls
**Context:** The Figma Make export contained a fictional user ("Amina Malik"), workspace, statistics, activity,
search, notification and profile controls, and simulated processing.
**Decision:** Keep every screen and its visual language, wire each one to real backend data, and remove controls
that had no real function. An unrelated design brief bundled in the export (`silgrid-design-brief.md`) was not used.
**Consequences:** Everything visible works; empty states explain how to get data instead of showing fake numbers.
