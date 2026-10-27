# Architecture

Code organisation, module responsibilities and the main technical decisions. The runtime behaviour of each pipeline
stage is described in [SYSTEM.md](SYSTEM.md); the decision log is [DECISIONS.md](DECISIONS.md).

## Shape

A **modular monolith**: one FastAPI process with plain Python modules per pipeline stage, and one React SPA. No
queues, no database server, no microservices — a judge can read the whole flow in an afternoon.

```
backend/app/
  main.py               app factory, middleware (CORS, security headers), routers, static SPA serving
  config.py             env/.env configuration, branding.json
  errors.py             AppError + JSON error handlers
  models.py             every Pydantic model (persisted data + API views)
  storage.py            ProjectStore / SettingsStore: JSON files, ID validation, locks, atomic writes
  ingestion.py          stage 1
  parsing/              stage 2 — pdf.py, docx_parser.py, xlsx_parser.py (+csv), types.py
  extraction/           stage 3 — rules.py (field specs), normalize.py, line_items.py, injection.py
  review.py             stage 4
  fields.py             canonical quotation fields + label synonyms (shared vocabulary)
  template_analysis.py  stage 5a
  mapping.py            stage 5b
  pricing.py            price list parsing and matching
  quotation.py          stage 6 — build + Decimal arithmetic + display formatting
  editing/              stage 7 — parser.py (rules), apply.py (operations + diff), __init__.py (proposals, undo)
  ai/                   optional adapter — base.py (guards, status), openai_compat.py
  validation.py         stage 8
  export/               stage 9 — docx_export.py, xlsx_export.py, pdf_export.py, common.py, __init__.py (verify)
  evidence.py           verbatim source text for the evidence panel (small LRU cache of parsed documents)
  services.py           workflow orchestration used by routes (upload processing, generate, views, summaries)
  api/                  routes: projects.py, system.py, library.py, deps.py
backend/tools/          sample/fixture builders (dev only; reportlab)
backend/tests/          pytest suites

frontend/src/
  main.tsx, App.tsx     shell (sidebar, top bar, help), hash routes
  router.ts             tiny hash router (no dependency)
  config.ts             branding, API base, accepted formats
  api/                  types.ts (mirror of models.py), client.ts (fetch/XHR wrapper, ApiError)
  components/           ui.tsx (Button, Badge, Notice…), Modal, UploadSlot, AppContext (health + toasts), HowItWorks
  flow/                 ProjectFlow + one component per step; editor/ (DocField, QuotationDocument, InstructionPanel, TemplatePreview)
  pages/                Overview, Projects, Templates, Documents, Activity, Settings
  lib/                  format.ts, files.ts, labels.ts
  styles/               tokens.css (design tokens), app.css (components)
```

## Data flow

1. **Upload** → `services.process_upload` → `ingestion.store_upload` → `parsing.parse_document` → role-specific step
   (`extract_tender` / `analyze_template` + `auto_mapping` / `parse_price_list`) → saved in `project.json`.
2. **Review / mapping** → small update routes mutate `Extraction` / `Mapping` inside a transaction.
3. **Generate** → `quotation.build_quotation` (pure function of project + settings) → `recalculate`.
4. **Edit** → `editing.propose` (rules, optional AI) → `EditProposal` → `apply_proposal` → `apply_operations` →
   `recalculate`; undo snapshots and history are stored on the project.
5. **Every read** → `services.project_view` → `validation.validate` (pure function) → `ProjectView`.
6. **Export** → `export.run_export` → fill template copy → re-open → checks → `ExportArtifact`.

## API boundaries

- The frontend only knows the JSON contract (`ProjectView`, `EditResult`, `ExportResponse`, …). It never builds file
  paths: downloads use `/api/projects/{id}/exports/{export_id}/download`.
- All IDs (`prj_`, `doc_`, `exp_`, `edt_`, `itm_`, `rec_`, `evt_` + 12 hex chars) are generated server-side and
  validated by regex before any filesystem access.
- Money/quantities are strings in JSON (Pydantic `Decimal` serialisation), so no float rounding happens in transit.

## Key decisions (summary)

| Decision | Why |
|---|---|
| Rule-based extraction first, AI optional | Works offline, deterministic, explainable (each field records its rule and source); demo never depends on an external service |
| pdfplumber instead of PyMuPDF | PyMuPDF is AGPL-3.0, incompatible with an MIT-licensed project's distribution goals; pdfplumber is MIT and has table detection |
| JSON files instead of SQLite | Single user, small data, human-inspectable, trivial deletion; per-project lock + atomic replace is enough |
| Full `ProjectView` returned after each mutation | Prevents client/server drift; validation always fresh. Cost: larger responses (fine locally) |
| One operation model for manual and NL edits | One validated code path, consistent history/undo, AI can only emit the same operations |
| Destination-keyed mapping rows | Mail-merge mental model; naturally exposes unfilled template fields; one source can feed several destinations |
| Hash router, no router library | Six pages and one parameterised route do not justify a dependency |
| Bundled fonts (Fontsource) | No third-party requests; works on offline demo laptops |
| docx-preview loaded lazily | Template-faithful preview without a server-side renderer; kept out of the main bundle |

## Trade-offs

- Regex rules cover common English tender phrasings; unusual layouts need manual entry in the review step.
- Whole-project JSON rewrite on every change is simple but not suited to very large projects or many concurrent users.
- DOCX formatting is preserved at run level; complex content controls, fields and text boxes are not processed.
- openpyxl may drop some XLSX features (charts, images) and does not adjust formulas when rows are inserted.

## Extension points

- **New extraction rule:** add a `FieldSpec` in `extraction/rules.py` (labels, normaliser, sentence rules) and a
  fixture assertion in `tests/test_extraction.py`.
- **New quotation field:** add a `FieldDef` (with synonyms) in `fields.py`; fill it in `quotation.build_quotation`.
- **New validation rule:** write `rule_x(ctx)` in `validation.py` and append it to `RULES`.
- **New instruction:** add a regex branch in `editing/parser.py` that returns existing operations, plus a test.
- **New AI provider:** implement `complete_json(system, user) -> dict` (the `AIProvider` protocol) and register it in
  `ai/base.get_provider`. The guards in `validate_ai_operations` apply automatically.
- **New export format:** add a writer in `export/` and extend `allowed_formats` and `_verify`.
