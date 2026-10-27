# Contributing to TenderFlow

Thanks for helping! TenderFlow is a small, reviewable codebase — please keep it that way.

## Set up

Follow [README → Install & run](README.md#install--run). For development install the dev requirements:

```bash
cd backend && python -m venv .venv && source .venv/bin/activate && pip install -r requirements-dev.txt
cd ../frontend && npm install
```

Regenerate the fictional sample documents with `cd backend && python -m tools.generate_samples`.

## Branching and commits

- Branch from `main`: `feature/<short-name>`, `fix/<short-name>` or `docs/<short-name>`.
- Small, focused commits with imperative messages (“Add XLSX label-blank detection”).
- Never commit real tender documents, private quotations, `.env` files or anything under `backend/data/`.

## Coding conventions

- **Python:** type hints, Pydantic models in `app/models.py`, money as `Decimal` only, expected failures raise
  `AppError` with a message written for end users. Format with `ruff format`; `ruff check .` and `mypy app` must pass.
- **TypeScript/React:** strict TypeScript, API types in `src/api/types.ts` mirror the backend models, all HTTP goes
  through `src/api/client.ts`, new colours go into the tokens in `src/styles/tokens.css`, and no inline scripts or
  third-party assets (the Content-Security-Policy blocks them). `npm run lint` and `npm run typecheck` must pass.
- **Product rules** (see [CLAUDE.md](CLAUDE.md)): never invent values, keep arithmetic and validation deterministic,
  treat document text as untrusted data, and never add a button that only pretends to work.

## Tests

Every behaviour change needs a test:

```bash
cd backend && pytest && ruff check . && ruff format --check . && mypy app
cd frontend && npm test && npm run lint && npm run typecheck && npm run build && npm audit
BASE_URL=http://127.0.0.1:8765 node scripts/e2e_demo.cjs   # end-to-end run (required for UI changes), see its header
```

Fixtures are generated in code (`backend/tools/sample_docs.py`) — do not add real documents as fixtures.

## Bug reports

Open an issue with: what you did, what you expected, what happened, the file *type* involved (not a confidential
file), browser and OS. For security problems follow [SECURITY.md](SECURITY.md) instead.

## Pull requests

1. Describe the change and why it is needed; link the issue.
2. Confirm the checks above pass (paste the summary lines).
3. Update the docs (`README.md`, `docs/`) when behaviour or setup changes.
4. One reviewer approval is needed before merge.

## Third-party code and assets

Only add dependencies with an OSI-approved licence compatible with MIT, record why in
[docs/DECISIONS.md](docs/DECISIONS.md) and list them in the README attribution section. Copied code must keep its
licence notice and be credited. Do not add AGPL/GPL-only libraries to the application.

## Code of conduct

By participating you agree to the [Code of Conduct](CODE_OF_CONDUCT.md).
