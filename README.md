# Valora — Investment Research & Valuation Platform

A traceable underwriting workspace: upload company financials, normalize them into a standardized
taxonomy, build a driver-based five-year forecast and unlevered DCF across base/bull/bear
scenarios, and export a formula-driven Excel model. See [`docs/prd.md`](docs/prd.md) for the full
product spec and [`docs/model-logic.md`](docs/model-logic.md) for every formula the engine
implements.

This repository currently implements the MVP vertical slice called out in the PRD's
implementation instructions: **create a deal → import CSV/XLSX financials → review & approve the
normalized mapping → edit base/bull/bear assumptions → calculate the forecast + DCF → approve a
model version → export a formula-driven Excel workbook.** See "Implementation status" in
`docs/prd.md` for what's built vs. deferred.

## Repository layout

```
apps/
  web/                  Next.js (App Router) frontend
  api/                  FastAPI backend — deals, financials, assumptions, model versions, exports
services/
  financial-engine/     Deterministic, pure-Python forecast/DCF/sensitivity/checks engine
infrastructure/
  docker/               Dockerfiles used by docker-compose.yml
docs/
  prd.md                Product requirements document
  model-logic.md         Every formula, unit convention, and edge case, with test references
```

`financial-engine` has zero framework dependencies by design (PRD §21: "Keep calculation logic in
pure Python functions with extensive unit tests; do not put financial logic in React components or
LLM prompts"). `apps/api` depends on it as a local editable package.

## Local development

### Option A — Docker Compose (Postgres + Redis + MinIO + API + web)

```bash
docker compose up --build
```

- API: http://localhost:8000 (docs at `/docs`)
- Web: http://localhost:3000
- MinIO console: http://localhost:9001 (user/pass: `valora` / `valora-dev-secret`)

### Option B — run services directly

**Financial engine + API** (defaults to a local SQLite file if `VALORA_DATABASE_URL` isn't set):

```bash
cd services/financial-engine && python3 -m venv .venv && . .venv/bin/activate && pip install -e ".[dev]"
cd ../../apps/api && python3 -m venv .venv && . .venv/bin/activate
pip install -e ../../services/financial-engine -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload
```

**Web:**

```bash
cd apps/web
cp .env.example .env.local   # point NEXT_PUBLIC_API_BASE_URL at the API above
npm install
npm run dev
```

## Tests

```bash
# Financial engine (30 unit tests incl. 3 golden company fixtures, PRD §17)
cd services/financial-engine && . .venv/bin/activate && pytest

# API (integration tests incl. a full create-deal-to-export-xlsx walkthrough)
cd apps/api && . .venv/bin/activate && pytest

# Frontend
cd apps/web && npm run typecheck && npm run build
```

## Financial import format (MVP)

The CSV/XLSX importer (`POST /api/deals/{deal_id}/financials/import`) expects a simple, documented
tabular schema — not an attempt to parse arbitrary filing layouts (that's the PDF/DOCX extraction
pipeline, out of scope for this slice):

| fiscal_year | statement_type | label | value | currency | unit_scale |
|---|---|---|---|---|---|
| 2024 | income_statement | Total revenue | 10000000 | USD | actuals |
| 2024 | balance_sheet | Cash and cash equivalents | 5000000 | USD | actuals |

`statement_type` is one of `income_statement`, `balance_sheet`, `cash_flow`. `currency` /
`unit_scale` are optional and fall back to the deal's settings. Reported labels are proposed a
standardized-taxonomy mapping by keyword rules (`app/services/taxonomy.py`); every mapping starts
as `proposed` and must be explicitly approved before it feeds the forecast engine.

## Compliance

Valora provides research, modeling, and analytical support. It does not provide personalized
investment advice, a recommendation to buy or sell securities, legal advice, tax advice, or
accounting advice. Independently verify all data, assumptions, and model outputs before use in any
investment decision.
