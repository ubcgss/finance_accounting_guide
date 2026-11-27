#--------------------------------------------------------------------------------------------
# File name:         test_budget_checks.py
# Creation date:     2026-11-25
# Author:            César Landín
# Files used:
#   - assets/budget-check/budget_checks.py
# Files created:
#   - Temporary .xlsx test workbooks in tempfile.TemporaryDirectory
# Purpose:
#   - Unit tests for budget integrity checks, sorting, and Markdown report rendering.
#--------------------------------------------------------------------------------------------

from contextlib import contextmanager
import datetime
from pathlib import Path
import tempfile
import unittest

import openpyxl

import sys

# The checker lives with the web page it runs in; put that folder on the import path.
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "assets" / "budget-check"))
import budget_checks  # noqa: E402


##########################################
##  (1): Test workbook builder helper.  ##
##########################################
# (1.1): Context manager that writes a synthetic .xlsx and opens both workbook views.
def populate_workbook(sheets: dict[str, dict[str, object]], target_path: Path) -> None:
    """Write sheets dict into an .xlsx file; (val, 's') forces text data_type."""
    wb = openpyxl.Workbook()
    if "Sheet" not in sheets:
        wb.remove(wb.active)

    for idx, (sheet_name, cells) in enumerate(sheets.items()):
        if idx == 0 and "Sheet" in sheets and sheet_name == "Sheet":
            ws = wb.active
        else:
            ws = wb.create_sheet(title=sheet_name)
        for coord, value in cells.items():
            if isinstance(value, tuple) and len(value) == 2 and value[1] == "s":
                ws[coord] = value[0]
                ws[coord].data_type = "s"
            else:
                ws[coord] = value

    wb.save(target_path)
    wb.close()


def build_assumptions_sheet(
    rows: list[tuple[str, object, datetime.date | None, datetime.date | None, str, str]],
    fy_start: datetime.date = datetime.date(2026, 6, 1),
    fy_end: datetime.date = datetime.date(2027, 5, 31),
    cpi: float | None = 0.022,
) -> dict[str, object]:
    """Build a new-layout Assumptions sheet with headers in A3:I3 and Fiscal year in row 4."""
    cells: dict[str, object] = {
        "A1": "PARAMETERS - FY 2026-27",
        "A2": "Rows needing attention:",
        "B2": '=COUNTIFS(C4:C100,"<>",C4:C100,"<>OK",C4:C100,"<>History")',
        "A3": "Parameter",
        "B3": "Value",
        "C3": "Status",
        "D3": "Valid from",
        "E3": "Valid until",
        "F3": "Basis",
        "G3": "Source",
        "H3": "CPI-inflated previous",
        "I3": "Notes",
        "A4": "Fiscal year",
        "B4": "2026-27",
        "D4": fy_start,
        "E4": fy_end,
    }
    next_row = 5
    if cpi is not None:
        cells[f"A{next_row}"] = "CPI"
        cells[f"B{next_row}"] = cpi
        cells[f"D{next_row}"] = fy_start
        cells[f"E{next_row}"] = fy_end
        cells[f"F{next_row}"] = "Published rate"
        cells[f"G{next_row}"] = "StatsCan"
        next_row += 1

    for offset, (param, val, vf, vu, basis, source) in enumerate(rows):
        row = next_row + offset
        cells[f"A{row}"] = param
        if val is not None:
            cells[f"B{row}"] = val
        if vf is not None:
            cells[f"D{row}"] = vf
        if vu is not None:
            cells[f"E{row}"] = vu
        if basis:
            cells[f"F{row}"] = basis
        if source:
            cells[f"G{row}"] = source
    return cells


