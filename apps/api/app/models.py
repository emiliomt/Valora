"""SQLAlchemy ORM models — subset of PRD section 9 data model needed for the
MVP vertical slice (create deal -> import financials -> map -> assumptions ->
DCF -> export). Fields not yet used by an implemented workflow are omitted
rather than stubbed, to avoid implying functionality that doesn't exist.
"""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import (
    JSON,
    Boolean,
    Enum,
    Float,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.types import GUID, new_uuid


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class TimestampMixin:
    created_at: Mapped[dt.datetime] = mapped_column(default=utcnow, nullable=False)
    updated_at: Mapped[dt.datetime] = mapped_column(default=utcnow, onupdate=utcnow, nullable=False)


class Workspace(TimestampMixin, Base):
    __tablename__ = "workspaces"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    settings_json: Mapped[dict] = mapped_column(JSON, default=dict)

    memberships: Mapped[list["WorkspaceMembership"]] = relationship(back_populates="workspace")
    deals: Mapped[list["Deal"]] = relationship(back_populates="workspace")


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=new_uuid)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)

    memberships: Mapped[list["WorkspaceMembership"]] = relationship(back_populates="user")


class WorkspaceRole(str):
    ADMIN = "admin"
    EDITOR = "editor"
    VIEWER = "viewer"


class WorkspaceMembership(TimestampMixin, Base):
    __tablename__ = "workspace_memberships"
    __table_args__ = (UniqueConstraint("workspace_id", "user_id", name="uq_workspace_user"),)

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=new_uuid)
    workspace_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("workspaces.id"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id"), nullable=False)
    role: Mapped[str] = mapped_column(Enum("admin", "editor", "viewer", name="workspace_role"), nullable=False)

    workspace: Mapped[Workspace] = relationship(back_populates="memberships")
    user: Mapped[User] = relationship(back_populates="memberships")


class Deal(TimestampMixin, Base):
    __tablename__ = "deals"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=new_uuid)
    workspace_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("workspaces.id"), nullable=False)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    ticker: Mapped[str | None] = mapped_column(String(20), nullable=True)
    exchange: Mapped[str | None] = mapped_column(String(50), nullable=True)
    investment_type: Mapped[str] = mapped_column(String(50), nullable=False, default="Public Equity")
    industry: Mapped[str] = mapped_column(String(100), nullable=False, default="general")
    subsector: Mapped[str | None] = mapped_column(String(100), nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    unit_scale: Mapped[str] = mapped_column(String(20), nullable=False, default="actuals")
    valuation_date: Mapped[dt.date | None] = mapped_column(nullable=True)
    fiscal_year_end: Mapped[str | None] = mapped_column(String(5), nullable=True)  # e.g. "12-31"
    forecast_years: Mapped[int] = mapped_column(default=5, nullable=False)
    investment_thesis: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft")
    created_by: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("users.id"), nullable=True)

    workspace: Mapped[Workspace] = relationship(back_populates="deals")
    source_documents: Mapped[list["SourceDocument"]] = relationship(back_populates="deal", cascade="all, delete-orphan")
    financial_periods: Mapped[list["FinancialPeriod"]] = relationship(back_populates="deal", cascade="all, delete-orphan")
    assumption_sets: Mapped[list["AssumptionSet"]] = relationship(back_populates="deal", cascade="all, delete-orphan")
    model_versions: Mapped[list["ModelVersion"]] = relationship(back_populates="deal", cascade="all, delete-orphan")

    def is_ready_for_valuation(self) -> bool:
        """PRD 7.2 acceptance criteria: cannot run a valuation until currency,
        valuation date, fiscal year end, and forecast period are set."""
        return bool(self.currency and self.valuation_date and self.fiscal_year_end and self.forecast_years)


class SourceDocument(TimestampMixin, Base):
    __tablename__ = "source_documents"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=new_uuid)
    deal_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("deals.id"), nullable=False)
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(1000), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(200), nullable=False)
    document_type: Mapped[str] = mapped_column(String(50), nullable=False, default="other")
    source_date: Mapped[dt.date | None] = mapped_column(nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("users.id"), nullable=True)
    processing_status: Mapped[str] = mapped_column(String(30), nullable=False, default="queued")
    processing_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    deal: Mapped[Deal] = relationship(back_populates="source_documents")


class FinancialPeriod(TimestampMixin, Base):
    __tablename__ = "financial_periods"
    __table_args__ = (UniqueConstraint("deal_id", "fiscal_year", "period_type", name="uq_deal_fy_type"),)

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=new_uuid)
    deal_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("deals.id"), nullable=False)
    fiscal_year: Mapped[int] = mapped_column(nullable=False)
    period_type: Mapped[str] = mapped_column(String(20), nullable=False, default="annual")
    is_historical: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    deal: Mapped[Deal] = relationship(back_populates="financial_periods")
    line_items: Mapped[list["FinancialLineItem"]] = relationship(back_populates="period", cascade="all, delete-orphan")


