# Demo script (2–3 minutes)

A live walkthrough using the fictional sample project. Everything shown runs locally; no AI key or internet
connection is needed.

## Before you present (10 minutes earlier)

```bash
cd frontend && npm install && npm run build            # once
cd ../backend && source .venv/bin/activate              # Windows: .venv\Scripts\activate
TENDERFLOW_DATA_DIR=/tmp/tf-demo uvicorn app.main:app --port 8000   # fresh, empty data folder
```

- Open <http://localhost:8000> in a maximised browser window (1440 px wide or more looks best). Zoom 100 %.
- Check the status pill says **Backend connected**.
- Do one dry run of the sample project. Then either keep that project as a backup (see "If something goes wrong")
  or use Settings → *Data & deletion* → *Delete everything* so the live run starts clean.
- Optional: install LibreOffice to show PDF export. Without it, the PDF option is disabled and explains why.

## Script

| Time | Do | Say |
|---|---|---|
| 0:00 | Overview page | "Answering a tender means copying dozens of values from a long document into your own quotation template, then checking every number. TenderFlow does the copying and the checking, and shows its work." |
| 0:15 | Click **Try the sample project** | "This is a fictional 3-page tender. It's processed locally by plain rules, not a language model." |
| 0:25 | Review step: click the tender reference, point at the evidence panel | "Every value links to the exact place in the tender it came from." |
| 0:35 | Point at the **Conflict** on the submission deadline; click **Use this** on one candidate | "The tender gives two different deadlines. TenderFlow doesn't guess — it shows both and asks." |
| 0:50 | **Confirm all found values**, confirm the issuer address, **Mark as reviewed & continue** | "Nothing counts as confirmed until a person confirms it." |
| 1:00 | Mapping step: scroll briefly; **Confirm mapping & generate quotation** | "This is *our* Word template. We confirm which value goes into which blank." |
| 1:10 | Editor: show origin dots and the red **missing** rack price; switch to **In your template** and back | "Each value shows where it came from. The rack has no price in our price list, so there is no total yet — TenderFlow never estimates a price." |
| 1:25 | Type *Change the delivery period to 30 days.* → **Preview change** | "Edits in plain language show a before/after preview first." |
| 1:35 | Show that **Apply** is disabled; tick the confirmation; **Apply change** | "Delivery is a commitment, so it needs an explicit confirmation. Undo is always there." |
| 1:45 | Click **Add** in item 4's *Unit price* cell, type `95000`, Enter | "We enter the missing price; amounts and the total are recalculated exactly." |
| 1:55 | **Review & export** → quick fixes **Use PKR**, **Confirm matched prices**, **Confirm the terms**; acknowledge the remaining warnings | "Nineteen deterministic checks: arithmetic, missing values, currency, tax, unconfirmed commitments, the tender's own requirements." |
| 2:15 | Status shows **Ready to export** → **Export DOCX** → show the checks → **Preview file** | "The export fills our own template. TenderFlow re-opens the file and checks it; the original template is never modified." |
| 2:30 | Close | "Local-first, open source, no AI key needed — and it never invents a value. That's TenderFlow." |

## If something goes wrong

| Problem | Fallback |
|---|---|
| Backend not reachable (pill says *Backend offline*) | Restart `uvicorn`; the page recovers on its own. Otherwise switch to the screenshots in `docs/screenshots/` (same flow, real captures). |
| A step fails live | Open **My work** and continue in the dry-run project you prepared. |
| Running out of time | Skip the mapping explanation and the template preview; go from the instruction preview straight to **Review & export**. |
| Projector is narrow (< 1200 px) | The evidence and instruction panels become drawers — use their toolbar buttons. |
| Someone asks about AI | It's optional and off: an OpenAI-compatible provider can be configured for unrecognised instructions, guarded and previewed. It has only been tested with a mocked provider — say so. |

## Do not claim

OCR, live AI quality, multi-user or cloud deployment, eligibility checking, user-study results or time savings —
none of these have been implemented or measured (see [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md)).