@contextmanager
def make_workbook(
    sheets: dict[str, dict[str, object]],
    cached_overrides: dict[str, dict[str, object]] | None = None,
):
    """Build an .xlsx in a temp dir and yield (wb_formulas, wb_values, path)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        xlsx_path = Path(tmpdir) / "synthetic_budget.xlsx"
        populate_workbook(sheets, xlsx_path)

        values_path = xlsx_path
        if cached_overrides is not None:
            merged = {
                name: dict(cells) for name, cells in sheets.items()
            }
            for sheet_name, overrides in cached_overrides.items():
                merged.setdefault(sheet_name, {}).update(overrides)
            values_path = Path(tmpdir) / "synthetic_values.xlsx"
            populate_workbook(merged, values_path)

        wb_formulas = openpyxl.load_workbook(xlsx_path, data_only=False)
        wb_values = openpyxl.load_workbook(values_path, data_only=True)
        try:
            yield wb_formulas, wb_values, xlsx_path
        finally:
            wb_formulas.close()
            wb_values.close()


####################################################
##  (2): Unit tests for budget integrity checks.  ##
####################################################
class BudgetChecksTests(unittest.TestCase):
    """Verify each integrity check rule, sorting order, and Markdown rendering."""

    # (2.1): Rolled-forward formula detection on department tabs.
    def test_rolled_forward_flags_and_ignores(self) -> None:
        sheets = {
            "Assumptions": {"A30": "CPI", "B30": 0.022},
            "10-CORP": {
                "R3": "2025-2026 Budget",
                "S3": "2025-2026 Actuals (Projected)",
                "B7": 4100,
                "C7": "Student Fees",
                "D7": "=S7*(1+Assumptions!$B$30)",
                "B8": 4200,
                "C8": "Interest",
                "D8": "=SUM(E8:P8)",
                "E8": "=$D7/12",
                "B36": 6200,
                "C36": "Audit",
                "D36": "=R36*1.02",
            },
            "720-10": {
                "B5": 5000,
                "C5": "Driver Line",
                "D5": "=R5*1.02",
            },
        }
        with make_workbook(sheets) as (wb_form, wb_val, unused_path):
            findings = budget_checks.check_rolled_forward(wb_form, wb_val)

        by_cell = {item["cell"]: item for item in findings}
        self.assertEqual(set(by_cell.keys()), {"D7", "D36"})
        self.assertEqual(by_cell["D36"]["severity"], "high")
        self.assertIn("2025-2026 Budget", by_cell["D36"]["why"])
        self.assertIn("1.02", by_cell["D36"]["why"])
        self.assertEqual(by_cell["D7"]["severity"], "review")
        self.assertIn("2025-2026 Actuals (Projected)", by_cell["D7"]["why"])

    # (2.2): Hard-coded literals inside formulas, sheet scope, and text-vs-formula check.
    def test_hard_coded_formula_literals(self) -> None:
        sheets = {
            "Assumptions": {"A30": "CPI", "B30": 0.022},
            "10-CORP": {
                "B6": 4000,
                "C6": "Fee",
                "E6": "=192678.18*(1+Assumptions!$B$30)",
                "B7": 4100,
                "C7": "Monthly",
                "E7": "=$D7/12",
                "B16": 4300,
                "C16": "WL",
                "D16": (
                    "=SUMIFS('WL Supporting'!$U$38:$U$47,"
                    "'WL Supporting'!$A$38:$A$47,$B$3,"
                    "'WL Supporting'!$B$38:$B$47,\"WL\")"
                ),
                "B18": 4400,
                "C18": "Quarterly",
                "E18": "=$D18/4",
            },
            "11-PRES": {
                "B44": 6400,
                "C44": "Travel",
                "D44": "=18926*200/175",
            },
            "Consolidated": {
                "B36": 6200,
                "C36": "Audit",
                "D36": (
                    "=SUMIF('10-CORP'!$B:$B,$B36,'10-CORP'!D:D)"
                    "+SUMIF('11-PRES'!$B:$B,$B36,'11-PRES'!D:D)"
                ),
            },
            "FT Staff": {
                "A1": "=DATE(2026,6,1)",
                "A2": '=_xlfn.TEXTBEFORE(_xlfn.TEXTAFTER(C3,"Dept "), " Budget")',
                "A3": ("= Earnings x 3.8%", "s"),
            },
            # Reporting tabs are outside hard_coded scan scope.
            "Dashboard": {
                "A1": "=18926*200",
                "A2": 125,
            },
        }
        with make_workbook(sheets) as (wb_form, wb_val, unused_path):
            findings = budget_checks.check_hard_coded(wb_form, wb_val)

        flagged = {(item["sheet"], item["cell"]): item for item in findings}
        self.assertEqual(set(flagged.keys()), {("10-CORP", "E6"), ("11-PRES", "D44")})
        self.assertEqual(flagged[("10-CORP", "E6")]["severity"], "high")
        self.assertEqual(flagged[("11-PRES", "D44")]["severity"], "high")
        self.assertIn("18926", flagged[("11-PRES", "D44")]["why"])
        self.assertIn("200", flagged[("11-PRES", "D44")]["why"])
        self.assertIn("175", flagged[("11-PRES", "D44")]["why"])

    # (2.3): Typed non-zero numbers among formulas (column rule on drivers, row rule on depts).
    def test_hard_coded_typed_among_formulas(self) -> None:
        honoraria = {
            "N7": "May 2027",
            "N18": "=SUM(N8:N17)",
        }
        for row in range(8, 15):
            honoraria[f"A{row}"] = f"Role {row}"
            honoraria[f"B{row}"] = 964.14
            honoraria[f"C{row}"] = 0
            honoraria[f"N{row}"] = "=$D$6"
        for row in range(15, 18):
            honoraria[f"A{row}"] = f"Role {row}"
            honoraria[f"B{row}"] = 964.14
            honoraria[f"C{row}"] = 0
            honoraria[f"N{row}"] = 1768.9941

        # Typed Expense/Income columns with 1 SUM and all-formula Total column must not flag.
        dept14_events = {
            "C4": "Expense",
            "D4": "Income",
            "E4": "Net Total",
            "C11": "=SUM(C5:C10)",
            "D11": "=SUM(D5:D10)",
            "E11": "=SUM(E5:E10)",
        }
        for row in range(5, 11):
            dept14_events[f"C{row}"] = 100 * row
            dept14_events[f"D{row}"] = 200 * row
            dept14_events[f"E{row}"] = f"=D{row}-C{row}"

        sheets = {
            "Honoraria": honoraria,
            "Dept14 Events": dept14_events,
            "10-CORP": {
                "B7": 4100,
                "C7": "Fees",
                "E7": "=$D7/12",
                "F7": 500,
                "G7": "=$D7/12",
                "H7": 0,
                "I7": "=$D7/12",
            },
        }
        with make_workbook(sheets) as (wb_form, wb_val, unused_path):
            findings = budget_checks.check_hard_coded(wb_form, wb_val)

        flagged = {(item["sheet"], item["cell"]) for item in findings}
        self.assertEqual(
            flagged,
            {
                ("Honoraria", "N15"),
                ("Honoraria", "N16"),
                ("Honoraria", "N17"),
                ("10-CORP", "F7"),
            },
        )
        self.assertTrue(all(item["severity"] == "high" for item in findings))

    # (2.3b): Text cells starting with '=' (data_type 's') are ignored by every rule.
    def test_text_starting_with_equals_ignored(self) -> None:
        sheets = {
            "Chart of Accounts - Accounts": {"A1": 4100},
            "10-CORP": {
                "R3": "2025-2026 Budget",
                "B7": 4100,
                "C7": "Fees",
                "D7": ("=R7*1.05", "s"),
                "E7": ("=18926*2", "s"),
                "F7": ("= Earnings x 3.8%", "s"),
            },
            "FT Staff": {
                "A1": ("= Earnings x 3.8%", "s"),
            },
        }
        with make_workbook(sheets) as (wb_form, wb_val, unused_path):
            self.assertEqual(budget_checks.check_rolled_forward(wb_form, wb_val), [])
            self.assertEqual(budget_checks.check_hard_coded(wb_form, wb_val), [])
            self.assertEqual(budget_checks.check_consistency(wb_form, wb_val), [])

    # (2.3c): Reporting tabs are never scanned by hard_coded.
    def test_reporting_tabs_not_scanned_by_hard_coded(self) -> None:
        sheets = {
            "Assumptions": {"A18": "EH Prem", "B18": 125},
            "Funder Report": {
                "A1": "=18926*200",
                "A2": 125,
                "B1": "=A1*1",
                "B2": "=A1*1",
                "B3": "=A1*1",
                "B4": 999,
            },
            "T3010 Year-End": {"A1": "=192678.18*1.05"},
            "AccountMap": {"A1": 125},
            "Monthly Cashflow": {"A1": "=500*1.2"},
            "Dashboard": {"A1": "=999*2"},
        }
        with make_workbook(sheets) as (wb_form, wb_val, unused_path):
            self.assertEqual(budget_checks.check_hard_coded(wb_form, wb_val), [])

    # (2.3d): Row rule on dept/Consolidated skips non-line rows and never scans R/S/T.
    def test_hard_coded_row_rule_skips_non_line_rows_and_rst(self) -> None:
        sheets = {
            "Assumptions": {"A18": "EH Prem", "B18": 125},
            "14-VPSTD": {
                "B7": 4100,
                "C7": "Line",
                "E7": "=$D7/12",
                "F7": 500,
                "G7": "=$D7/12",
                "R7": 125,
                "S7": 125,
                "T7": "Prior note",
                # Non-line event-planning table (no int code in B): must be skipped.
                "A98": "Grad Gala",
                "E98": "=SUM(C98:D98)",
                "F98": 500,
                "G98": "=F98-E98",
            },
            "Consolidated": {
                "B4": 4000,
                "C4": "Fees",
                "E4": "=SUMIF('14-VPSTD'!$B:$B,$B4,'14-VPSTD'!E:E)",
                "F4": 500,
                "G4": "=SUMIF('14-VPSTD'!$B:$B,$B4,'14-VPSTD'!G:G)",
                "B21": 4200,
                "C21": "Prior Totals",
                "R21": 125,
                "S21": 125,
                "B22": 4300,
                "R22": "=SUMIF('14-VPSTD'!$B:$B,$B22,'14-VPSTD'!R:R)",
                "S22": "=SUMIF('14-VPSTD'!$B:$B,$B22,'14-VPSTD'!S:S)",
                "B23": 4400,
                "R23": "=SUMIF('14-VPSTD'!$B:$B,$B23,'14-VPSTD'!R:R)",
                "S23": "=SUMIF('14-VPSTD'!$B:$B,$B23,'14-VPSTD'!S:S)",
                "B24": 4500,
                "R24": "=SUMIF('14-VPSTD'!$B:$B,$B24,'14-VPSTD'!R:R)",
                "S24": "=SUMIF('14-VPSTD'!$B:$B,$B24,'14-VPSTD'!S:S)",
            },
        }
        with make_workbook(sheets) as (wb_form, wb_val, unused_path):
            findings = budget_checks.check_hard_coded(wb_form, wb_val)

        flagged = {(item["sheet"], item["cell"]) for item in findings}
        self.assertEqual(flagged, {("14-VPSTD", "F7"), ("Consolidated", "F4")})

    # (2.3e): MID/LEFT/RIGHT and ROUND/ROUNDUP/ROUNDDOWN integer arguments are ignored.
    def test_hard_coded_ignores_mid_left_right_and_round_args(self) -> None:
        sheets = {
            "FT Staff": {
                "A1": "=MID(D31,6,2)",
                "A2": "=LEFT(C3,5)",
                "A3": "=RIGHT(C3,7)",
                "A4": "=ROUND(B4*1.05,2)",
                "A5": "=ROUNDUP(SUM(B1:B5)*1.03,2)",
                "A6": "=ROUNDDOWN(B6*2.5,3)",
            }
        }
        with make_workbook(sheets) as (wb_form, wb_val, unused_path):
            findings = budget_checks.check_hard_coded(wb_form, wb_val)

        by_cell = {item["cell"]: item for item in findings}
        self.assertEqual(set(by_cell.keys()), {"A4", "A5", "A6"})
        self.assertIn("Contains the typed number(s) 1.05 inside", by_cell["A4"]["why"])
        self.assertIn("Contains the typed number(s) 1.03 inside", by_cell["A5"]["why"])
        self.assertIn("Contains the typed number(s) 2.5 inside", by_cell["A6"]["why"])

    # (2.4): Parameter match flags copies while skipping Assumptions source cells.
    def test_hard_coded_should_be_parameter_and_skips_source(self) -> None:
        sheets = {
            "Assumptions": {
                "A14": "CPP Annual Maximum",
                "B14": "='CPP EI RRSP'!$B$5",
                "A18": "Extended Health Prem/mo",
                "B18": 125,
            },
            "CPP EI RRSP": {
                "A5": "CPP Max",
                "B5": 68500,
            },
            "10-CORP": {
                "B10": 6100,
                "C10": "Extended Health",
                "E10": 125,
                "E11": "=125*12",
                "E12": 68500,
            },
        }
        cached = {"Assumptions": {"B14": 68500}}
        with make_workbook(sheets, cached_overrides=cached) as (wb_form, wb_val, unused_path):
            findings = budget_checks.check_hard_coded(wb_form, wb_val)

        by_loc = {(item["sheet"], item["cell"]): item for item in findings}
        self.assertEqual(
            set(by_loc.keys()),
            {("10-CORP", "E10"), ("10-CORP", "E11"), ("10-CORP", "E12")},
        )
        self.assertNotIn(("CPP EI RRSP", "B5"), by_loc)
        self.assertEqual(by_loc[("10-CORP", "E10")]["severity"], "review")
        self.assertIn("Assumptions!B18", by_loc[("10-CORP", "E10")]["why"])
        self.assertEqual(by_loc[("10-CORP", "E11")]["severity"], "high")
        self.assertIn("Assumptions!B18", by_loc[("10-CORP", "E11")]["why"])
        self.assertEqual(by_loc[("10-CORP", "E12")]["severity"], "review")
        self.assertIn("Assumptions!B14", by_loc[("10-CORP", "E12")]["why"])

    # (2.4b): Rolled-forward cells are not duplicated as hard_coded (a) findings.
    def test_dedup_rolled_forward_and_hard_coded(self) -> None:
        sheets = {
            "Assumptions": {"A30": "CPI", "B30": 0.022},
            "Chart of Accounts - Accounts": {"A1": 6200},
            "10-CORP": {
                "R3": "2025-2026 Budget",
                "B36": 6200,
                "C36": "Audit",
                "D36": "=R36*1.02",
                "E36": 100,
                "Q36": 100,
            },
            "Consolidated": {
                "B4": 6200,
                "C4": "Audit",
                "D4": 0,
                "E4": 0,
                "Q4": 0,
            },
        }
        with make_workbook(sheets) as (unused_f, unused_v, xlsx_path):
            findings = budget_checks.run_checks(xlsx_path)

        d36_findings = [
            item
            for item in findings
            if item["sheet"] == "10-CORP" and item["cell"] == "D36"
        ]
        self.assertEqual(len(d36_findings), 1)
        self.assertEqual(d36_findings[0]["check"], "rolled_forward")
        self.assertEqual(d36_findings[0]["severity"], "high")
        self.assertIn("1.02", d36_findings[0]["why"])

    # (2.5): Old Assumptions layouts return a single "not set up" high finding.
    def test_parameters_old_layout_not_set_up(self) -> None:
        old_headerless = {
            "Assumptions": {
                "A5": "Fiscal Year Label",
                "B5": "2026-27",
                "A6": "Budget FY Start Year",
                "B6": 2026,
                "A30": "CPI",
                "B30": 0.022,
                "C30": "Named range: CPI_RATE",
            },
            "10-CORP": {"D7": "=S7*(1+Assumptions!$B$30)"},
        }
        with make_workbook(old_headerless) as (wb_form, wb_val, unused_path):
            findings = budget_checks.check_parameters(wb_form, wb_val)
            self.assertEqual(
                budget_checks.find_fy_bounds(wb_val[budget_checks.ASSUMPTIONS]),
                (datetime.date(2026, 6, 1), datetime.date(2027, 5, 31)),
            )
            self.assertEqual(
                budget_checks.find_cpi_rate(wb_val[budget_checks.ASSUMPTIONS]),
                0.022,
            )

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["check"], "parameters")
        self.assertEqual(findings[0]["severity"], "high")
        self.assertEqual(findings[0]["sheet"], "Assumptions")
        self.assertEqual(findings[0]["content"], "Parameters table not set up yet")
        self.assertIn("Budget Check", findings[0]["fix"])

        old_draft_headers = {
            "Assumptions": {
                "D3": "Kind",
                "E3": "Basis",
                "F3": "Source document",
                "I3": "Valid until",
                "A6": "Budget FY Start Year",
                "B6": 2026,
            }
        }
        with make_workbook(old_draft_headers) as (wb_form, wb_val, unused_path):
            draft_findings = budget_checks.check_parameters(wb_form, wb_val)

        self.assertEqual(len(draft_findings), 1)
        self.assertEqual(draft_findings[0]["severity"], "high")
        self.assertEqual(draft_findings[0]["content"], "Parameters table not set up yet")

    # (2.5b): History rows, band rows, and Fiscal year are never flagged or marked unused.
    def test_parameters_history_and_band_rows_ignored(self) -> None:
        assumptions = build_assumptions_sheet(
            [
                ("SECTION BAND", None, None, None, "", ""),
                (
                    "Old Lease",
                    4000,
                    datetime.date(2025, 6, 1),
                    datetime.date(2026, 5, 31),
                    "Estimate",
                    "",
                ),
            ]
        )
        sheets = {
            "Assumptions": assumptions,
            "Driver": {"A1": "=Assumptions!$B$5"},
        }
        with make_workbook(sheets) as (wb_form, wb_val, unused_path):
            findings = budget_checks.check_parameters(wb_form, wb_val)

        self.assertEqual(findings, [])

    # (2.5c): Split-period same-name rows satisfy lapsing/mid-year; single partial row flags.
    def test_parameters_split_periods_and_lapsing_or_midyear(self) -> None:
        two_periods = build_assumptions_sheet(
            [
                (
                    "CPP rate",
                    0.0595,
                    datetime.date(2026, 1, 1),
                    datetime.date(2026, 12, 31),
                    "Published rate",
                    "CRA T4127",
                ),
                (
                    "CPP rate",
                    0.0610,
                    datetime.date(2027, 1, 1),
                    datetime.date(2027, 12, 31),
                    "Published rate",
                    "CRA T4127",
                ),
            ]
        )
        sheets = {
            "Assumptions": two_periods,
            "Driver": {"A1": "=Assumptions!$B$5+Assumptions!$B$6+Assumptions!$B$7"},
        }
        with make_workbook(sheets) as (wb_form, wb_val, unused_path):
            findings = budget_checks.check_parameters(wb_form, wb_val)
        self.assertEqual(findings, [])

        # Removing the 2027 row causes the 2026 row to lapse before FY end (2027-05-31).
        lapsing_only = build_assumptions_sheet(
            [
                (
                    "CPP rate",
                    0.0595,
                    datetime.date(2026, 1, 1),
                    datetime.date(2026, 12, 31),
                    "Published rate",
                    "CRA T4127",
                ),
            ]
        )
        sheets_lapsing = {
            "Assumptions": lapsing_only,
            "Driver": {"A1": "=Assumptions!$B$5+Assumptions!$B$6"},
        }
        with make_workbook(sheets_lapsing) as (wb_form, wb_val, unused_path):
            lapsing_findings = budget_checks.check_parameters(wb_form, wb_val)

        self.assertEqual(len(lapsing_findings), 1)
        self.assertEqual(lapsing_findings[0]["severity"], "high")
        self.assertEqual(lapsing_findings[0]["cell"], "B6")
        self.assertEqual(lapsing_findings[0]["line"], "CPP rate")
        self.assertEqual(lapsing_findings[0]["content"], "0.0595 (2026-01-01 to 2026-12-31)")
        self.assertIn("Lapses before the fiscal year ends", lapsing_findings[0]["why"])

        # Keeping only the 2027 row triggers Starts mid-year.
        midyear_only = build_assumptions_sheet(
            [
                (
                    "CPP rate",
                    0.0610,
                    datetime.date(2027, 1, 1),
                    datetime.date(2027, 12, 31),
                    "Published rate",
                    "CRA T4127",
                ),
            ]
        )
        sheets_midyear = {
            "Assumptions": midyear_only,
            "Driver": {"A1": "=Assumptions!$B$5+Assumptions!$B$6"},
        }
        with make_workbook(sheets_midyear) as (wb_form, wb_val, unused_path):
            midyear_findings = budget_checks.check_parameters(wb_form, wb_val)

        self.assertEqual(len(midyear_findings), 1)
        self.assertEqual(midyear_findings[0]["severity"], "high")
        self.assertIn("Starts mid-year", midyear_findings[0]["why"])

    # (2.6): Status rules for No source, Estimate, and CPI (match, mismatch, no previous).
    def test_parameters_status_rules_source_estimate_cpi(self) -> None:
        assumptions = build_assumptions_sheet(
            [
                # Row 6: CPI match (prev 100 from 2025-06-01, curr 102.20 from 2026-06-01).
                (
                    "CPI Good",
                    100.00,
                    datetime.date(2025, 6, 1),
                    datetime.date(2026, 5, 31),
                    "Contract",
                    "SLA s.4",
                ),
                (
                    "CPI Good",
                    102.20,
                    datetime.date(2026, 6, 1),
                    datetime.date(2027, 5, 31),
                    "CPI",
                    "SLA s.4",
                ),
                # Row 8-9: CPI mismatch (110 vs 102.20) -> high.
                (
                    "CPI Bad",
                    100.00,
                    datetime.date(2025, 6, 1),
                    datetime.date(2026, 5, 31),
                    "Contract",
                    "SLA s.5",
                ),
                (
                    "CPI Bad",
                    110.00,
                    datetime.date(2026, 6, 1),
                    datetime.date(2027, 5, 31),
                    "CPI",
                    "SLA s.5",
                ),
                # Row 10: CPI with no previous period -> review.
                (
                    "CPI No Prev",
                    250.00,
                    datetime.date(2026, 6, 1),
                    datetime.date(2027, 5, 31),
                    "CPI",
                    "Vendor quote",
                ),
                # Row 11: Basis Estimate -> review.
                (
                    "Audit Estimate",
                    18000,
                    datetime.date(2026, 6, 1),
                    datetime.date(2027, 5, 31),
                    "Estimate",
                    "Prior invoice",
                ),
                # Row 12: No source (even with Estimate basis, rule 3 wins) -> high.
                (
                    "Missing Source",
                    500,
                    datetime.date(2026, 6, 1),
                    datetime.date(2027, 5, 31),
                    "Estimate",
                    "",
                ),
            ]
        )
        usage_formula = (
            "=Assumptions!B5+Assumptions!B7+Assumptions!B9"
            "+Assumptions!B10+Assumptions!B11+Assumptions!B12"
        )
        sheets = {
            "Assumptions": assumptions,
            "Driver": {"A1": usage_formula},
        }
        with make_workbook(sheets) as (wb_form, wb_val, unused_path):
            findings = budget_checks.check_parameters(wb_form, wb_val)
            self.assertEqual(
                budget_checks.find_fy_bounds(wb_val[budget_checks.ASSUMPTIONS]),
                (datetime.date(2026, 6, 1), datetime.date(2027, 5, 31)),
            )
            self.assertEqual(
                budget_checks.find_cpi_rate(wb_val[budget_checks.ASSUMPTIONS]),
                0.022,
            )

        by_line = {item["line"]: item for item in findings}
        self.assertEqual(set(by_line.keys()), {"CPI Bad", "CPI No Prev", "Audit Estimate", "Missing Source"})
        self.assertEqual(by_line["CPI Bad"]["severity"], "high")
        self.assertEqual(by_line["CPI Bad"]["cell"], "B9")
        self.assertIn("102.20", by_line["CPI Bad"]["why"])
        self.assertEqual(by_line["CPI No Prev"]["severity"], "review")
        self.assertEqual(by_line["CPI No Prev"]["cell"], "B10")
        self.assertEqual(by_line["Audit Estimate"]["severity"], "review")
        self.assertEqual(by_line["Audit Estimate"]["cell"], "B11")
        self.assertEqual(by_line["Missing Source"]["severity"], "high")
        self.assertEqual(by_line["Missing Source"]["cell"], "B12")
        self.assertIn("No source", by_line["Missing Source"]["why"])

    # (2.6b): Unused active parameters are grouped once; Fiscal year, bands, and History skipped.
    def test_parameters_unused_grouped(self) -> None:
        assumptions = build_assumptions_sheet(
            [
                ("BENEFITS", None, None, None, "", ""),
                (
                    "Old Benefit",
                    0.03,
                    datetime.date(2025, 6, 1),
                    datetime.date(2026, 5, 31),
                    "Policy",
                    "Handbook",
                ),
                (
                    "RRSP Match",
                    0.04,
                    datetime.date(2026, 6, 1),
                    datetime.date(2027, 5, 31),
                    "HFC decision",
                    "HFC Minutes",
                ),
                (
                    "WL Wage Rate",
                    26.02,
                    datetime.date(2026, 6, 1),
                    datetime.date(2027, 5, 31),
                    "Published rate",
                    "UBC WorkLearn",
                ),
            ]
        )
        sheets = {
            "Assumptions": assumptions,
            "Driver": {"A1": "=Assumptions!$B$5"},
        }
        with make_workbook(sheets) as (wb_form, wb_val, unused_path):
            findings = budget_checks.check_parameters(wb_form, wb_val)

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["severity"], "review")
        self.assertIn("RRSP Match (B8)", findings[0]["why"])
        self.assertIn("WL Wage Rate (B9)", findings[0]["why"])
        self.assertNotIn("Fiscal year", findings[0]["why"])
        self.assertNotIn("BENEFITS", findings[0]["why"])
        self.assertNotIn("Old Benefit", findings[0]["why"])

    # (2.6c): Out-of-period parameter usage on dept tabs and driver tabs.
    def test_parameters_used_outside_valid_period(self) -> None:
        assumptions = build_assumptions_sheet(
            [
                (
                    "CPP rate",
                    0.0595,
                    datetime.date(2026, 1, 1),
                    datetime.date(2026, 12, 31),
                    "Published rate",
                    "CRA T4127",
                ),
                (
                    "CPP rate",
                    0.0610,
                    datetime.date(2027, 1, 1),
                    datetime.date(2027, 12, 31),
                    "Published rate",
                    "CRA T4127",
                ),
            ]
        )
        months = [
            "Jun 2026", "Jul 2026", "Aug 2026", "Sep 2026", "Oct 2026", "Nov 2026",
            "Dec 2026", "Jan 2027", "Feb 2027", "Mar 2027", "Apr 2027", "May 2027",
        ]
        driver_sheet: dict[str, object] = {"A4": "FT Staff CPP", "B4": 5000}
        for idx, label in enumerate(months):
            col_letter = openpyxl.utils.get_column_letter(3 + idx)
            driver_sheet[f"{col_letter}3"] = label
        # D4 is Jul 2026 (valid for B6); J4 is Jan 2027 (outside B6).
        driver_sheet["D4"] = "=B4*Assumptions!$B$6"
        driver_sheet["J4"] = "=B4*Assumptions!$B$6"

        sheets = {
            "Assumptions": assumptions,
            "10-CORP": {
                "B5": 4000,
                "C5": "CPI Line",
                "D5": "=S5*(1+Assumptions!$B$5)",
                "B14": 6150,
                "C14": "Employer CPP",
                # F14 is Jul 2026 (valid for B6); L14 is Jan 2027 (outside B6); P14 uses B7 (valid).
                "F14": "=D14*Assumptions!$B$6",
                "L14": "=D14*Assumptions!$B$6",
                "P14": "=D14*Assumptions!$B$7",
                # Contiguous out-of-period range L15:N15 (Jan 2027-Mar 2027).
                "B15": 6151,
                "C15": "Employer CPP 2",
                "L15": "=D15*'Assumptions'!$B$6",
                "M15": "=D15*'Assumptions'!$B$6",
                "N15": "=D15*'Assumptions'!$B$6",
            },
            "CPP EI RRSP": driver_sheet,
        }
        with make_workbook(sheets) as (wb_form, wb_val, unused_path):
            findings = budget_checks.check_parameters(wb_form, wb_val)

        by_loc = {(item["sheet"], item["cell"]): item for item in findings}
        self.assertEqual(
            set(by_loc.keys()),
            {
                ("10-CORP", "L14"),
                ("10-CORP", "L15:N15"),
                ("CPP EI RRSP", "J4"),
            },
        )
        self.assertEqual(by_loc[("10-CORP", "L14")]["severity"], "high")
        self.assertEqual(by_loc[("10-CORP", "L14")]["code"], 6150)
        self.assertEqual(by_loc[("10-CORP", "L14")]["line"], "Employer CPP")
        self.assertIn("Uses CPP rate valid 2026-01-01 to 2026-12-31 for Jan 2027", by_loc[("10-CORP", "L14")]["why"])
        self.assertIn("Link these months to the CPP rate row that covers them", by_loc[("10-CORP", "L14")]["fix"])

        self.assertEqual(by_loc[("10-CORP", "L15:N15")]["content"], "=D15*'Assumptions'!$B$6")
        self.assertIn("Jan 2027-Mar 2027", by_loc[("10-CORP", "L15:N15")]["why"])

        self.assertEqual(by_loc[("CPP EI RRSP", "J4")]["line"], "FT Staff CPP")
        self.assertIn("Jan 2027", by_loc[("CPP EI RRSP", "J4")]["why"])

    # (2.7): Consistency checks (grouped COA, text dash, Q != sum(E:P), Consolidated mismatch).
    def test_consistency_checks(self) -> None:
        sheets = {
            "Chart of Accounts - Accounts": {
                "A1": 4000,
                "A2": 6200,
            },
            "10-CORP": {
                "B4": 4000,
                "C4": "Fees",
                "D4": 1200,
                "E4": 100,
                "F4": "-",
                "G4": ("= Earnings x 3.8%", "s"),
                "Q4": 1000,
                "B13": 4330,
                "C13": "Missing COA Line",
                "D13": 100,
                "E13": 100,
                "Q13": 100,
            },
            "11-PRES": {
                "B10": 4330,
                "C10": "Missing COA Line",
                "D10": 50,
                "E10": 50,
                "Q10": 50,
            },
            "Consolidated": {
                "B4": 4000,
                "C4": "Fees",
                "D4": 1500,
                "E4": 1500,
                "Q4": 1500,
                "B10": 4330,
                "C10": "Missing COA Line",
                "D10": 150,
                "E10": 150,
                "Q10": 150,
            },
        }
        with make_workbook(sheets) as (wb_form, wb_val, unused_path):
            findings = budget_checks.check_consistency(wb_form, wb_val)

        locations = {(item["sheet"], item["cell"], item["code"]) for item in findings}
        self.assertIn(("10-CORP", "F4", 4000), locations)
        self.assertIn(("10-CORP", "Q4", 4000), locations)
        self.assertIn(("10-CORP", "D4", 4000), locations)
        self.assertIn(("Consolidated", "D4", 4000), locations)

        coa_findings = [item for item in findings if item["code"] == 4330]
        self.assertEqual(len(coa_findings), 1)
        self.assertEqual(coa_findings[0]["sheet"], "10-CORP")
        self.assertEqual(coa_findings[0]["cell"], "B13")
        self.assertIn("10-CORP, 11-PRES, Consolidated", coa_findings[0]["why"])

    # (2.7b): Uncached Consolidated formulas skip value-based consistency checks.
    def test_consistency_missing_cached_values(self) -> None:
        sheets = {
            "Chart of Accounts - Accounts": {"A1": 4000},
            "10-CORP": {
                "B4": 4000,
                "C4": "Fees",
                "D4": 1200,
                "E4": 100,
                "Q4": 1000,
            },
            "Consolidated": {
                "B4": 4000,
                "C4": "Fees",
                "D4": "=SUMIF('10-CORP'!$B:$B,$B4,'10-CORP'!D:D)",
            },
        }
        with make_workbook(sheets) as (wb_form, wb_val, unused_path):
            findings = budget_checks.check_consistency(wb_form, wb_val)

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["severity"], "review")
        self.assertIn("Cached values are missing", findings[0]["why"])

    # (2.7c): External workbook links and formula references are flagged in consistency.
    def test_consistency_external_workbook_links(self) -> None:
        sheets = {
            "Chart of Accounts - Accounts": {"A1": 4000},
            "10-CORP": {
                "B4": 4000,
                "C4": "Fees",
                "D4": 100,
                "E4": 100,
                "Q4": 100,
                "E5": "=[1]Sheet1!A1",
                "F5": "='[Other.xlsx]Budget'!$B$2",
            },
            "11-PRES": {
                "E4": "='C:\\temp\\[Book.xlsm]Sheet'!A1",
                "F4": "='C:\\temp\\[Book.xlsm]Sheet'!B1",
                "G4": "='C:\\temp\\[Book.xlsm]Sheet'!C1",
                "H4": "='C:\\temp\\[Book.xlsm]Sheet'!D1",
                "I4": "='C:\\temp\\[Book.xlsm]Sheet'!E1",
                "J4": "='https://example.com/[Book.xls]Sheet'!F1",
            },
            "Consolidated": {
                "B4": 4000,
                "C4": "Fees",
                "D4": 100,
                "E4": 100,
                "Q4": 100,
            },
        }
        with make_workbook(sheets) as (wb_form, wb_val, unused_path):
            wb_form._external_links = [object()]
            findings = budget_checks.check_consistency(wb_form, wb_val)

        by_sheet = {item["sheet"]: item for item in findings}
        self.assertIn("(workbook)", by_sheet)
        self.assertEqual(by_sheet["(workbook)"]["severity"], "high")
        self.assertIn("another file", by_sheet["(workbook)"]["why"])

        self.assertIn("10-CORP", by_sheet)
        self.assertEqual(by_sheet["10-CORP"]["severity"], "high")
        self.assertEqual(by_sheet["10-CORP"]["cell"], "E5, F5")
        self.assertEqual(by_sheet["10-CORP"]["content"], "=[1]Sheet1!A1")
        self.assertIn("another file", by_sheet["10-CORP"]["why"])

        self.assertIn("11-PRES", by_sheet)
        self.assertEqual(by_sheet["11-PRES"]["cell"], "E4, F4, G4, H4, I4")
        self.assertIn("(+1 more)", by_sheet["11-PRES"]["why"])

    # (2.8): Required lines check flags missing or zero-budget mandatory lines.
    def test_required_lines_missing_and_zero(self) -> None:
        sheets = {
            "Consolidated": {
                "B4": 6160,
                "C4": "WorkSafeBC",
                "D4": 5000,
                "B5": 6200,
                "C5": "Audit",
                "D5": 0,
                "B6": 6500,
                "C6": "Occupancy",
                "D6": 20000,
                "B7": 6550,
                "C7": "Insurance",
                "D7": 8000,
                "B8": 6580,
                "C8": "Bank Fees",
                "D8": 1200,
            }
        }
        with make_workbook(sheets) as (wb_form, wb_val, unused_path):
            findings = budget_checks.check_required_lines(wb_form, wb_val)

        by_code = {item["code"]: item for item in findings}
        self.assertEqual(set(by_code.keys()), {6150, 6200})
        self.assertEqual(by_code[6150]["severity"], "high")
        self.assertIn("No budget line", by_code[6150]["why"])
        self.assertEqual(by_code[6200]["severity"], "high")
        self.assertIn("has no budget", by_code[6200]["why"])

    # (2.9): Markdown report formatting (summary table, escaping, driver tabs).
    def test_render_markdown_summary_and_escaping(self) -> None:
        sample = [
            {
                "check": "hard_coded",
                "severity": "high",
                "sheet": "10-CORP",
                "cell": "D36",
                "code": 6200,
                "line": "Audit | Fees",
                "content": "=100|200\n+300",
                "why": "Line one\nLine two | detail",
                "fix": "Use | link",
            }
        ]
        md = budget_checks.render_markdown(
            sample,
            "Master.xlsx",
            "2026-11-25 14:30",
            driver_tabs=["FT Staff", "Honoraria"],
        )
        self.assertIn("# Budget Integrity Check", md)
        self.assertIn("## Summary", md)
        self.assertIn("| Parameters | 0 | 0 |", md)
        self.assertIn("| Hard-coded numbers | 1 | 0 |", md)
        self.assertIn("FT Staff, Honoraria", md)
        self.assertIn("Audit \\| Fees", md)
        self.assertIn("`=100\\|200 +300`", md)
        self.assertIn("Line one Line two \\| detail", md)
        self.assertIn("No findings.", md)

    # (2.10): End-to-end run_checks sorting places high severity before review.
    def test_run_checks_sorts_high_before_review(self) -> None:
        sheets = {
            "Assumptions": {
                "A30": "CPI",
                "B30": 0.022,
            },
            "Chart of Accounts - Accounts": {
                "A1": 6200,
            },
            "10-CORP": {
                "B7": 6200,
                "C7": "Audit",
                "D7": "=S7*(1+Assumptions!$B$30)",
                "E7": 100,
                "Q7": 100,
                "B36": 6200,
                "C36": "Other Audit",
                "D36": "=R36*1.02",
            },
            "Consolidated": {
                "B4": 6200,
                "C4": "Audit",
                "D4": 100,
                "E4": 100,
                "Q4": 100,
            },
        }
        with make_workbook(sheets) as (unused_f, unused_v, xlsx_path):
            findings = budget_checks.run_checks(xlsx_path)

        severities = [item["severity"] for item in findings]
        self.assertIn("high", severities)
        self.assertIn("review", severities)
        first_review = severities.index("review")
        self.assertTrue(all(sev == "high" for sev in severities[:first_review]))
        self.assertTrue(all(sev == "review" for sev in severities[first_review:]))


if __name__ == "__main__":
    unittest.main()
