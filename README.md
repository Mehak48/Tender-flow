# TenderFlow

**From tender documents to quotation-ready proposals.**

TenderFlow reads a tender document you already have, shows you exactly what it found (with the page and
line it came from), lets you map that data into **your own quotation template**, and produces a draft you can
edit in plain language, check with deterministic validation, and export as DOCX / XLSX (and PDF when LibreOffice
is installed). It prepares drafts for human review — it never submits bids or makes commitments for you.

> Hackathon prototype built for **Hacktoberfest Hackathon NUST × NSTP 2026**. Local-first: documents stay on the
> computer running the backend. No AI key is needed.

---

## Contents

- [The problem](#the-problem) · [The solution](#the-solution) · [Feature status](#feature-status)
- [Screenshots](#screenshots) · [Architecture](#architecture) · [Technology](#technology-stack)
- [Install & run](#install--run) · [Configuration](#configuration) · [Demo workflow](#demo-workflow)
- [Supported files & template conventions](#supported-files--template-conventions)
- [Security & privacy](#security--privacy) · [Known limitations](#known-limitations) · [Testing](#testing)
- [License](#license) · [Attribution](#attribution--acknowledgements) · [Contributing](#contributing) · [Roadmap](#roadmap) · [Team](#team)

## The problem

Tenders arrive as long documents full of line items, quantities, specifications, deadlines, commercial terms and
eligibility rules. To answer one, staff read the whole thing, copy the relevant parts into their own quotation
template, check the figures and chase missing details. It is slow, and transcription errors and omissions are easy
to make.

## The solution

1. **Upload** the tender (PDF/DOCX), your quotation template (DOCX/XLSX) and optionally your price list (XLSX/CSV).
2. **Review** the extracted data. Every value links to its source location; conflicts and gaps are flagged, never guessed.
3. **Map** quotation data to the fields of *your* template (placeholders, “Label: ____” blanks, items table).
4. **Edit** the draft directly or with instructions such as *“Change the delivery period to 30 days.”* — you always see a before/after preview first, money and commitment changes need explicit confirmation, and Undo is available.
5. **Validate & export.** Plain-code checks (arithmetic, totals, missing values, unconfirmed commitments, currency, tax…) run on every change. Export fills your template; the uploaded original is never modified.

**What makes it different:** user-owned templates · source-linked extraction · explicit field mapping ·
previewed natural-language edits · deterministic validation · honest handling of missing data ·
fully open source and runnable without any AI service. (Other tender tools exist; TenderFlow's focus is a
trustworthy, reviewable workflow.)

## Feature status

| Area | Status | Notes |
|---|---|---|
| Upload with drag & drop, type/size/signature checks | ✅ Implemented | PDF, DOCX, XLSX, CSV; 25 MB default limit; zip-bomb guard |
| PDF parsing (page-aware, ruled tables) | ✅ Implemented | pdfplumber; scanned pages are detected and reported (no OCR) |
| DOCX / XLSX / CSV parsing | ✅ Implemented | paragraph / table / row / cell references |
| Rule-based extraction with source references | ✅ Implemented | reference, title, issuer, dates, terms, currency, tax wording, line items, requirements |
| Conflict detection | ✅ Implemented | e.g. two different submission deadlines |
| Instruction-like text (prompt-injection) detection | ✅ Implemented | basic pattern check; text is always treated as data |
| Extraction review (confirm / edit / choose / add items) | ✅ Implemented | with a verbatim source-evidence panel |
| Template analysis (DOCX & XLSX) | ✅ Implemented | `{{placeholders}}`, label blanks, items table detection |
| Field mapping with confirmation | ✅ Implemented | required/optional, unfilled destinations, unused sources |
| Price list matching | ✅ Implemented | name matching; fuzzy matches need confirmation; never estimates |
| Quotation generation + Decimal arithmetic | ✅ Implemented | ROUND_HALF_UP to 2 dp; totals only when every line is priced |
| Natural-language edits (local rules) | ✅ Implemented | fixed set of instruction patterns (13 documented examples), preview, material-change confirmation, undo |
| Optional AI provider (OpenAI-compatible) | ⚠️ Implemented, **not tested against a live provider** | unit-tested with a mocked transport; off by default |
| Deterministic validation (19 rules) | ✅ Implemented | errors vs warnings, acknowledgement, quick fixes |
| DOCX / XLSX export with post-export verification | ✅ Implemented | re-opened and checked; original template hash verified |
| PDF export | ✅ When LibreOffice is installed | otherwise disabled with an explanation |
| Template-faithful preview in the browser | ✅ Implemented | DOCX via docx-preview (approximate rendering); XLSX cell grid |
| Projects, templates, document library, activity log | ✅ Implemented | stored as files on disk |
| Settings (company, currency, tax, AI status, delete all data) | ✅ Implemented | no currency or tax rate is ever assumed |
| OCR, authentication, multi-user, cloud deployment | ❌ Not implemented | out of scope for the prototype |

## Screenshots

Real screenshots captured by the end-to-end script (`scripts/e2e_demo.cjs`) running the fictional sample project.

| | |
|---|---|
| ![Overview](docs/screenshots/01-overview.png) Overview | ![Extraction review with source evidence](docs/screenshots/02-extraction-review.png) Extraction review + source evidence |
| ![Field mapping](docs/screenshots/03-mapping.png) Field mapping | ![Three-panel editor](docs/screenshots/04-editor.png) Three-panel editor |
| ![Instruction preview](docs/screenshots/05-instruction-preview.png) Instruction preview & confirmation | ![Validation](docs/screenshots/06-validation.png) Validation workspace |
| ![Export](docs/screenshots/07-export.png) Verified export | ![Upload](docs/screenshots/08-upload.png) Upload step |
| ![Draft in your template](docs/screenshots/11-template-preview.png) Draft rendered in your own template | ![My work](docs/screenshots/09-my-work.png) My work |

## Architecture

A modular monolith: a FastAPI backend that owns all processing and storage, and a React single-page app.

```mermaid
flowchart LR
  UI[React SPA<br/>frontend/] -- JSON / multipart --> API[FastAPI routes<br/>app/api]
  API --> ING[ingestion<br/>validate & store]
  ING --> PARSE[parsing<br/>PDF · DOCX · XLSX · CSV]
  PARSE --> EXT[extraction<br/>rules + sources + conflicts]
  API --> TPL[template_analysis] --> MAP[mapping]
  EXT --> Q[quotation<br/>Decimal arithmetic]
  MAP --> Q
  PRICE[pricing<br/>price list match] --> Q
  Q --> VAL[validation<br/>19 deterministic rules]
  API --> EDIT[editing<br/>rule parser → proposal → apply/undo]
  EDIT -. optional, off by default .-> AI[ai adapter<br/>OpenAI-compatible]
  Q --> EXP[export<br/>DOCX · XLSX · PDF via LibreOffice]
  API <--> STORE[(storage<br/>backend/data/*.json + files)]
```

Details: [docs/SYSTEM.md](docs/SYSTEM.md) (request flow and pipeline), [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
(modules and decisions), [docs/DATA_MODEL.md](docs/DATA_MODEL.md).

## Technology stack

| Layer | Technology (pinned versions in `backend/requirements*.txt` and `frontend/package.json`) |
|---|---|
| Backend | Python 3.11+, FastAPI 0.162, Pydantic 2.14, Uvicorn 0.54 |
| Documents | pdfplumber 0.11 (PDF), python-docx 1.2 (DOCX), openpyxl 3.1 (XLSX), LibreOffice (optional, PDF export) |
| Frontend | React 19.2, TypeScript 5.9, Vite 8, Tailwind CSS 4.2, lucide-react icons, docx-preview |
| Tests | pytest 9, ruff, mypy · Vitest 5 + Testing Library · Playwright (end-to-end script) |
| Storage | Local filesystem (JSON per project + uploaded/exported files). No database server. |

## Install & run

**Prerequisites:** Python 3.11 or newer (tested with 3.13); Node.js 22 (22.22.2 or newer) or 24 (24.15 or newer)
with npm — tested with Node 22.23.4 and npm 10.9.9. The test runner's DOM library (jsdom 30) sets that minimum; older
Node 22 releases can still build and run the app but not `npm test`.
Optional: [LibreOffice](https://www.libreoffice.org/) for PDF export.

### 1. Backend (terminal 1)

```bash
cd backend
python -m venv .venv
# macOS / Linux
source .venv/bin/activate
# Windows (PowerShell)
#   .venv\Scripts\Activate.ps1
pip install -r requirements.txt          # add -dev for tests: pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000
```

Check it: <http://localhost:8000/api/health> returns `"status": "ok"`. API docs: <http://localhost:8000/docs>.

### 2. Frontend (terminal 2)

```bash
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173>. The dev server proxies `/api` to the backend on port 8000.

### Single-port demo mode (recommended for presenting)

```bash
cd frontend && npm install && npm run build      # creates frontend/dist
cd ../backend && uvicorn app.main:app --port 8000
```

Open <http://localhost:8000> — the backend serves the built app and the API from one port.

> `frontend/.npmrc` sets `legacy-peer-deps=true` to work around an npm 10 crash when resolving Vite's optional peer
> dependencies (see [docs/DECISIONS.md](docs/DECISIONS.md), ADR-009). All required peers are listed explicitly.

## Configuration

Everything works without configuration. Optional settings are environment variables; copy
[`.env.example`](.env.example) to `.env` in the repository root (the backend reads `TENDERFLOW_*` keys from it;
real environment variables take precedence).

| Variable | Default | Purpose |
|---|---|---|
| `TENDERFLOW_DATA_DIR` | `backend/data` | Where projects, uploads and exports are stored |
| `TENDERFLOW_MAX_UPLOAD_MB` | `25` | Upload size limit (1–200) |
| `TENDERFLOW_CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | Allowed browser origins in development |
| `TENDERFLOW_SAMPLES_DIR` | `samples` | Location of the fictional sample documents |
| `TENDERFLOW_FRONTEND_DIST` | `frontend/dist` | Built UI served by the backend |
| `TENDERFLOW_SOFFICE_PATH` | auto-detect | Path to LibreOffice `soffice` for PDF export |
| `TENDERFLOW_AI_PROVIDER` | *(empty = local rules only)* | `openai_compatible` to enable the optional adapter |
| `TENDERFLOW_AI_BASE_URL` | — | e.g. `http://localhost:11434/v1` (Ollama) or a hosted endpoint |
| `TENDERFLOW_AI_MODEL` | — | Model name at that endpoint |
| `TENDERFLOW_AI_API_KEY` | — | Only if the endpoint needs one. Never committed, never sent to the browser |
| `TENDERFLOW_AI_TIMEOUT_S` | `20` | Provider timeout |

Even when a provider is configured, it is only used after you also switch it on in **Settings → AI processing**.

## Demo workflow

1. Open the app → **Try the sample project** (fictional tender, template and price list — processed live, nothing pre-computed).
2. **Review:** the deadline conflict (11:00 vs 11:30 AM, page 1 vs page 3) → pick one; click a *Page … line …* link to see the verbatim source; *Confirm all found values*; confirm the address guessed from the heading. Note the flagged instruction-like sentence in the annex.
3. **Map:** fields were auto-matched by exact name; the signature field is never filled → *Confirm mapping & generate*.
4. **Edit:** type *“Change the delivery period to 30 days.”* → preview shows before/after → tick the confirmation → Apply. Enter the missing rack price (not in the price list — nothing was invented).
5. **Validate & export:** use the quick fixes (*Use PKR*, *Confirm matched prices*, *Confirm the terms*), acknowledge the tax warning, then **Export DOCX** and open it in Word. A 2–3 minute script with a fallback path is in [docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md).

## Supported files & template conventions

| Role | Formats | Notes |
|---|---|---|
| Tender | `.pdf`, `.docx` | PDFs need a text layer (no OCR); password-protected PDFs are rejected |
| Quotation template | `.docx`, `.xlsx` | Your own layout is kept; values are written into it |
| Price list (optional) | `.xlsx`, `.csv` | Needs an item/description column and a price column |

Template conventions (details in [docs/SYSTEM.md](docs/SYSTEM.md#template-conventions)):

- `{{company_name}}`, `{{quotation_number}}`, `{{tender_reference}}`, `{{total}}`, … anywhere (body, tables, headers, footers, cells). `{{notes?}}` marks an optional field. 27 field keys are recognised.
- An items table with a header row such as *#, Description, Specification, Qty, Unit, Unit price, Amount*; the row below the header is repeated per item (or use `{{item.description}}`-style placeholders in that row).
- *Label: ______* lines and *Label | (empty cell)* table rows are detected for recognised labels.
- Signature fields are detected and **never** filled.

## Security & privacy

- Local-first: files are stored under generated IDs in `backend/data/` and never leave the machine in local mode.
- Uploads are validated (extension allow-list, file signature, OOXML structure, size, zip-bomb guard); filenames are sanitised and used for display only.
- Document text is treated as untrusted data; instruction-like text is flagged and never acted on.
- API responses contain no filesystem paths or secrets; the AI key is never returned or logged.
- Strict Content-Security-Policy and security headers; XML entity bombs and zip bombs are rejected (tested).
- No analytics, telemetry or third-party requests (fonts and icons are bundled).
- This is a prototype, not a security-certified procurement system. See [SECURITY.md](SECURITY.md) and [docs/SECURITY_PRIVACY.md](docs/SECURITY_PRIVACY.md).

## Known limitations

Rule-based extraction covers common English tender phrasings, not every format; no OCR; the browser preview of a
DOCX is approximate; XLSX row insertion does not adjust your formulas; the AI adapter has not been tested against a
live provider; single-user local storage without authentication. Full list: [docs/KNOWN_LIMITATIONS.md](docs/KNOWN_LIMITATIONS.md).

## Testing

```bash
# backend (from backend/, with requirements-dev.txt installed)
pytest                     # 96 tests: upload safety, parsing, extraction, mapping, arithmetic, validation, editing, export, API, AI adapter
ruff check . && ruff format --check . && mypy app   # lint, formatting, type check

# frontend (from frontend/)
npm test                   # Vitest: 30 tests
npm run lint && npm run typecheck && npm run build && npm audit

# end-to-end in a real browser (needs Playwright + Chromium and a backend on :8765, see the script header)
BASE_URL=http://127.0.0.1:8765 node scripts/e2e_demo.cjs  # 14 steps: sample project → template preview → edits → export → download, plus real uploads
```

Results of the last full run are recorded in [docs/TEST_PLAN.md](docs/TEST_PLAN.md#latest-results). Test strategy and
manual acceptance checklist: [docs/TEST_PLAN.md](docs/TEST_PLAN.md). Evaluation method: [docs/EVALUATION.md](docs/EVALUATION.md).

## License

[MIT](LICENSE). **Before publishing, the team must confirm the copyright holder line in `LICENSE`** (it currently
reads “TenderFlow contributors”).

## Attribution & acknowledgements

- UI design: created by the team in Figma Make; the frontend was rebuilt from that export.
- Development assistance: parts of this repository were drafted with an AI coding assistant (Claude by Anthropic). The team is responsible for reviewing all code before submission.
- Backend libraries: FastAPI (MIT), Starlette (BSD-3), Pydantic (MIT), Uvicorn (BSD-3), python-multipart (Apache-2.0), pdfplumber & pdfminer.six (MIT), pypdfium2 (Apache-2.0/BSD-3), python-docx (MIT), openpyxl (MIT), httpx (BSD-3). Dev: pytest (MIT), ruff (MIT), mypy (MIT), reportlab (BSD) for generating sample PDFs.
- Frontend libraries: React (MIT), Vite (MIT), Tailwind CSS (MIT), lucide-react (ISC), docx-preview (Apache-2.0), JSZip (MIT/GPLv3 dual — used under MIT). Dev: TypeScript (Apache-2.0), ESLint (MIT), typescript-eslint (MIT), Vitest (MIT), Testing Library (MIT), jsdom (MIT).
- Fonts: DM Sans and Manrope via Fontsource, SIL Open Font License 1.1, bundled locally.
- Optional runtime tool: LibreOffice (MPL-2.0) for PDF conversion — not bundled.
- Transitive dependencies were checked as well. Python: all permissive (MIT, BSD, Apache-2.0, PSF, MIT-CMU for
  Pillow) except certifi (MPL-2.0, file-level copyleft, used unmodified). Frontend production tree: MIT, ISC,
  Apache-2.0, OFL-1.1 (fonts), MIT AND Zlib (pako). No GPL/AGPL-only packages.
- PyMuPDF was deliberately **not** used because it is AGPL-3.0 licensed (see [docs/DECISIONS.md](docs/DECISIONS.md)).
- All sample documents in `samples/` are fictional and generated by `backend/tools/generate_samples.py`.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) and the [Code of Conduct](CODE_OF_CONDUCT.md). Project guidance for AI coding
assistants is in [CLAUDE.md](CLAUDE.md).

## Roadmap

- OCR for scanned tenders (e.g. Tesseract) with per-region confidence shown honestly
- More extraction patterns and multilingual tenders (e.g. Urdu)
- Optional LLM-assisted extraction with the same source-reference and validation guarantees
- Reusable template library across projects; template designer helpers
- Formula-aware XLSX row insertion
- Authentication and team workspaces for multi-user deployments

## Team

*Add the team members' names and roles here before submission.* (Left blank on purpose — no names were provided
for this repository.)