class FinancialLineItem(TimestampMixin, Base):
    __tablename__ = "financial_line_items"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=new_uuid)
    deal_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("deals.id"), nullable=False)
    period_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("financial_periods.id"), nullable=False)
    statement_type: Mapped[str] = mapped_column(String(30), nullable=False)  # income_statement | balance_sheet | cash_flow
    reported_label: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_key: Mapped[str | None] = mapped_column(String(100), nullable=True)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    unit_scale: Mapped[str] = mapped_column(String(20), nullable=False, default="actuals")
    source_document_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("source_documents.id"), nullable=True)
    mapping_status: Mapped[str] = mapped_column(String(20), nullable=False, default="proposed")
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    period: Mapped[FinancialPeriod] = relationship(back_populates="line_items")


class AssumptionSet(TimestampMixin, Base):
    __tablename__ = "assumption_sets"
    __table_args__ = (UniqueConstraint("deal_id", "scenario", name="uq_deal_scenario"),)

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=new_uuid)
    deal_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("deals.id"), nullable=False)
    scenario: Mapped[str] = mapped_column(String(20), nullable=False)  # base | bull | bear
    name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    wacc: Mapped[float] = mapped_column(Float, nullable=False, default=0.10)
    terminal_growth_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.025)

    deal: Mapped[Deal] = relationship(back_populates="assumption_sets")
    assumptions: Mapped[list["Assumption"]] = relationship(back_populates="assumption_set", cascade="all, delete-orphan")


class Assumption(TimestampMixin, Base):
    __tablename__ = "assumptions"
    __table_args__ = (
        UniqueConstraint("assumption_set_id", "key", "fiscal_year", name="uq_assumption_set_key_year"),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=new_uuid)
    assumption_set_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("assumption_sets.id"), nullable=False)
    key: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g. revenue_growth_rate
    label: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    fiscal_year: Mapped[int] = mapped_column(nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(20), nullable=False, default="pct")
    origin: Mapped[str] = mapped_column(String(30), nullable=False, default="user")
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    assumption_set: Mapped[AssumptionSet] = relationship(back_populates="assumptions")


class ModelVersion(TimestampMixin, Base):
    __tablename__ = "model_versions"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=new_uuid)
    deal_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("deals.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")  # draft|in_review|approved|archived
    scenario_default: Mapped[str] = mapped_column(String(20), nullable=False, default="base")
    input_snapshot_json: Mapped[dict] = mapped_column(JSON, default=dict)
    calculation_snapshot_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_by: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("users.id"), nullable=True)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("users.id"), nullable=True)
    approved_at: Mapped[dt.datetime | None] = mapped_column(nullable=True)

    deal: Mapped[Deal] = relationship(back_populates="model_versions")
    valuation_runs: Mapped[list["ValuationRun"]] = relationship(back_populates="model_version", cascade="all, delete-orphan")
    export_jobs: Mapped[list["ExportJob"]] = relationship(back_populates="model_version", cascade="all, delete-orphan")


class ValuationRun(TimestampMixin, Base):
    __tablename__ = "valuation_runs"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=new_uuid)
    model_version_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("model_versions.id"), nullable=False)
    scenario: Mapped[str] = mapped_column(String(20), nullable=False)
    method: Mapped[str] = mapped_column(String(30), nullable=False, default="dcf")
    inputs_json: Mapped[dict] = mapped_column(JSON, default=dict)
    outputs_json: Mapped[dict] = mapped_column(JSON, default=dict)
    model_check_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")

    model_version: Mapped[ModelVersion] = relationship(back_populates="valuation_runs")


class ExportJob(TimestampMixin, Base):
    __tablename__ = "export_jobs"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=new_uuid)
    model_version_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("model_versions.id"), nullable=False)
    export_type: Mapped[str] = mapped_column(String(10), nullable=False)  # xlsx | pptx
    scenario: Mapped[str] = mapped_column(String(20), nullable=False, default="base")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued")
    storage_key: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    generated_at: Mapped[dt.datetime | None] = mapped_column(nullable=True)

    model_version: Mapped[ModelVersion] = relationship(back_populates="export_jobs")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=new_uuid)
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("workspaces.id"), nullable=True)
    deal_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("deals.id"), nullable=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    old_value_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    new_value_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(default=utcnow, nullable=False)
