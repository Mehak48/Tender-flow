# Product specification

**TenderFlow** — *From tender documents to quotation-ready proposals.* Version 0.1.0, hackathon prototype for
Hacktoberfest Hackathon NUST × NSTP 2026. Status of each requirement reflects the code in this repository.

## 1. Problem

Suppliers answer tenders by reading long PDF/Word documents, copying line items, quantities, deadlines and commercial
terms into their own quotation template, pricing every line and checking the result. The work is repetitive, and
the costly mistakes are omissions and transcription errors: a missed line item, a wrong quantity, a delivery
period promised that the company cannot meet, a total that does not add up.

## 2. Target users (assumptions, not research findings)

- **Bid / sales coordinator at a small or mid-sized supplier** who prepares several quotations a month in Word or
  Excel templates the company already uses.
- **Reviewer / manager** who checks a quotation before it is sent and needs to see where every figure came from.

No user interviews or usability tests have been run yet; [EVALUATION.md](EVALUATION.md) describes how to run them.

## 3. Goals and non-goals

**Goals**
1. Cut the time from "tender received" to "draft quotation ready for review".
2. Make every value traceable: source location, user input, price list, company profile or calculation.
3. Keep the user's own template and formatting.
4. Never invent data; make gaps and conflicts visible.
5. Work locally, offline and without an AI key.

**Non-goals (out of scope)**
Tender discovery or scraping, marketplaces, bid submission, e-signatures, notifications, authentication and team
workspaces, analytics dashboards, OCR of scanned documents, price estimation.

## 4. Core workflow and user stories

| # | As a coordinator, I want to… | So that… |
|---|---|---|
| U1 | upload a tender, my quotation template and optionally my price list | I start from my real documents |
| U2 | see the reference, dates, buyer, terms, line items and requirements found in the tender, each with its source | I can trust or correct them quickly |
| U3 | be told when the tender contradicts itself or lacks something | I do not copy an error or miss a gap |
| U4 | confirm how the data fills my template | values land in the right place |
| U5 | get a draft with my prices and company details filled in, and missing items clearly marked | I only work on what is left |
| U6 | change the draft by typing an instruction or editing in place, seeing the effect before it is applied | edits are fast but never surprising |
| U7 | have arithmetic, totals and consistency checked automatically | the numbers are right |
| U8 | export into my own Word/Excel template (or PDF) | the result looks like my company's quotation |
| U9 | delete everything when I am done | confidential tenders do not linger |

## 5. Functional requirements

Status: ✅ implemented and tested · ⚠️ implemented with a limitation · ❌ not implemented.

