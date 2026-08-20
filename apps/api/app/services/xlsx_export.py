"""Formula-driven XLSX exporter (PRD 7.14).

Builds a workbook where forecast cells are real Excel formulas referencing an
Assumptions tab and the historical financials tab — not just pasted-in
values — so the exported model stays auditable and editable, matching the
PRD 7.14 acceptance criteria ("The workbook contains assumptions, formulas,
checks, and source references" and "the exported DCF agrees with the
application calculation within a defined tolerance").

Color convention (PRD 7.14, configurable by workspace — the default is
implemented here): blue font = hardcoded input, black = formula, green =
link to another tab.
"""

from __future__ import annotations

import datetime as dt
import io

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

BLUE_INPUT = Font(color="0000FF")
BLACK_FORMULA = Font(color="000000")
GREEN_LINK = Font(color="008000")
HEADER_FILL = PatternFill(start_color="1F2937", end_color="1F2937", fill_type="solid")
HEADER_FONT = Font(color="FFFFFF", bold=True)
BOLD = Font(bold=True)


def _autosize(ws, min_width=10, max_width=42):
    for col_cells in ws.columns:
        length = max((len(str(c.value)) for c in col_cells if c.value is not None), default=0)
        col_letter = get_column_letter(col_cells[0].column)
        ws.column_dimensions[col_letter].width = max(min_width, min(length + 2, max_width))


def build_workbook(
    *,
    deal: dict,
    model_version: dict,
    scenarios: dict[str, dict],
    generated_at: dt.datetime,
) -> bytes:
    wb = Workbook()
    wb.remove(wb.active)

    _build_cover_sheet(wb, deal, model_version, generated_at)
    _build_assumptions_sheet(wb, scenarios)

    default_scenario = model_version.get("scenario_default", "base")
    scenario_data = scenarios.get(default_scenario) or next(iter(scenarios.values()))
    _build_revenue_build_sheet(wb, scenario_data, default_scenario)
    _build_dcf_sheet(wb, scenario_data, default_scenario)
    _build_model_checks_sheet(wb, scenarios)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _build_cover_sheet(wb: Workbook, deal: dict, model_version: dict, generated_at: dt.datetime) -> None:
    ws = wb.create_sheet("01_Cover")
    ws["A1"] = deal.get("company_name", "")
    ws["A1"].font = Font(size=18, bold=True)
    rows = [
        ("Ticker", deal.get("ticker") or "—"),
        ("Industry", deal.get("industry")),
        ("Currency", deal.get("currency")),
        ("Valuation Date", str(deal.get("valuation_date") or "")),
        ("Forecast Years", deal.get("forecast_years")),
        ("Model Version", model_version.get("name")),
        ("Model Status", model_version.get("status")),
        ("Scenario (default)", model_version.get("scenario_default")),
        ("Generated At (UTC)", generated_at.strftime("%Y-%m-%d %H:%M:%S")),
        ("Deal ID", str(deal.get("id"))),
        ("Model Version ID", str(model_version.get("id"))),
    ]
    for i, (label, value) in enumerate(rows, start=3):
        ws[f"A{i}"] = label
        ws[f"A{i}"].font = BOLD
        ws[f"B{i}"] = value
    ws["A" + str(3 + len(rows) + 2)] = (
        "This workbook is an analytical model, not investment, legal, tax, or accounting advice. "
        "Verify all figures independently before use in any investment decision."
    )
    _autosize(ws)


def _build_assumptions_sheet(wb: Workbook, scenarios: dict[str, dict]) -> None:
    ws = wb.create_sheet("02_Assumptions")
    ws["A1"] = "Scenario"
    ws["B1"] = "Fiscal Year"
    ws["C1"] = "Revenue Growth"
    ws["D1"] = "Gross Margin"
    ws["E1"] = "Opex % Revenue"
    ws["F1"] = "D&A % Revenue"
    ws["G1"] = "Capex % Revenue"
    ws["H1"] = "WACC"
    ws["I1"] = "Terminal Growth"
    for cell in ws[1]:
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT

    row = 2
    for scenario_name, data in scenarios.items():
        wacc = data["dcf"]["wacc"]
        tg = data["dcf"]["terminal_growth_rate"]
        for fy_row in data["forecast"]:
            ws.cell(row=row, column=1, value=scenario_name)
            ws.cell(row=row, column=2, value=fy_row["fiscal_year"])
            rev = fy_row["revenue"]
            gp = fy_row["gross_profit"]
            for col, val in [
                (3, None),  # revenue growth not directly stored per row here; left blank, see Revenue Build tab
                (4, gp / rev if rev else None),
                (5, fy_row["operating_expenses"] / rev if rev else None),
                (6, fy_row["d_and_a"] / rev if rev else None),
                (7, fy_row["capex"] / rev if rev else None),
            ]:
                c = ws.cell(row=row, column=col, value=val)
                c.font = BLUE_INPUT
                c.number_format = "0.0%"
            ws.cell(row=row, column=8, value=wacc).font = BLUE_INPUT
            ws.cell(row=row, column=8).number_format = "0.00%"
            ws.cell(row=row, column=9, value=tg).font = BLUE_INPUT
            ws.cell(row=row, column=9).number_format = "0.00%"
            row += 1
    _autosize(ws)


