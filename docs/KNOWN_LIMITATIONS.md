# Known limitations

An honest list for TenderFlow 0.1.0, grouped by area. If something is not listed here, it either works as
described in the README or has not been tested — the [TEST_PLAN.md](TEST_PLAN.md) says which.

## Reading documents

- **No OCR.** Scanned or image-only PDF pages are detected and reported; their content is not read.
- **Encrypted PDFs** and legacy `.doc` / `.xls` / `.rtf` / `.odt` files are rejected with an explanation.
- **PDF tables must have ruling lines.** pdfplumber's line strategy finds bordered tables; borderless tables are read
  as text lines, so their line items are **not** extracted (the review step allows adding items manually).
- Multi-column page layouts can interleave text from both columns.
- Limits: PDF ≤ 300 pages; DOCX ≤ 20 000 blocks; XLSX ≤ 5 000 rows × 60 columns per sheet; upload ≤ 25 MB by default.
- Text boxes, shapes, footnotes and comments in DOCX tenders are not read.

## Extraction

- **Rule-based, English only.** 16 fields are found through label patterns ("Tender No:", "Closing date –", label
  cell + value cell) and a few sentence patterns. Unusual wording is missed and shows as *missing*.
- **Numeric dates are read day-first** (`03/04/2026` = 3 April 2026). US-style month-first dates would be misread;
  dates written with month names are unambiguous. Two-digit years are not recognised.
- The issuer name and address come from heuristics and are always marked *needs review*.
- Line items need a table whose header has a description column and a quantity column. Quantities must be numeric
  ("4", "6 Boxes"); words or phrases such as "ten" or "As required" are flagged for review, not guessed. (Number
  words are understood in durations such as "one (1) year".)
- Requirements are sentences containing *shall / must / should / mandatory / is (are) required to*, categorised by
  keywords — not a legal reading of the tender.
- Instruction-like-text detection uses 7 patterns and will miss creative wording (see [SECURITY_PRIVACY.md](SECURITY_PRIVACY.md)).
- "Rupees" without a code maps to PKR as a suggestion only; currency is never applied without the user's choice.
  Supported currencies: PKR, USD, EUR, GBP, AED, SAR, CNY, INR, BHD, QAR.

## Templates, mapping and pricing

- Placeholders must be written as `{{key}}` (or `{{key?}}` for optional) in normal text runs. Content controls,
  text boxes, fields (MERGEFIELD) and form fields are **not** filled.
- One items table per template. Nested tables are not supported.
- XLSX: when more line items than template rows exist, rows are inserted and styles copied, but **formulas below
  the table are not adjusted** and charts/images may be lost (openpyxl limitation). Check the exported workbook.
- Automatic mapping covers recognised keys and labels only; everything else is mapped by hand.
- Price matching compares product names word by word. It does not convert units or currencies, and ambiguous
  matches deliberately get no price.

## Editing and AI

- The local instruction parser understands 13 patterns (listed in the editor and the README), in English. Anything
  else gets "not understood" with examples, unless the optional AI provider is enabled.
- **The AI adapter has only been tested against a mocked HTTP transport**, never against a live provider. Model
  quality, latency and JSON compliance of any real provider are unverified.
- Undo keeps the last 30 snapshots; there is no redo.

## Validation and export

- Validation is deterministic and covers arithmetic, completeness, consistency with the tender and confirmations.
  It does **not** check eligibility, legal terms, technical compliance or whether prices are competitive.
- The deadline check compares the tender's date and time with the clock of the computer running the backend.
  Time zones are not interpreted.
- **PDF export requires LibreOffice**; layout fidelity depends on LibreOffice's rendering of the template.
- The in-browser *In your template* preview is approximate; Word or Excel remain the reference.
- Post-export checks confirm content (no leftover placeholders, totals and line items present, original unchanged),
  not visual layout.

## Platform and operations

- **Single user on localhost, no authentication.** Not safe to expose on a network (see SECURITY_PRIVACY.md).
- No encryption at rest, no backups, no migrations between data-format versions.
- Long operations (large PDFs, LibreOffice conversion) run inside the request; there is no job queue or progress
  beyond the upload progress bar.
- Developed and tested on **Linux** only (Python 3.13, Node 22.23.4, Chromium via Playwright). Windows and macOS
  are expected to work but have not been tested.
- No formal accessibility audit (screen reader, axe) and no usability testing with real users yet.
- No performance benchmark on large tenders.
- Light theme only; English UI only.

## Process

- Parts of the code and documentation were drafted with an AI coding assistant; the team must review all of it
  before submission (README → Attribution).
- The LICENSE copyright holder, team credits and security contact are placeholders for the team to fill in.
