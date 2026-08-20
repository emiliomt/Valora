import datetime as dt
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import models, schemas
from app.db import get_db
from app.deps import get_current_user, require_deal_access, require_editor
from app.services import audit
from app.services.engine_bridge import run_scenario
from financial_engine.schemas import DCFInputs
from financial_engine.sensitivity import wacc_vs_terminal_growth_grid

router = APIRouter(tags=["model-versions"])


@router.post("/api/deals/{deal_id}/model-versions", response_model=schemas.ModelVersionOut, status_code=status.HTTP_201_CREATED)
def create_model_version(
    deal_id: uuid.UUID,
    payload: schemas.ModelVersionCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    require_editor(deal_id, db, user)
    mv = models.ModelVersion(deal_id=deal_id, name=payload.name, scenario_default=payload.scenario_default, created_by=user.id)
    db.add(mv)
    db.commit()
    db.refresh(mv)
    audit.record(db, entity_type="model_version", entity_id=mv.id, action="create", actor_id=user.id, deal_id=deal_id)
    db.commit()
    return mv


@router.get("/api/deals/{deal_id}/model-versions", response_model=list[schemas.ModelVersionOut])
def list_model_versions(deal_id: uuid.UUID, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    require_deal_access(deal_id, db, user)
    return db.query(models.ModelVersion).filter_by(deal_id=deal_id).order_by(models.ModelVersion.created_at.desc()).all()


def _get_model_version(model_version_id: uuid.UUID, db: Session, user: models.User) -> models.ModelVersion:
    mv = db.get(models.ModelVersion, model_version_id)
    if mv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model version not found")
    require_deal_access(mv.deal_id, db, user)
    return mv


@router.get("/api/model-versions/{model_version_id}", response_model=schemas.ModelVersionOut)
def get_model_version(model_version_id: uuid.UUID, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    return _get_model_version(model_version_id, db, user)


@router.post("/api/model-versions/{model_version_id}/calculate", response_model=schemas.ValuationRunOut)
def calculate_model_version(
    model_version_id: uuid.UUID, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)
):
    """Runs the deterministic engine for every scenario that has an
    assumption set defined, persists a ValuationRun per scenario, and
    returns all results (PRD 7.7 acceptance criteria: same inputs -> same
    outputs; full calculation trace retrievable)."""
    mv = _get_model_version(model_version_id, db, user)
    require_editor(mv.deal_id, db, user)
    deal = db.get(models.Deal, mv.deal_id)
    if not deal.is_ready_for_valuation():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Deal is missing currency, valuation_date, fiscal_year_end, or forecast_years.",
        )

    assumption_sets = db.query(models.AssumptionSet).filter_by(deal_id=mv.deal_id).all()
    if not assumption_sets:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No assumption sets defined for this deal.")

    scenarios: dict[str, dict] = {}
    for assumption_set in assumption_sets:
        try:
            result = run_scenario(db, deal, assumption_set)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"[{assumption_set.scenario}] {exc}") from exc
        scenarios[assumption_set.scenario] = result

        db.query(models.ValuationRun).filter_by(model_version_id=mv.id, scenario=assumption_set.scenario, method="dcf").delete()
        run_row = models.ValuationRun(
            model_version_id=mv.id,
            scenario=assumption_set.scenario,
            method="dcf",
            inputs_json={"wacc": assumption_set.wacc, "terminal_growth_rate": assumption_set.terminal_growth_rate},
            outputs_json=result,
            model_check_status="blocked" if result["model_checks"]["has_blocking_failures"] else "passed",
        )
        db.add(run_row)

    mv.calculation_snapshot_json = scenarios
    db.commit()
    audit.record(
        db,
        entity_type="model_version",
        entity_id=mv.id,
        action="calculate",
        actor_id=user.id,
        deal_id=mv.deal_id,
        new_value={"scenarios": list(scenarios.keys())},
    )
    db.commit()
    return schemas.ValuationRunOut(scenarios=scenarios)


@router.get("/api/model-versions/{model_version_id}/outputs", response_model=schemas.ValuationRunOut)
def get_outputs(model_version_id: uuid.UUID, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    mv = _get_model_version(model_version_id, db, user)
    if not mv.calculation_snapshot_json:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Model version has not been calculated yet.")
    return schemas.ValuationRunOut(scenarios=mv.calculation_snapshot_json)


@router.post("/api/model-versions/{model_version_id}/approve", response_model=schemas.ModelVersionOut)
def approve_model_version(
    model_version_id: uuid.UUID, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)
):
    """PRD 7.16: only approved models can be designated as official exports;
    a model cannot be approved while material unresolved mappings or failed
    balance checks exist, unless the user has already recorded an override
    (surfaced here as a hard block — no override flow implemented in this
    slice, so a blocking check simply prevents approval)."""
    mv = _get_model_version(model_version_id, db, user)
    require_editor(mv.deal_id, db, user)
    if not mv.calculation_snapshot_json:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Calculate the model version before approving it.")

    blocking = [
        scenario
        for scenario, result in mv.calculation_snapshot_json.items()
        if result["model_checks"]["has_blocking_failures"]
    ]
    if blocking:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot approve: blocking model-check failures in scenario(s) {blocking}.",
        )

    mv.status = "approved"
    mv.approved_by = user.id
    mv.approved_at = dt.datetime.now(dt.timezone.utc)
    db.commit()
    db.refresh(mv)
    audit.record(db, entity_type="model_version", entity_id=mv.id, action="approve", actor_id=user.id, deal_id=mv.deal_id)
    db.commit()
    return mv


@router.get("/api/model-versions/{model_version_id}/sensitivities/wacc-vs-growth", response_model=schemas.SensitivityGridOut)
def wacc_vs_growth_sensitivity(
    model_version_id: uuid.UUID,
    scenario: str = "base",
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """PRD 7.8 required sensitivity: WACC vs terminal growth rate."""
    mv = _get_model_version(model_version_id, db, user)
    if not mv.calculation_snapshot_json or scenario not in mv.calculation_snapshot_json:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"No calculated results for scenario '{scenario}'.")

    dcf = mv.calculation_snapshot_json[scenario]["dcf"]
    ufcf_by_year = {dy["fiscal_year"]: dy["ufcf"] for dy in dcf["discounted_years"]}
    assumption_set = db.query(models.AssumptionSet).filter_by(deal_id=mv.deal_id, scenario=scenario).first()

    base_inputs = DCFInputs(
        ufcf_by_year=ufcf_by_year,
        wacc=dcf["wacc"],
        terminal_growth_rate=dcf["terminal_growth_rate"],
        valuation_date_fiscal_year=min(ufcf_by_year) - 1,
        cash=0.0,
        debt=0.0,
    )
    wacc_center = assumption_set.wacc if assumption_set else dcf["wacc"]
    g_center = assumption_set.terminal_growth_rate if assumption_set else dcf["terminal_growth_rate"]
    wacc_values = [round(wacc_center + delta, 4) for delta in (-0.02, -0.01, 0.0, 0.01, 0.02)]
    g_values = [round(g_center + delta, 4) for delta in (-0.01, -0.005, 0.0, 0.005, 0.01)]

    grid = wacc_vs_terminal_growth_grid(base_inputs, wacc_values, g_values)
    return schemas.SensitivityGridOut(
        row_label=grid.row_label,
        column_label=grid.column_label,
        row_values=grid.row_values,
        column_values=grid.column_values,
        grid=grid.grid,
        metric=grid.metric,
    )