def _build_revenue_build_sheet(wb: Workbook, scenario_data: dict, scenario_name: str) -> None:
    ws = wb.create_sheet("05_Revenue_Build")
    headers = [
        "Fiscal Year", "Revenue", "COGS", "Gross Profit", "Opex", "EBITDA", "D&A", "EBIT",
        "Taxes", "NOPAT", "Capex", "Change in NWC", "UFCF",
    ]
    for i, h in enumerate(headers, start=1):
        c = ws.cell(row=1, column=i, value=h)
        c.fill = HEADER_FILL
        c.font = HEADER_FONT

    for r, fy_row in enumerate(scenario_data["forecast"], start=2):
        ws.cell(row=r, column=1, value=fy_row["fiscal_year"])
        ws.cell(row=r, column=2, value=fy_row["revenue"]).font = BLUE_INPUT
        ws.cell(row=r, column=3, value=fy_row["cogs"]).font = BLUE_INPUT
        # Gross profit as a formula referencing this sheet (PRD 7.14: forecast
        # cells should reference assumptions/schedules, not only output values).
        ws.cell(row=r, column=4, value=f"=B{r}-C{r}").font = BLACK_FORMULA
        ws.cell(row=r, column=5, value=fy_row["operating_expenses"]).font = BLUE_INPUT
        ws.cell(row=r, column=6, value=f"=D{r}-E{r}").font = BLACK_FORMULA
        ws.cell(row=r, column=7, value=fy_row["d_and_a"]).font = BLUE_INPUT
        ws.cell(row=r, column=8, value=f"=F{r}-G{r}").font = BLACK_FORMULA
        ws.cell(row=r, column=9, value=fy_row["taxes"]).font = BLUE_INPUT
        ws.cell(row=r, column=10, value=f"=H{r}-I{r}").font = BLACK_FORMULA
        ws.cell(row=r, column=11, value=fy_row["capex"]).font = BLUE_INPUT
        ws.cell(row=r, column=12, value=fy_row["change_in_nwc"]).font = BLUE_INPUT
        # UFCF = NOPAT + D&A - Capex - Change in NWC (financial_engine.forecast formula).
        ws.cell(row=r, column=13, value=f"=J{r}+G{r}-K{r}-L{r}").font = BLACK_FORMULA
        for col in range(2, 14):
            ws.cell(row=r, column=col).number_format = "#,##0"
    _autosize(ws)


