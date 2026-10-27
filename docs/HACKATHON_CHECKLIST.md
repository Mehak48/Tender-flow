# Hackathon checklist — Hacktoberfest Hackathon NUST × NSTP 2026

> **Source of these items:** the project brief the team gave to the development assistant. The organizers'
> official rules and judging criteria were **not** available in this repository. Check every line against the
> organizers' published material before submitting, and do not treat anything here as an organizer confirmation.

Legend: ✅ done in this repository · ⚠️ done, needs a team decision or check · ❌ not done (team action) ·
❓ requires organizer confirmation

## 1. Items that require organizer confirmation

| Item | Status | Notes |
|---|---|---|
| Whether **Kiro** must be used, and how it affects scoring | ❓ **Requires organizer confirmation** | The brief flags an inconsistency in how Kiro relates to scoring. We assumed neither that it is mandatory nor how it is scored. This repository was **not** built with Kiro (an AI coding assistant, Claude, was used — disclosed in the README). Do not claim Kiro use. If it turns out to be required, agree with the organizers how to meet it honestly. |
| Final judging criteria and their weighting | ❓ | Do not rely on any unofficial interpretation of the scoring. |
| Submission format (repository link, video, slides, live demo) and deadline | ❓ | `docs/DEMO_SCRIPT.md` supports a live demo or a recording. |
| Rules on AI-assisted development and how to disclose it | ❓ | Disclosed in README → Attribution. |
| Any repository requirements (visibility, topics, contribution history) | ❓ | Nothing has been pushed anywhere. |

## 2. Repository and open-source readiness

| Item | Status | Where |
|---|---|---|
| OSI-approved license | ⚠️ MIT present; **copyright holder line must be confirmed** by the team | `LICENSE` |
| README: problem, solution, feature status, screenshots, architecture, setup, configuration, demo, limitations, testing, license, attribution, roadmap | ✅ | `README.md` |
| Team names and roles | ❌ placeholder — add real names and roles only | README → Team |
| Contributing guide, code of conduct, security policy, changelog | ✅ (security contact and conduct contact are placeholders ⚠️) | root |
| `.gitignore`, `.gitattributes`, `.env.example` (placeholders only) | ✅ | root |
| No secrets, real documents or local data committed | ✅ `python scripts/check_secrets.py` clean; samples are fictional | `samples/README.md` |
| Third-party licences compatible with MIT (no AGPL) | ✅ | README → Attribution, `docs/DECISIONS.md` ADR-003 |
| GitHub repository created and pushed | ❌ team action — nothing was created, pushed or published by the assistant | — |

## 3. Working prototype

| Item | Status | Evidence |
|---|---|---|
| Runs locally from documented commands | ✅ on Linux; ⚠️ Windows/macOS untested | README → Install & run |
| Complete flow: upload → review → mapping → generate → edit → validate → export | ✅ | E2E script, 14 steps |
| Works offline, without an AI key | ✅ | `docs/AI_POLICY.md` |
| Fictional sample project for the demo | ✅ | Overview → *Try the sample project* |
| Automated tests actually run | ✅ | `docs/TEST_PLAN.md` → Latest results |
| Honest limitations documented | ✅ | `docs/KNOWN_LIMITATIONS.md` |

## 4. Product brief requirements

Requirement-by-requirement status: [PRODUCT_SPEC.md §5](PRODUCT_SPEC.md#5-functional-requirements).
Summary: all core workflow requirements are implemented and tested. Limitations: extraction is rule-based (English,
common phrasings); the optional AI adapter is tested only against a mocked provider; PDF export needs LibreOffice;
no OCR.

## 5. Documentation set

| Document | Status |
|---|---|
| `docs/PRODUCT_SPEC.md`, `SYSTEM.md`, `DESIGN.md`, `ARCHITECTURE.md`, `DATA_MODEL.md` | ✅ |
| `docs/AI_POLICY.md`, `SECURITY_PRIVACY.md` | ✅ |
| `docs/TEST_PLAN.md` (with real results), `EVALUATION.md` (method; no results collected yet) | ✅ / ⚠️ |
| `docs/DEMO_SCRIPT.md`, `DECISIONS.md`, `HACKATHON_CHECKLIST.md`, `KNOWN_LIMITATIONS.md` | ✅ |
| `CLAUDE.md` (guidance for AI coding assistants working on the repo) | ✅ |

## 6. Before submitting — team to-do

1. Confirm the **LICENSE** copyright holder (team name or members; no invented legal entity).
2. Add **team names and roles** to the README.
3. Add a **security contact** (SECURITY.md) and a **conduct contact** (CODE_OF_CONDUCT.md).
4. **Ask the organizers** about Kiro, judging criteria and submission format (section 1).
5. **Review the code and docs.** Parts were drafted with an AI coding assistant; the team is responsible for them.
6. Create the GitHub repository yourselves, run `python scripts/check_secrets.py`, check `git status` for stray
   files, then push.
7. Rehearse `docs/DEMO_SCRIPT.md` on the presentation laptop. Optionally install LibreOffice for PDF export.
8. If time allows, run a small evaluation (`docs/EVALUATION.md`) — and report only measured numbers.
