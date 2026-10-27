# Evaluation plan

How to measure whether TenderFlow is accurate and useful. **No results have been collected yet.** The tables below
are intentionally empty; fill them only with measured numbers and keep the raw data (outside the repository if it
contains real tenders).

The fictional sample tender is **not** an evaluation set: the extraction rules were developed against it.

## 1. Questions

1. **Extraction accuracy:** how many tender fields and line items does TenderFlow find correctly, and how often does
   it show a wrong value as *extracted*?
2. **Traceability:** do source references point to the right page/line/cell?
3. **Time:** how long does it take to go from a tender to a validated draft, compared with the current manual process?
4. **Errors:** does the validated draft contain fewer omissions and arithmetic errors than a manual one?
5. **Usability and trust:** can a first-time user complete the flow, and do they trust the result enough to send it
   after review?

## 2. Extraction accuracy

**Data set:** 10–20 real tenders the team is allowed to use (digital PDFs and DOCX; note scanned ones separately).
Never commit them.

**Ground truth:** for each tender, a spreadsheet with one row per field (the 16 field keys in
`backend/app/extraction/rules.py`) and one row per line item (description, quantity, unit), filled in by a person
who did not see TenderFlow's output.

**Metrics:**

| Metric | Definition |
|---|---|
| Field precision | correct values ÷ values TenderFlow shows as *extracted* or *needs review* |
| Field recall | correct values ÷ fields present in the tender |
| False "extracted" rate | wrong values with status *extracted* ÷ all *extracted* values (the most harmful error) |
| Conflict detection | genuine contradictions flagged ÷ genuine contradictions present |
| Line-item recall / precision | items with matching description and exact quantity |
| Source accuracy | source references that point to the text containing the value ÷ values checked |

**Results:** *not yet measured*

| Tender | Pages | Field precision | Field recall | False "extracted" | Line-item recall | Notes |
|---|---|---|---|---|---|---|
| — | — | — | — | — | — | — |

## 3. Time and error study

**Design:** within-subject. Each participant prepares one quotation manually and one with TenderFlow, using two
comparable tenders, with the order counterbalanced. Use the participant's normal template and price list.

**Measures:** time to a draft they would send for review; omissions (line items, required fields); arithmetic errors;
number of corrections made in TenderFlow before export.

**Results:** *not yet measured*

| Participant | Manual time | TenderFlow time | Manual errors | TenderFlow errors | Corrections | Notes |
|---|---|---|---|---|---|---|
| — | — | — | — | — | — | — |

## 4. Usability test

**Participants:** 5 people who prepare quotations (or as close as available). **Task:** use the sample project, then
one of their own tenders, from upload to exported DOCX. Think-aloud; facilitator does not help unless blocked.

**Measures:** task completion, time per step, errors and blockers, System Usability Scale (SUS) questionnaire, and a
1–5 rating of "I would send this quotation after my normal review".

**Results:** *not yet measured*

| Participant | Completed? | Blockers | SUS | Trust (1–5) | Notes |
|---|---|---|---|---|---|
| — | — | — | — | — | — |

## 5. Reporting rules

- Report sample sizes with every number; do not extrapolate from the sample tender.
- Report failures and blockers, not only averages.
- Do not quote participants by name without their consent; never publish their documents.
- Record the TenderFlow version (commit) used.