| ID | Requirement | Status | Acceptance (how it is verified) |
|---|---|---|---|
| F1 | Upload tender PDF/DOCX, template DOCX/XLSX, price list XLSX/CSV; reject other types with an explanation | ✅ | `test_ingestion.py`; E2E steps 12–13 |
| F2 | Validate size, extension and content signature; guard against zip and XML bombs | ✅ | `test_ingestion.py` |
| F3 | Parse PDF (page-aware, tables), DOCX, XLSX, CSV with source locations | ✅ | `test_parsing.py` |
| F4 | Detect scanned/image-only PDFs and say OCR is not supported | ✅ | `test_parsing.py` |
| F5 | Extract 16 tender fields, line items and categorised requirements with source references | ⚠️ rule-based; common English phrasings only | `test_extraction.py` |
| F6 | Flag conflicting values and keep all candidates | ✅ | `test_extraction.py`; E2E steps 2–3 |
| F7 | Flag instruction-like text and treat it as data | ✅ pattern-based | `test_document_instructions_do_not_change_behaviour` |
| F8 | Review: confirm, edit, choose candidate, add/remove line items, acknowledge requirements, show verbatim evidence | ✅ | `test_api.py`; E2E steps 2–4 |
| F9 | Analyse templates: `{{placeholders}}`, "Label: ____" blanks, items table, signature fields (never filled) | ✅ | `test_template_mapping.py` |
| F10 | Destination-keyed field mapping with required/unfilled indicators and explicit confirmation | ✅ | `test_template_mapping.py`; E2E step 5 |
| F11 | Generate a quotation: company profile, buyer and tender data, terms (unconfirmed when from the tender), prices only from the price list | ✅ | `test_quotation_validation.py` |
| F12 | Decimal arithmetic, ROUND_HALF_UP, totals only when every line is priced, tax only when configured | ✅ | `test_quotation_validation.py` |
| F13 | Edit in place and via 13 rule-based instruction patterns, with preview, material-change confirmation, version check, history and undo | ✅ | `test_editing.py`; E2E steps 7–8 |
| F14 | Optional OpenAI-compatible provider for unrecognised instructions, off by default, guarded | ⚠️ mocked tests only | `test_ai_adapter.py` |
| F15 | 19 deterministic validation rules; errors block final export; warnings acknowledgeable; quick fixes | ✅ | `test_quotation_validation.py`; E2E steps 9–10 |
| F16 | Export into the user's DOCX/XLSX template; `[MISSING: …]` markers; draft labelling; post-export checks; original unchanged | ✅ | `test_export.py`; E2E step 11 |
| F17 | PDF export | ⚠️ only when LibreOffice is installed | `test_export.py` (runs when `soffice` exists) |
| F18 | Preview the draft in the user's template in the browser | ⚠️ approximate DOCX rendering | E2E steps 6 and 11 |
| F19 | Projects list, template library with reuse, document library, activity history | ✅ | `test_api.py`; E2E step 14 |
| F20 | Settings: company profile, quotation defaults, currency, tax, AI opt-in, delete all data | ✅ | `test_api.py` |
| F21 | Fictional sample project that runs the real pipeline | ✅ | `test_sample_project_runs_the_real_pipeline`; E2E |
| F22 | OCR, authentication, multi-user, cloud deployment | ❌ | out of scope |

## 6. Non-functional requirements

| Area | Requirement | Status |
|---|---|---|
| Integrity | No invented tender data, prices, tax, dates, certifications, signatures or company details; every value has an origin | ✅ enforced in code and tests |
| Privacy | Local storage only; no analytics; no outbound requests unless an AI provider is configured and enabled | ✅ |
| Security | Untrusted uploads, no execution, ID-validated file access, no paths/secrets in responses, CSP | ✅ see [SECURITY_PRIVACY.md](SECURITY_PRIVACY.md) |
| Transparency | AI use visible (mode, engine badge, origin marker, validation warning) | ✅ |
| Accessibility | Keyboard operable, labelled controls, AA contrast | ⚠️ no formal audit yet |
| Performance | Interactive on tender-sized documents. The sample project (3-page PDF tender + DOCX template + XLSX price list through the full pipeline) took about 0.075 s per run on a 2-vCPU development VM | ⚠️ measured informally (3 runs of `POST /api/demo/project`), no benchmark on large tenders |
| Portability | Windows, macOS, Linux with Python 3.11+ and Node 22.22.2+/24.15+ | ⚠️ developed and tested on Linux only |
| Licensing | MIT; all dependencies under permissive licences (no AGPL) | ✅ see README attribution |

## 7. Success measures (to be collected — none reported yet)

- Time from upload to a validated draft, compared with the team's manual process on the same tender.
- Share of tender line items and key fields extracted correctly (precision/recall per field) on a labelled set.
- Number of corrections a user makes before export.
- Task success and confidence in a moderated usability test (5 participants).

Methods and templates: [EVALUATION.md](EVALUATION.md).

## 8. Open questions

- Which tender formats do the target users receive most (scanned vs digital PDF)? This decides whether OCR is next.
- Do users keep price lists in a form the matcher can read (one row per product with a price column)?
- Which hackathon judging criteria apply and how they are weighted — see [HACKATHON_CHECKLIST.md](HACKATHON_CHECKLIST.md).