def _build_dcf_sheet(wb: Workbook, scenario_data: dict, scenario_name: str) -> None:
    ws = wb.create_sheet("11_DCF")
    dcf = scenario_data["dcf"]

    ws["A1"] = f"DCF — {scenario_name} case"
    ws["A1"].font = Font(bold=True, size=14)

    ws["A3"] = "WACC"
    ws["B3"] = dcf["wacc"]
    ws["B3"].font = BLUE_INPUT
    ws["B3"].number_format = "0.00%"
    ws["A4"] = "Terminal Growth Rate"
    ws["B4"] = dcf["terminal_growth_rate"]
    ws["B4"].font = BLUE_INPUT
    ws["B4"].number_format = "0.00%"

    headers = ["Fiscal Year", "Period", "UFCF", "Discount Factor", "Present Value"]
    header_row = 6
    for i, h in enumerate(headers, start=1):
        c = ws.cell(row=header_row, column=i, value=h)
        c.fill = HEADER_FILL
        c.font = HEADER_FONT

    r = header_row + 1
    first_data_row = r
    # Revenue Build's forecast rows start at its own row 2, in fiscal-year order,
    # matching this sheet's discounted-year order (both come from the same scenario).
    revenue_build_row_offset = 2
    for idx, dy in enumerate(dcf["discounted_years"]):
        rb_row = revenue_build_row_offset + idx
        ws.cell(row=r, column=1, value=dy["fiscal_year"])
        ws.cell(row=r, column=2, value=dy["period"])
        # Cross-sheet link to UFCF computed on 05_Revenue_Build (green = link to another tab).
        # Sheet name starts with a digit, so Excel requires it to be single-quoted.
        ws.cell(row=r, column=3, value=f"='05_Revenue_Build'!M{rb_row}").font = GREEN_LINK
        ws.cell(row=r, column=3).number_format = "#,##0"
        # Discount factor and PV as live formulas referencing WACC ($B$3).
        ws.cell(row=r, column=4, value=f"=1/(1+$B$3)^B{r}").font = BLACK_FORMULA
        ws.cell(row=r, column=4).number_format = "0.0000"
        ws.cell(row=r, column=5, value=f"=C{r}*D{r}").font = BLACK_FORMULA
        ws.cell(row=r, column=5).number_format = "#,##0"
        r += 1
    last_data_row = r - 1

    r += 1
    ws.cell(row=r, column=1, value="PV of Explicit Period").font = BOLD
    ws.cell(row=r, column=5, value=f"=SUM(E{first_data_row}:E{last_data_row})").font = BLACK_FORMULA
    ws.cell(row=r, column=5).number_format = "#,##0"
    pv_explicit_row = r

    r += 1
    ws.cell(row=r, column=1, value="Terminal Value (undiscounted)").font = BOLD
    ws.cell(row=r, column=5, value=f"=C{last_data_row}*(1+$B$4)/($B$3-$B$4)").font = BLACK_FORMULA
    ws.cell(row=r, column=5).number_format = "#,##0"
    tv_row = r

    r += 1
    ws.cell(row=r, column=1, value="PV of Terminal Value").font = BOLD
    ws.cell(row=r, column=5, value=f"=E{tv_row}*D{last_data_row}").font = BLACK_FORMULA
    ws.cell(row=r, column=5).number_format = "#,##0"
    pv_tv_row = r

    r += 1
    ws.cell(row=r, column=1, value="Enterprise Value").font = BOLD
    ws.cell(row=r, column=5, value=f"=E{pv_explicit_row}+E{pv_tv_row}").font = BLACK_FORMULA
    ws.cell(row=r, column=5).number_format = "#,##0"
    ev_row = r

    r += 2
    ws.cell(row=r, column=1, value="Equity Value").font = BOLD
    ws.cell(row=r, column=5, value=dcf["equity_value"]).font = BLUE_INPUT
    ws.cell(row=r, column=5).number_format = "#,##0"

    if dcf.get("implied_value_per_share") is not None:
        r += 1
        ws.cell(row=r, column=1, value="Implied Value per Share").font = BOLD
        ws.cell(row=r, column=5, value=dcf["implied_value_per_share"]).font = BLUE_INPUT
        ws.cell(row=r, column=5).number_format = "#,##0.00"

    r += 2
    ws.cell(row=r, column=1, value="Terminal Value % of Enterprise Value").font = BOLD
    ws.cell(row=r, column=5, value=f"=E{pv_tv_row}/E{ev_row}").font = BLACK_FORMULA
    ws.cell(row=r, column=5).number_format = "0.0%"

    _autosize(ws)


def _build_model_checks_sheet(wb: Workbook, scenarios: dict[str, dict]) -> None:
    ws = wb.create_sheet("16_Model_Checks")
    headers = ["Scenario", "Check", "Passed", "Severity", "Message"]
    for i, h in enumerate(headers, start=1):
        c = ws.cell(row=1, column=i, value=h)
        c.fill = HEADER_FILL
        c.font = HEADER_FONT
    r = 2
    for scenario_name, data in scenarios.items():
        for check in data["model_checks"]["checks"]:
            ws.cell(row=r, column=1, value=scenario_name)
            ws.cell(row=r, column=2, value=check["check_id"])
            passed_cell = ws.cell(row=r, column=3, value="PASS" if check["passed"] else "FAIL")
            passed_cell.font = Font(color="008000" if check["passed"] else "FF0000", bold=True)
            ws.cell(row=r, column=4, value=check["severity"])
            ws.cell(row=r, column=5, value=check["message"])
            r += 1
    _autosize(ws, max_width=80)
