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

    # (2.5): Parameters check when Assumptions metadata columns are absent.
    def test_parameters_missing_headers_and_named_ranges(self) -> None:
        sheets = {
            "Assumptions": {
                "A5": "Fiscal Year Label",
                "B5": "2026-27",
                "C5": "Named range: FY_LABEL",
                "A30": "CPI",
                "B30": 0.022,
                "C30": "Named range: CPI_RATE",
            },
            "10-CORP": {
                "D7": "=S7*(1+Assumptions!$B$30)",
            },
        }
        with make_workbook(sheets) as (wb_form, wb_val, unused_path):
            findings = budget_checks.check_parameters(wb_form, wb_val)

        self.assertEqual(len(findings), 2)
        missing_hdr = [item for item in findings if "no source/validity columns" in item["why"]][0]
        missing_names = [item for item in findings if "named ranges" in item["why"]][0]
        self.assertEqual(missing_hdr["severity"], "review")
        self.assertEqual(missing_names["severity"], "review")
        self.assertIn("FY_LABEL (C5)", missing_names["why"])
        self.assertIn("CPI_RATE (C30)", missing_names["why"])

    # (2.5b): Unused parameters are grouped once and exclude Kind == Setting.
    def test_parameters_unused_grouped_and_skips_setting(self) -> None:
        sheets = {
            "Assumptions": {
                "D3": "Kind",
                "E3": "Basis",
                "F3": "Source document",
                "I3": "Valid until",
                "A6": "Budget FY Start Year",
                "B6": 2026,
                "D6": "Setting",
                "A17": "RRSP Match",
                "B17": 0.04,
                "D17": "Rate",
                "F17": "Policy",
                "A19": "WL Wage Rate",
                "B19": 26.02,
                "D19": "Rate",
                "F19": "UBC",
            }
        }
        with make_workbook(sheets) as (wb_form, wb_val, unused_path):
            findings = budget_checks.check_parameters(wb_form, wb_val)

        unused_findings = [item for item in findings if "No budget formula" in item["why"]]
        self.assertEqual(len(unused_findings), 1)
        self.assertIn("RRSP Match (B17)", unused_findings[0]["why"])
        self.assertIn("WL Wage Rate (B19)", unused_findings[0]["why"])
        self.assertNotIn("Budget FY Start Year", unused_findings[0]["why"])

    # (2.6): Parameters check with metadata headers, dates, Setting skip, and CPI.
    def test_parameters_with_headers_and_cpi(self) -> None:
        assumptions = {
            "D3": "Kind",
            "E3": "Basis",
            "F3": "Source document",
            "G3": "Clause",
            "H3": "Valid from",
            "I3": "Valid until",
            "J3": "Previous value",
            "K3": "Previous valid from",
            "L3": "Previous valid until",
            "M3": "Inflated previous",
            "N3": "Owner",
            "O3": "Status",
            "A6": "Budget FY Start Year",
            "B6": 2026,
            "D6": "Setting",
            "A30": "CPI",
            "B30": 0.022,
            "D30": "Setting",
            # Row 41: missing source document -> high.
            "A41": "No Source Rate",
            "B41": 100,
            "D41": "Rate",
            "E41": "Fixed",
            "H41": datetime.date(2026, 6, 1),
            "I41": datetime.date(2027, 5, 31),
            # Row 42: lapses before FY end -> high.
            "A42": "Lapsing Contract",
            "B42": 200,
            "D42": "Contract",
            "E42": "Fixed",
            "F42": "Lease",
            "H42": datetime.date(2026, 6, 1),
            "I42": datetime.date(2027, 3, 31),
            # Row 43: starts mid-year -> review (no gap with previous).
            "A43": "Midyear Rate",
            "B43": 300,
            "D43": "Contract",
            "E43": "Fixed",
            "F43": "Union",
            "H43": datetime.date(2026, 9, 1),
            "I43": datetime.date(2027, 5, 31),
            "K43": datetime.date(2025, 6, 1),
            "L43": datetime.date(2026, 8, 31),
            # Row 44: gap before Valid from -> review.
            "A44": "Gapped Contract",
            "B44": 400,
            "D44": "Contract",
            "E44": "Fixed",
            "F44": "Vendor",
            "H44": datetime.date(2026, 6, 1),
            "I44": datetime.date(2027, 5, 31),
            "L44": datetime.date(2026, 5, 15),
            # Row 45: CPI mismatch (105 vs expected 102.2) -> high.
            "A45": "CPI Bad",
            "B45": 105,
            "D45": "Contract",
            "E45": "CPI",
            "F45": "SLA",
            "H45": datetime.date(2026, 6, 1),
            "I45": datetime.date(2027, 5, 31),
            "J45": 100,
            "K45": datetime.date(2025, 6, 1),
            "L45": datetime.date(2026, 5, 31),
            # Row 46: CPI match (102.2) -> no CPI finding.
            "A46": "CPI Good",
            "B46": 102.2,
            "D46": "Contract",
            "E46": "CPI",
            "F46": "SLA 2",
            "H46": datetime.date(2026, 6, 1),
            "I46": datetime.date(2027, 5, 31),
            "J46": 100,
            "K46": datetime.date(2025, 6, 1),
            "L46": datetime.date(2026, 5, 31),
            # Row 47: Setting row with missing source and early date -> skipped.
            "A47": "Ignored Setting",
            "B47": 999,
            "D47": "Setting",
            "I47": datetime.date(2026, 12, 31),
        }
        # Reference every Assumptions parameter on another sheet to isolate metadata checks.
        usage_formula = (
            "=Assumptions!B6+Assumptions!B30+Assumptions!B41+Assumptions!B42"
            "+Assumptions!B43+Assumptions!B44+Assumptions!B45+Assumptions!B46+Assumptions!B47"
        )
        sheets = {
            "Assumptions": assumptions,
            "Driver": {"A1": usage_formula},
        }
        with make_workbook(sheets) as (wb_form, wb_val, unused_path):
            findings = budget_checks.check_parameters(wb_form, wb_val)

        by_line = {item["line"]: item for item in findings}
        self.assertEqual(len(findings), 5)
        self.assertEqual(by_line["No Source Rate"]["severity"], "high")
        self.assertEqual(by_line["Lapsing Contract"]["severity"], "high")
        self.assertEqual(by_line["Midyear Rate"]["severity"], "review")
        self.assertEqual(by_line["Gapped Contract"]["severity"], "review")
        self.assertEqual(by_line["CPI Bad"]["severity"], "high")
        self.assertIn("102.20", by_line["CPI Bad"]["why"])
        self.assertNotIn("CPI Good", by_line)
        self.assertNotIn("Ignored Setting", by_line)

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
