# Investment Research & Valuation Platform — Product Requirements Document

> Document status: Draft for implementation
> Primary build environment: Cursor
> Target users: Investment analysts, associates, founders, corporate-development teams, family offices, and early-stage investment teams
> Initial deployment: Internal/private beta
> Primary language: English, with architecture ready for Spanish localization

See the project README for current implementation status against this PRD.

*(Full PRD text lives in the original task description / project history; this file is the
canonical reference copy checked into the repo per §21 "Cursor Implementation Instructions":
"Maintain a docs/model-logic.md document explaining all financial formulas ... " and general
documentation practice. Section numbers below mirror the source PRD.)*

## 1. Product Summary

A web application that converts uploaded company financials and supporting materials into a
transparent, editable investment-research workspace: normalize historical financials, run
structured diligence, build a five-year driver-based forecast and DCF, visualize findings, let
users edit assumptions and scenarios, and export a formula-driven Excel model plus an
investment-committee PowerPoint.

The application must never present itself as investment advice or fabricate data. Every material
output must be traceable to a source, an assumption, or a deterministic calculation.

## Implementation status (this repo)

This repository implements the MVP vertical slice called out in PRD §21 "Cursor Implementation
Instructions":

> Start with the smallest end-to-end vertical slice: create deal → import CSV/XLSX → map
> historicals → edit assumptions → calculate DCF → display results.

Delivered:

- Monorepo layout (`apps/api`, `apps/web`, `services/financial-engine`) per PRD §8.2.
- Deterministic financial engine (`services/financial-engine`) as pure, unit-tested Python —
  forecast build, UFCF, DCF, terminal value, net debt bridge, sensitivities, model checks.
  See `docs/model-logic.md`.
- FastAPI backend (`apps/api`) with SQLAlchemy models covering the §9 data model subset needed
  for the vertical slice, Alembic migrations, deal CRUD, CSV/XLSX financial import with
  rule-based standardized-taxonomy mapping, assumption CRUD (base/bull/bear), model
  calculation, and a formula-driven XLSX exporter (§7.14).
- Minimal Next.js frontend (`apps/web`) covering deal creation, financial upload + mapping
  review, assumption editing by scenario, and a valuation/DCF/sensitivity dashboard.
- Audit log entries on assumption and mapping writes (§7.16).

Not yet implemented (left for subsequent milestones per §16): OAuth/full RBAC enforcement in the
UI, PDF/DOCX/PPTX ingestion, AI diligence & thesis assistant (§7.10–7.12), PPTX export (§7.15),
comparable-company analysis (§7.9), industry-template KPI packs beyond the general template, and
production-grade auth/session hardening. These are explicitly out of scope for a first vertical
slice and are flagged as such in the UI/API rather than silently faked.
