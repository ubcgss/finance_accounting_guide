#--------------------------------------------------------------------------------------------
# File name:         budget_checks.py
# Creation date:     2026-11-25
# Author:            César Landín
# Files used:
#   - User-supplied budget master workbook (.xlsx)
# Files created:
#   - Optional Markdown report file when -o is passed
# Purpose:
#   - Check GSS annual budget master workbooks for formula, parameter, and consistency issues.
#--------------------------------------------------------------------------------------------

import argparse
import datetime
from pathlib import Path
import re

import openpyxl
from openpyxl.utils import coordinate_to_tuple, get_column_letter


#########################################
##  (1): Constants and configuration.  ##
#########################################
# (1.1): Constants required by the public checker specification.
ALLOWED_CONSTANTS = {0, 1, 2, 3, 4, 12, 24, 100}
REQUIRED_LINES = {
    6150: "Employer CPP/EI",
    6160: "WorkSafeBC",
    6200: "Professional & Contracted Services (audit)",
    6500: "Occupancy (Lease Agreement)",
    6550: "Insurance",
    6580: "Bank & Financial Services Fees",
}
DEPT_TAB_RE = r"^\d\d-[A-Z]+$"
CONSOLIDATED = "Consolidated"
ASSUMPTIONS = "Assumptions"
COA_SHEET = "Chart of Accounts - Accounts"
DRIVER_TABS = [
    "FT Staff",
    "RRSP",
    "CPP EI RRSP",
    "WSA HSA",
    "Retention Bonus",
    "Honoraria",
    "PT Commercial",
    "PT Benefits",
    "WL Supporting",
    "720-10",
    "Dept14 Events",
]
PARAM_HEADERS = [
    "Kind",
    "Basis",
    "Source document",
    "Clause",
    "Valid from",
    "Valid until",
    "Previous value",
    "Previous valid from",
    "Previous valid until",
    "Inflated previous",
    "Owner",
    "Status",
]
CPI_TOLERANCE = 0.005
MONEY_TOLERANCE = 0.5

# (1.2): Report ordering, human-readable titles, and sheet exclusions.
CHECK_ORDER = (
    "parameters",
    "rolled_forward",
    "hard_coded",
    "consistency",
    "required_lines",
)
CHECK_TITLES = {
    "parameters": "Parameters",
    "rolled_forward": "Rolled-forward formulas",
    "hard_coded": "Hard-coded numbers",
    "consistency": "Internal consistency",
    "required_lines": "Required lines",
}
DRIVER_TAB_SET = set(DRIVER_TABS)
MIN_COLUMN_BLOCK_FORMULAS = 3
MIN_COLUMN_FORMULA_SHARE = 0.6
TEXT_DASHES = {"-", "\u2013", "\u2014"}


##############################################
##  (2): Shared workbook and cell helpers.  ##
##############################################
# (2.1): Type and value inspection helpers for openpyxl cells.
def is_number(value) -> bool:
    """Return True for numeric values while excluding booleans."""
    # In Python, bool is a subclass of int, so isinstance(True, int) is True.
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def as_int(value) -> int | None:
    """Return an int if value is an integer (or whole float), else None."""
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def as_date(value) -> datetime.date | None:
    """Normalize openpyxl datetime/date values to a plain date, or None."""
    # datetime is a subclass of date, so check datetime first to strip the time part.
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    return None


def cell_formula(cell) -> str | None:
    """Return formula text only when cell.data_type == 'f' (ignore text strings)."""
    if cell.data_type != "f":
        return None
    val = cell.value
    if isinstance(val, str):
        return val
    # Openpyxl wraps dynamic/CSE array formulas in an object with a .text string.
    if hasattr(val, "text") and isinstance(val.text, str):
        return val.text
    return None


def is_empty_value(value) -> bool:
    """Return True if a cell value is None or whitespace-only text."""
    if value is None:
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    return False


def format_value(value) -> str:
    """Convert a raw cell value or ArrayFormula into clean display text."""
    if hasattr(value, "text") and isinstance(value.text, str):
        return value.text
    date_val = as_date(value)
    if date_val is not None:
        return date_val.isoformat()
    if value is None:
        return ""
    return str(value)


def format_cell(cell) -> str:
    """Format an openpyxl Cell, preserving formula text when data_type == 'f'."""
    formula = cell_formula(cell)
    if formula is not None:
        return formula
    return format_value(cell.value)


# (2.2): Sheet classification and finding construction helpers.
def is_dept_tab(sheet_name: str) -> bool:
    """Return True for department budget tabs like 10-CORP, excluding 720-10."""
    return re.match(DEPT_TAB_RE, sheet_name) is not None


def is_hard_coded_target_sheet(sheet_name: str) -> bool:
    """Scan only department tabs, Consolidated, and known driver tabs."""
    return (
        is_dept_tab(sheet_name)
        or sheet_name == CONSOLIDATED
        or sheet_name in DRIVER_TAB_SET
    )


def make_finding(
    check: str,
    severity: str,
    sheet: str,
    cell: str,
    code: int | None,
    line: str,
    content: str,
    why: str,
    fix: str,
) -> dict:
    """Build a finding dictionary with the exact required keys."""
    return {
        "check": check,
        "severity": severity,
        "sheet": sheet,
        "cell": cell,
        "code": code,
        "line": line,
        "content": content,
        "why": why,
        "fix": fix,
    }


def row_context(ws, sheet_name: str, row: int) -> tuple[int | None, str]:
    """Extract account code and line label for a row based on sheet layout."""
    if is_dept_tab(sheet_name) or sheet_name == CONSOLIDATED:
        if row >= 4:
            code_val = as_int(ws.cell(row=row, column=2).value)
            line_text = str(ws.cell(row=row, column=3).value or "").strip()
            return code_val, line_text
        return None, ""
    label_val = ws.cell(row=row, column=1).value
    if label_val is None:
        return None, ""
    return None, str(label_val).strip()


# (2.3): Formula sanitization and numeric literal extraction.
def strip_strings_and_sheet_prefixes(formula: str) -> str:
    """Remove string literals, sheet prefixes, and _xlfn/_xlws markers."""
    cleaned = re.sub(r'"(?:[^"]|"")*"', " ", formula)
    cleaned = re.sub(r"'(?:[^']|'')*'!", " ", cleaned)
    cleaned = re.sub(r"[A-Za-z_][\w.]*!", " ", cleaned)
    cleaned = re.sub(r"\b(?:_xlfn|_xlws)\.", "", cleaned, flags=re.IGNORECASE)
    return cleaned


IGNORED_INT_ARG_FUNCS = {
    "MID": {2, 3},
    "LEFT": {2, 3},
    "RIGHT": {2, 3},
    "ROUND": {2},
    "ROUNDUP": {2},
    "ROUNDDOWN": {2},
}


def strip_ignored_function_args(cleaned: str) -> str:
    """Blank out integer-literal argument positions for MID/LEFT/RIGHT/ROUND*."""
    chars = list(cleaned)
    func_re = re.compile(
        r"\b(MID|LEFT|RIGHT|ROUND|ROUNDUP|ROUNDDOWN)\(",
        flags=re.IGNORECASE,
    )
    for match in func_re.finditer(cleaned):
        ignored_positions = IGNORED_INT_ARG_FUNCS[match.group(1).upper()]
        depth = 1
        arg_idx = 1
        arg_start = match.end()
        pos = match.end()
        while pos < len(cleaned) and depth > 0:
            ch = cleaned[pos]
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    if arg_idx in ignored_positions and re.fullmatch(
                        r"\d+", cleaned[arg_start:pos].strip()
                    ):
                        chars[arg_start:pos] = [" "] * (pos - arg_start)
            elif ch == "," and depth == 1:
                if arg_idx in ignored_positions and re.fullmatch(
                    r"\d+", cleaned[arg_start:pos].strip()
                ):
                    chars[arg_start:pos] = [" "] * (pos - arg_start)
                arg_idx += 1
                arg_start = pos + 1
            pos += 1
    return "".join(chars)


def extract_numeric_literals(formula: str) -> list[tuple[str, float]]:
    """Return unique (raw_text, float_value) numeric literals in a formula."""
    cleaned = strip_strings_and_sheet_prefixes(formula)
    cleaned = re.sub(r"\bDATE(?:VALUE)?\([^()]*\)", " ", cleaned, flags=re.IGNORECASE)
    cleaned = strip_ignored_function_args(cleaned)
    # Remove whole-column, whole-row, and A1 cell references before scanning digits.
    cleaned = re.sub(r"\$?[A-Za-z]{1,3}:\$?[A-Za-z]{1,3}", " ", cleaned)
    cleaned = re.sub(r"\$?\d+:\$?\d+", " ", cleaned)
    cleaned = re.sub(
        r"(?<![A-Za-z0-9_])\$?[A-Za-z]{1,3}\$?\d+(?![A-Za-z0-9_])",
        " ",
        cleaned,
    )
    cleaned = re.sub(r"[A-Za-z][A-Za-z0-9.]*\(", " ", cleaned)

    # Match numbers (including leading-dot decimals like .5) not attached to identifiers.
    pattern = r"(?<![A-Za-z_.])(?:\d+(?:\.\d+)?|\.\d+)(?![A-Za-z_])"
    seen = set()
    literals = []
    for raw in re.findall(pattern, cleaned):
        if raw not in seen:
            seen.add(raw)
            literals.append((raw, float(raw)))
    return literals


##########################################
##  (3): Budget integrity check rules.  ##
##########################################
# (3.1): Rule 1 - Parameters (Assumptions metadata, CPI, named ranges, unused).
def find_assumptions_header(ws) -> tuple[int | None, dict[str, int]]:
    """Find the parameter header row in rows 1..10 and map headers to columns."""
    max_scan = min(10, ws.max_row)
    for row in range(1, max_scan + 1):
        row_map = {}
        has_valid_until = False
        for col in range(1, ws.max_column + 1):
            val = ws.cell(row=row, column=col).value
            if val is not None:
                text = str(val).strip()
                if text == "Valid until":
                    has_valid_until = True
                if text in PARAM_HEADERS and text not in row_map:
                    row_map[text] = col
        if has_valid_until:
            return row, row_map
    return None, {}


def find_fy_bounds(ws_values) -> tuple[datetime.date | None, datetime.date | None]:
    """Determine fiscal year start (Jun 1) and end (May 31) from Assumptions."""
    fy_year = None
    for row in range(1, ws_values.max_row + 1):
        label = ws_values.cell(row=row, column=1).value
        if label is not None and str(label).strip() == "Budget FY Start Year":
            fy_year = as_int(ws_values.cell(row=row, column=2).value)
            break
    if fy_year is None:
        candidate = as_int(ws_values.cell(row=6, column=2).value)
        if candidate is not None and 1900 <= candidate <= 2100:
            fy_year = candidate
    if fy_year is None:
        return None, None
    return datetime.date(fy_year, 6, 1), datetime.date(fy_year + 1, 5, 31)


def find_cpi_rate(ws_values) -> float | None:
    """Return the numeric CPI rate from the Assumptions row labeled 'CPI'."""
    for row in range(1, ws_values.max_row + 1):
        label = ws_values.cell(row=row, column=1).value
        if label is not None and str(label).strip() == "CPI":
            val = ws_values.cell(row=row, column=2).value
            if is_number(val):
                return float(val)
            return None
    return None


def collect_other_sheet_formulas(wb_formulas) -> list[str]:
    """Gather all formula strings from every sheet other than Assumptions."""
    formulas = []
    for name in wb_formulas.sheetnames:
        if name == ASSUMPTIONS:
            continue
        ws = wb_formulas[name]
        for row_cells in ws.iter_rows():
            for cell in row_cells:
                formula = cell_formula(cell)
                if formula is not None:
                    formulas.append(formula)
    return formulas


def check_parameters(wb_formulas, wb_values) -> list[dict]:
    """Run parameter source, validity, CPI, named-range, and usage checks."""
    if ASSUMPTIONS not in wb_formulas.sheetnames:
        return [
            make_finding(
                check="parameters",
                severity="high",
                sheet=ASSUMPTIONS,
                cell="",
                code=None,
                line="",
                content="",
                why="The Assumptions tab is missing from the workbook.",
                fix="Restore the Assumptions tab so budget parameters can be checked.",
            )
        ]

    ws_form = wb_formulas[ASSUMPTIONS]
    ws_val = wb_values[ASSUMPTIONS]
    findings = []

    header_row, col_map = find_assumptions_header(ws_form)
    if header_row is None:
        findings.append(
            make_finding(
                check="parameters",
                severity="review",
                sheet=ASSUMPTIONS,
                cell="",
                code=None,
                line="",
                content="",
                why=(
                    "The Assumptions tab has no source/validity columns, "
                    "so no parameter can be traced to a contract or decision."
                ),
                fix=(
                    "Paste in the Parameters columns (Kind, Basis, Source document, "
                    "... Status) from the draft workbook."
                ),
            )
        )
    else:
        fy_start, fy_end = find_fy_bounds(ws_val)
        cpi_rate = find_cpi_rate(ws_val)
        missing_cpi_reported = False

        for row in range(header_row + 1, ws_form.max_row + 1):
            label_raw = ws_form.cell(row=row, column=1).value
            b_cell = ws_form.cell(row=row, column=2)
            b_form = b_cell.value
            b_val = ws_val.cell(row=row, column=2).value
            if is_empty_value(label_raw) or (is_empty_value(b_form) and is_empty_value(b_val)):
                continue

            label = str(label_raw).strip()
            kind_col = col_map.get("Kind")
            kind_raw = ws_val.cell(row=row, column=kind_col).value if kind_col else None
            kind = str(kind_raw).strip() if kind_raw is not None else ""
            if kind == "Setting":
                continue

            # Source document check.
            src_col = col_map.get("Source document")
            src_val = ws_val.cell(row=row, column=src_col).value if src_col else None
            if is_empty_value(src_val):
                src_cell = f"{get_column_letter(src_col)}{row}" if src_col else f"B{row}"
                findings.append(
                    make_finding(
                        check="parameters",
                        severity="high",
                        sheet=ASSUMPTIONS,
                        cell=src_cell,
                        code=None,
                        line=label,
                        content=format_cell(b_cell),
                        why="No source document is listed for this parameter.",
                        fix="Enter the contract, bylaw, statutory source, or decision in Source document.",
                    )
                )

            # Validity date checks against the fiscal year.
            vf_col = col_map.get("Valid from")
            vu_col = col_map.get("Valid until")
            pvf_col = col_map.get("Previous valid from")
            pvu_col = col_map.get("Previous valid until")
            valid_from = as_date(ws_val.cell(row=row, column=vf_col).value) if vf_col else None
            valid_until = as_date(ws_val.cell(row=row, column=vu_col).value) if vu_col else None
            prev_valid_from = as_date(ws_val.cell(row=row, column=pvf_col).value) if pvf_col else None
            prev_valid_until = as_date(ws_val.cell(row=row, column=pvu_col).value) if pvu_col else None

            if valid_until is not None and fy_end is not None and valid_until < fy_end:
                findings.append(
                    make_finding(
                        check="parameters",
                        severity="high",
                        sheet=ASSUMPTIONS,
                        cell=f"{get_column_letter(vu_col)}{row}",
                        code=None,
                        line=label,
                        content=valid_until.isoformat(),
                        why=(
                            f"Lapses before the fiscal year ends "
                            f"({valid_until.isoformat()} vs {fy_end.isoformat()})."
                        ),
                        fix="Confirm the renewal rate or update Valid until to cover the full fiscal year.",
                    )
                )

            if valid_from is not None and fy_start is not None and valid_from > fy_start:
                findings.append(
                    make_finding(
                        check="parameters",
                        severity="review",
                        sheet=ASSUMPTIONS,
                        cell=f"{get_column_letter(vf_col)}{row}",
                        code=None,
                        line=label,
                        content=valid_from.isoformat(),
                        why=(
                            f"Starts mid-year ({valid_from.isoformat()}); "
                            "the budget line may need two rates."
                        ),
                        fix="Verify that months before the start date use the prior rate and months after use this rate.",
                    )
                )

            if (
                prev_valid_until is not None
                and valid_from is not None
                and prev_valid_until != valid_from - datetime.timedelta(days=1)
            ):
                findings.append(
                    make_finding(
                        check="parameters",
                        severity="review",
                        sheet=ASSUMPTIONS,
                        cell=f"{get_column_letter(pvu_col)}{row}",
                        code=None,
                        line=label,
                        content=prev_valid_until.isoformat(),
                        why=(
                            f"Gap or overlap with the previous period "
                            f"({prev_valid_until.isoformat()} before {valid_from.isoformat()})."
                        ),
                        fix="Check the contract dates so the new period begins the day after the previous period ends.",
                    )
                )

            # CPI escalator verification when Basis == "CPI".
            basis_col = col_map.get("Basis")
            basis_raw = ws_val.cell(row=row, column=basis_col).value if basis_col else None
            basis = str(basis_raw).strip() if basis_raw is not None else ""
            if basis == "CPI":
                if cpi_rate is None:
                    if not missing_cpi_reported:
                        missing_cpi_reported = True
                        findings.append(
                            make_finding(
                                check="parameters",
                                severity="review",
                                sheet=ASSUMPTIONS,
                                cell="",
                                code=None,
                                line="CPI",
                                content="",
                                why="CPI rate was not found on the Assumptions tab, so CPI-indexed rows were not verified.",
                                fix="Ensure a row labeled 'CPI' with a numeric value in column B exists on Assumptions.",
                            )
                        )
                    continue

                prev_col = col_map.get("Previous value")
                prev_val = ws_val.cell(row=row, column=prev_col).value if prev_col else None
                if is_empty_value(prev_val):
                    prev_cell = f"{get_column_letter(prev_col)}{row}" if prev_col else f"B{row}"
                    findings.append(
                        make_finding(
                            check="parameters",
                            severity="review",
                            sheet=ASSUMPTIONS,
                            cell=prev_cell,
                            code=None,
                            line=label,
                            content="",
                            why="Cannot verify inflation (no previous value).",
                            fix="Enter the prior-period value in Previous value so the CPI adjustment can be checked.",
                        )
                    )
                elif (
                    is_number(prev_val)
                    and is_number(b_val)
                    and valid_from is not None
                    and prev_valid_from is not None
                ):
                    years = round((valid_from - prev_valid_from).days / 365.25)
                    expected = float(prev_val) * ((1.0 + cpi_rate) ** years)
                    if expected == 0:
                        mismatch = abs(float(b_val)) > CPI_TOLERANCE
                    else:
                        mismatch = abs(float(b_val) / expected - 1.0) > CPI_TOLERANCE
                    if mismatch:
                        findings.append(
                            make_finding(
                                check="parameters",
                                severity="high",
                                sheet=ASSUMPTIONS,
                                cell=f"B{row}",
                                code=None,
                                line=label,
                                content=format_value(b_val),
                                why=(
                                    f"Value does not equal the previous value inflated by CPI "
                                    f"(expected {expected:,.2f})."
                                ),
                                fix="Update the value to the CPI-adjusted amount or change Basis if another escalator applies.",
                            )
                        )

    # Named range claims and unused parameter checks always run (grouped once each).
    defined_upper = {name.upper() for name in wb_formulas.defined_names.keys()}
    claimed_names = {}
    missing_named_ranges = []
    for row in range(1, ws_form.max_row + 1):
        c_val = ws_form.cell(row=row, column=3).value
        if c_val is None:
            continue
        c_text = str(c_val)
        match = re.search(r"Named range:\s*([A-Z_][A-Z0-9_]*)", c_text)
        if match:
            claimed = match.group(1)
            claimed_names[row] = claimed
            if claimed.upper() not in defined_upper:
                missing_named_ranges.append((row, claimed))

    if missing_named_ranges:
        summary_names = ", ".join(f"{name} (C{r})" for r, name in missing_named_ranges)
        findings.append(
            make_finding(
                check="parameters",
                severity="review",
                sheet=ASSUMPTIONS,
                cell="",
                code=None,
                line="",
                content="",
                why=(
                    "Column C claims named ranges that do not exist, so formulas "
                    f"cannot use them: {summary_names}."
                ),
                fix="Create these names (Formulas > Name Manager) pointing at column B, or delete the notes in column C.",
            )
        )

    other_formulas = collect_other_sheet_formulas(wb_formulas)
    kind_col = col_map.get("Kind")
    unused_params = []
    for row in range(4, ws_form.max_row + 1):
        a_val = ws_form.cell(row=row, column=1).value
        b_cell = ws_form.cell(row=row, column=2)
        if is_empty_value(a_val):
            continue
        if not (is_number(b_cell.value) or cell_formula(b_cell) is not None):
            continue
        if kind_col is not None:
            kind_raw = ws_val.cell(row=row, column=kind_col).value
            if kind_raw is not None and str(kind_raw).strip() == "Setting":
                continue

        cell_ref_re = re.compile(
            rf"'?{re.escape(ASSUMPTIONS)}'?!\$?B\$?{row}(?!\d)",
            flags=re.IGNORECASE,
        )
        claimed = claimed_names.get(row)
        name_re = (
            re.compile(rf"\b{re.escape(claimed)}\b", flags=re.IGNORECASE)
            if claimed
            else None
        )

        used = any(
            cell_ref_re.search(formula) is not None
            or (name_re is not None and name_re.search(formula) is not None)
            for formula in other_formulas
        )
        if not used:
            unused_params.append((row, str(a_val).strip()))

    if unused_params:
        summary_unused = ", ".join(f"{label} (B{r})" for r, label in unused_params)
        findings.append(
            make_finding(
                check="parameters",
                severity="review",
                sheet=ASSUMPTIONS,
                cell="",
                code=None,
                line="",
                content="",
                why=f"No budget formula uses these parameters: {summary_unused}.",
                fix="Link the relevant budget lines to these parameters or remove them if unused.",
            )
        )

    return findings


# (3.2): Rule 2 - Rolled-forward formulas in department Annual Target (col D).
def find_rolled_forward_cols(formula: str, row: int) -> list[str]:
    """Return R/S column letters referenced on the same row in a formula."""
    cleaned = strip_strings_and_sheet_prefixes(formula)
    return re.findall(
        rf"(?<![A-Z0-9_$])\$?([RS])\$?{row}(?!\d)",
        cleaned,
        flags=re.IGNORECASE,
    )


def check_rolled_forward(wb_formulas, wb_values) -> list[dict]:
    """Flag dept-tab column D formulas that reference same-row col R or S."""
    findings = []
    for sheet_name in wb_formulas.sheetnames:
        if not is_dept_tab(sheet_name):
            continue
        ws = wb_formulas[sheet_name]
        r3_header = str(ws.cell(row=3, column=18).value or "2025-2026 Budget").strip()
        s3_header = str(ws.cell(row=3, column=19).value or "2025-2026 Actuals (Projected)").strip()

        for row in range(4, ws.max_row + 1):
            code_val = as_int(ws.cell(row=row, column=2).value)
            if code_val is None:
                continue
            formula = cell_formula(ws.cell(row=row, column=4))
            if formula is None:
                continue

            rs_matches = find_rolled_forward_cols(formula, row)
            if not rs_matches:
                continue

            literals = extract_numeric_literals(formula)
            bad_literals = [
                (raw, val) for raw, val in literals if val not in ALLOWED_CONSTANTS
            ]
            severity = "high" if bad_literals else "review"

            matched_cols = {col.upper() for col in rs_matches}
            if matched_cols == {"R"}:
                prior_label = f"'{r3_header}'"
            elif matched_cols == {"S"}:
                prior_label = f"'{s3_header}'"
            else:
                prior_label = f"'{r3_header}' and '{s3_header}'"

            if bad_literals:
                raw_list = ", ".join(raw for raw, unused in bad_literals)
                noun = "number" if len(bad_literals) == 1 else "numbers"
                why = (
                    f"Starts from {prior_label} and multiplies by the typed "
                    f"{noun} {raw_list} instead of being calculated for this year."
                )
            else:
                why = (
                    f"Starts from {prior_label} and rolls it forward instead of "
                    "being calculated for this year."
                )

            line_name = str(ws.cell(row=row, column=3).value or "").strip()
            findings.append(
                make_finding(
                    check="rolled_forward",
                    severity=severity,
                    sheet=sheet_name,
                    cell=f"D{row}",
                    code=code_val,
                    line=line_name,
                    content=formula,
                    why=why,
                    fix=(
                        "If a driver tab calculates this line (e.g. FT Staff, Honoraria), "
                        "link to it; if the line has no driver, confirm the roll-forward is "
                        "intended and note it in column T."
                    ),
                )
            )
    return findings


# (3.3): Rule 3 - Hard-coded literals, typed cells among formulas, unlinked parameters.
def collect_assumption_parameters(wb_values) -> list[tuple[int, str, float]]:
    """Collect numeric Assumptions!B values eligible for unlinked-value matching."""
    if ASSUMPTIONS not in wb_values.sheetnames:
        return []
    ws_val = wb_values[ASSUMPTIONS]
    params = []
    for row in range(4, ws_val.max_row + 1):
        val = ws_val.cell(row=row, column=2).value
        if not is_number(val):
            continue
        if abs(val) < 50:
            continue
        int_val = as_int(val)
        if int_val is not None and 1900 <= int_val <= 2100:
            continue
        label = str(ws_val.cell(row=row, column=1).value or "").strip()
        params.append((row, label, float(val)))
    return params


def collect_assumption_source_cells(wb_formulas) -> set[tuple[str, str]]:
    """Parse (sheet_casefold, cell_coord) targets pointed to by Assumptions!B formulas."""
    if ASSUMPTIONS not in wb_formulas.sheetnames:
        return set()
    ws_form = wb_formulas[ASSUMPTIONS]
    quoted_re = re.compile(r"'((?:[^']|'')*)'!\$?([A-Za-z]{1,3})\$?(\d+)(?!\d)")
    unquoted_re = re.compile(
        r"(?<![A-Za-z0-9_'])([A-Za-z_][\w.]*)!\$?([A-Za-z]{1,3})\$?(\d+)(?!\d)"
    )
    sources = set()
    for row in range(1, ws_form.max_row + 1):
        formula = cell_formula(ws_form.cell(row=row, column=2))
        if formula is None:
            continue
        cleaned = re.sub(r'"(?:[^"]|"")*"', " ", formula)
        for match in quoted_re.finditer(cleaned):
            target_sheet = match.group(1).replace("''", "'").casefold()
            coord = f"{match.group(2).upper()}{match.group(3)}"
            sources.add((target_sheet, coord))
        without_quoted = quoted_re.sub(" ", cleaned)
        for match in unquoted_re.finditer(without_quoted):
            target_sheet = match.group(1).casefold()
            coord = f"{match.group(2).upper()}{match.group(3)}"
            sources.add((target_sheet, coord))
    return sources


def find_matching_parameter(
    number_val: float,
    params: list[tuple[int, str, float]],
) -> tuple[int, str, float] | None:
    """Return the first Assumptions parameter matching number_val within 0.01."""
    for p_row, p_label, p_val in params:
        if abs(number_val - p_val) <= 0.01:
            return (p_row, p_label, p_val)
    return None


def find_typed_among_row_formulas(ws, sheet_name: str) -> list[dict]:
    """Flag typed non-zero numbers in E..P sitting between two formulas on budget line rows."""
    findings = []
    scan_cols = list(range(5, 17))
    for row in range(4, ws.max_row + 1):
        code_val, line_name = row_context(ws, sheet_name, row)
        # Skip non-line rows (e.g. headers, totals, or event tables without an int code).
        if code_val is None:
            continue
        row_cells = [ws.cell(row=row, column=col) for col in scan_cols]
        for idx, col in enumerate(scan_cols):
            cell = row_cells[idx]
            val = cell.value
            if cell_formula(cell) is not None or not is_number(val) or val == 0:
                continue

            left_is_formula = False
            for left_idx in range(idx - 1, -1, -1):
                left_cell = row_cells[left_idx]
                if cell_formula(left_cell) is not None:
                    left_is_formula = True
                    break
                if not is_empty_value(left_cell.value):
                    break
            if not left_is_formula:
                continue

            right_is_formula = False
            for right_idx in range(idx + 1, len(scan_cols)):
                right_cell = row_cells[right_idx]
                if cell_formula(right_cell) is not None:
                    right_is_formula = True
                    break
                if not is_empty_value(right_cell.value):
                    break
            if not right_is_formula:
                continue

            findings.append(
                make_finding(
                    check="hard_coded",
                    severity="high",
                    sheet=sheet_name,
                    cell=f"{get_column_letter(col)}{row}",
                    code=code_val,
                    line=line_name,
                    content=format_value(val),
                    why=(
                        "A typed number sits between formulas in this row, "
                        "so it will not follow changes to the rate it was copied from."
                    ),
                    fix="Replace it with the same formula as its neighbours.",
                )
            )
    return findings


def find_typed_among_column_formulas(ws_form, ws_val, sheet_name: str) -> list[dict]:
    """Flag typed non-zero numbers inside mostly-formula contiguous column blocks."""
    findings = []
    for col in range(1, ws_form.max_column + 1):
        col_letter = get_column_letter(col)
        block_rows = []

        def flush_block() -> None:
            if not block_rows:
                return
            formula_count = 0
            typed_count = 0
            typed_nonzero = []
            for b_row in block_rows:
                f_cell = ws_form.cell(row=b_row, column=col)
                v_val = ws_val.cell(row=b_row, column=col).value
                if cell_formula(f_cell) is not None:
                    # Skip formulas whose cached output is non-empty text (e.g. headers).
                    if not (isinstance(v_val, str) and v_val.strip() != ""):
                        formula_count += 1
                elif is_number(f_cell.value):
                    typed_count += 1
                    if f_cell.value != 0:
                        typed_nonzero.append((b_row, f_cell.value))

            numeric_total = formula_count + typed_count
            if (
                formula_count >= MIN_COLUMN_BLOCK_FORMULAS
                and numeric_total > 0
                and (formula_count / numeric_total) >= MIN_COLUMN_FORMULA_SHARE
            ):
                for b_row, num_val in typed_nonzero:
                    code_val, line_name = row_context(ws_form, sheet_name, b_row)
                    findings.append(
                        make_finding(
                            check="hard_coded",
                            severity="high",
                            sheet=sheet_name,
                            cell=f"{col_letter}{b_row}",
                            code=code_val,
                            line=line_name,
                            content=format_value(num_val),
                            why=(
                                "A typed number sits in a mostly-formula column, "
                                "so it will not follow changes to the formula it was copied from."
                            ),
                            fix="Replace it with the same formula as the other rows in this column.",
                        )
                    )
            block_rows.clear()

        for row in range(1, ws_form.max_row + 1):
            f_cell = ws_form.cell(row=row, column=col)
            if cell_formula(f_cell) is None and is_empty_value(f_cell.value):
                flush_block()
            else:
                block_rows.append(row)
        flush_block()
    return findings


def check_hard_coded(wb_formulas, wb_values) -> list[dict]:
    """Run hard-coded formula literal, typed-among-formulas, and parameter-match checks."""
    findings = []
    params = collect_assumption_parameters(wb_values)
    source_cells = collect_assumption_source_cells(wb_formulas)

    for sheet_name in wb_formulas.sheetnames:
        if not is_hard_coded_target_sheet(sheet_name):
            continue
        ws = wb_formulas[sheet_name]
        ws_val = wb_values[sheet_name]
        dept_sheet = is_dept_tab(sheet_name)
        dept_or_cons = dept_sheet or sheet_name == CONSOLIDATED
        start_row = 4 if dept_or_cons else 1

        # (3.3a & 3.3c): Formula literals and unlinked parameter matches.
        for row in range(start_row, ws.max_row + 1):
            code_val, line_name = row_context(ws, sheet_name, row)
            for col in range(1, ws.max_column + 1):
                if dept_or_cons and col in (18, 19, 20):
                    continue
                f_cell = ws.cell(row=row, column=col)
                coord = f"{get_column_letter(col)}{row}"
                formula = cell_formula(f_cell)
                is_source_cell = (sheet_name.casefold(), coord) in source_cells

                if formula is not None:
                    # Rolled-forward formulas already list their literals in rolled_forward.
                    if (
                        dept_sheet
                        and col == 4
                        and row >= 4
                        and code_val is not None
                        and find_rolled_forward_cols(formula, row)
                    ):
                        continue

                    literals = extract_numeric_literals(formula)
                    bad_literals = [
                        (raw, num) for raw, num in literals if num not in ALLOWED_CONSTANTS
                    ]
                    if not bad_literals:
                        continue

                    high_flag = (dept_sheet and 4 <= col <= 16) or any(
                        (not num.is_integer()) or abs(num) >= 1000
                        for unused, num in bad_literals
                    )
                    severity = "high" if high_flag else "review"
                    raw_list = ", ".join(raw for raw, unused in bad_literals)
                    why = (
                        f"Contains the typed number(s) {raw_list} inside the formula; "
                        "if the underlying rate changes, this cell will not update."
                    )
                    fix = (
                        "Move the hard-coded number(s) to the Assumptions tab or a driver "
                        "tab and reference that cell instead."
                    )

                    # Append parameter-match note onto the existing (a) finding if matched.
                    if not is_source_cell:
                        matched_param = None
                        for unused, num in bad_literals:
                            matched_param = find_matching_parameter(num, params)
                            if matched_param is not None:
                                break
                        if matched_param is not None:
                            p_row, p_label, unused = matched_param
                            why += (
                                f" Equals the parameter '{p_label}' (Assumptions!B{p_row}) "
                                "but is typed instead of linked."
                            )
                            fix += f" Link to Assumptions!B{p_row}."

                    findings.append(
                        make_finding(
                            check="hard_coded",
                            severity=severity,
                            sheet=sheet_name,
                            cell=coord,
                            code=code_val,
                            line=line_name,
                            content=formula,
                            why=why,
                            fix=fix,
                        )
                    )
                elif is_number(f_cell.value):
                    # Skip Assumptions source cells and column B account codes on dept/Consolidated.
                    if is_source_cell or (dept_or_cons and col == 2):
                        continue
                    matched_param = find_matching_parameter(float(f_cell.value), params)
                    if matched_param is not None:
                        p_row, p_label, unused = matched_param
                        findings.append(
                            make_finding(
                                check="hard_coded",
                                severity="review",
                                sheet=sheet_name,
                                cell=coord,
                                code=code_val,
                                line=line_name,
                                content=format_value(f_cell.value),
                                why=(
                                    f"Equals the parameter '{p_label}' (Assumptions!B{p_row}) "
                                    "but is typed instead of linked."
                                ),
                                fix=f"Link to Assumptions!B{p_row}.",
                            )
                        )

        # (3.3b): Typed non-zero numbers among formulas (row rule on dept/Consolidated, column rule on drivers).
        if dept_or_cons:
            findings.extend(find_typed_among_row_formulas(ws, sheet_name))
        else:
            findings.extend(find_typed_among_column_formulas(ws, ws_val, sheet_name))

    return findings


# (3.4): Rule 4 - Internal consistency (sums, COA codes, text dashes, Consolidated tie-out).
def collect_coa_codes(wb_formulas, wb_values) -> set[int] | None:
    """Collect every integer 1000..9999 on the COA sheet, or None if sheet is missing."""
    if COA_SHEET not in wb_formulas.sheetnames:
        return None
    codes = set()
    for wb in (wb_values, wb_formulas):
        ws = wb[COA_SHEET]
        for row_vals in ws.iter_rows(values_only=True):
            for val in row_vals:
                int_val = as_int(val)
                if int_val is not None and 1000 <= int_val <= 9999:
                    codes.add(int_val)
    return codes


def has_missing_cached_values(wb_formulas, wb_values) -> bool:
    """Return True if Consolidated col D has formulas whose cached values are all None."""
    if CONSOLIDATED not in wb_formulas.sheetnames:
        return False
    ws_form = wb_formulas[CONSOLIDATED]
    ws_val = wb_values[CONSOLIDATED]
    line_rows = [
        row
        for row in range(4, ws_form.max_row + 1)
        if as_int(ws_form.cell(row=row, column=2).value) is not None
    ]
    if not line_rows:
        return False
    has_formula = any(
        cell_formula(ws_form.cell(row=row, column=4)) is not None
        for row in line_rows
    )
    all_none = all(ws_val.cell(row=row, column=4).value is None for row in line_rows)
    return has_formula and all_none


def check_consistency(wb_formulas, wb_values) -> list[dict]:
    """Run internal consistency checks across department tabs and Consolidated."""
    findings = []
    cached_missing = has_missing_cached_values(wb_formulas, wb_values)
    if cached_missing:
        findings.append(
            make_finding(
                check="consistency",
                severity="review",
                sheet=CONSOLIDATED,
                cell="",
                code=None,
                line="",
                content="",
                why=(
                    "Cached values are missing; open the file in Excel, "
                    "let it calculate, save, and run again."
                ),
                fix="Open the workbook in Excel, allow formulas to calculate, save, and re-run.",
            )
        )

    coa_codes = collect_coa_codes(wb_formulas, wb_values)
    if coa_codes is None:
        findings.append(
            make_finding(
                check="consistency",
                severity="review",
                sheet=COA_SHEET,
                cell="",
                code=None,
                line="",
                content="",
                why="The Chart of Accounts tab is missing, so account codes could not be verified.",
                fix="Restore the 'Chart of Accounts - Accounts' tab from the template.",
            )
        )

    target_sheets = [
        name
        for name in wb_formulas.sheetnames
        if is_dept_tab(name) or name == CONSOLIDATED
    ]
    cons_by_code = {}
    dept_by_code = {}
    missing_coa_by_code = {}

    for sheet_name in target_sheets:
        ws_form = wb_formulas[sheet_name]
        ws_val = wb_values[sheet_name]

        for row in range(4, ws_form.max_row + 1):
            code_val = as_int(ws_form.cell(row=row, column=2).value)
            line_name = str(ws_form.cell(row=row, column=3).value or "").strip()

            # Text-dash check in D..P (cols 4..16) on all rows >= 4.
            for col in range(4, 17):
                f_cell = ws_form.cell(row=row, column=col)
                v_val = ws_val.cell(row=row, column=col).value
                dash_text = None
                if (
                    cell_formula(f_cell) is None
                    and isinstance(f_cell.value, str)
                    and f_cell.value.strip() in TEXT_DASHES
                ):
                    dash_text = f_cell.value.strip()
                elif not cached_missing and isinstance(v_val, str) and v_val.strip() in TEXT_DASHES:
                    dash_text = v_val.strip()
                if dash_text is not None:
                    findings.append(
                        make_finding(
                            check="consistency",
                            severity="high",
                            sheet=sheet_name,
                            cell=f"{get_column_letter(col)}{row}",
                            code=code_val,
                            line=line_name,
                            content=dash_text,
                            why=(
                                "A dash typed as text is not a number; "
                                "totals treat it as zero or error."
                            ),
                            fix="Replace the text dash with 0 or a formula.",
                        )
                    )

            if code_val is None:
                continue

            # Chart of Accounts code check (grouped once per missing code).
            if coa_codes is not None and code_val not in coa_codes:
                missing_coa_by_code.setdefault(code_val, []).append(
                    (sheet_name, f"B{row}", line_name)
                )

            if cached_missing:
                continue

            d_val = ws_val.cell(row=row, column=4).value
            q_val = ws_val.cell(row=row, column=17).value
            ep_vals = [ws_val.cell(row=row, column=col).value for col in range(5, 17)]

            if is_number(q_val):
                ep_sum = sum(float(v) for v in ep_vals if is_number(v))
                if abs(float(q_val) - ep_sum) > MONEY_TOLERANCE:
                    findings.append(
                        make_finding(
                            check="consistency",
                            severity="high",
                            sheet=sheet_name,
                            cell=f"Q{row}",
                            code=code_val,
                            line=line_name,
                            content=f"{float(q_val):,.2f}",
                            why=(
                                f"Annual Budget (Q{row} = {float(q_val):,.2f}) does not match "
                                f"the sum of months Jun-May ({ep_sum:,.2f})."
                            ),
                            fix=f"Set Q{row} to =SUM(E{row}:P{row}) and verify the monthly values.",
                        )
                    )

            if is_number(d_val) and is_number(q_val):
                if abs(float(d_val) - float(q_val)) > MONEY_TOLERANCE:
                    findings.append(
                        make_finding(
                            check="consistency",
                            severity="high",
                            sheet=sheet_name,
                            cell=f"D{row}",
                            code=code_val,
                            line=line_name,
                            content=f"{float(d_val):,.2f}",
                            why=(
                                f"Annual Target (D{row} = {float(d_val):,.2f}) does not match "
                                f"Annual Budget (Q{row} = {float(q_val):,.2f})."
                            ),
                            fix="Reconcile Annual Target with the sum of the 12 monthly budgets.",
                        )
                    )

            if sheet_name == CONSOLIDATED:
                cons_by_code[code_val] = (row, line_name, d_val)
            else:
                dept_by_code.setdefault(code_val, []).append((sheet_name, row, line_name, d_val))

    for code_val, occurrences in missing_coa_by_code.items():
        first_sheet, first_cell, first_line = occurrences[0]
        tabs = list(dict.fromkeys(s for s, unused_c, unused_l in occurrences))
        findings.append(
            make_finding(
                check="consistency",
                severity="high",
                sheet=first_sheet,
                cell=first_cell,
                code=code_val,
                line=first_line,
                content=str(code_val),
                why=f"Code {code_val} is on {', '.join(tabs)} but not in the Chart of Accounts tab.",
                fix="Use a valid Chart of Accounts code or update the COA tab.",
            )
        )

    if not cached_missing and CONSOLIDATED in wb_values.sheetnames:
        for code_val, (c_row, c_line, c_d) in cons_by_code.items():
            dept_entries = dept_by_code.get(code_val, [])
            dept_sum = sum(float(d) for unused_s, unused_r, unused_l, d in dept_entries if is_number(d))
            c_num = float(c_d) if is_number(c_d) else 0.0
            if abs(c_num - dept_sum) > MONEY_TOLERANCE:
                findings.append(
                    make_finding(
                        check="consistency",
                        severity="high",
                        sheet=CONSOLIDATED,
                        cell=f"D{c_row}",
                        code=code_val,
                        line=c_line,
                        content=format_value(c_d),
                        why=(
                            f"Consolidated Annual Target ({c_num:,.2f}) does not match the sum "
                            f"of department tabs ({dept_sum:,.2f}) for code {code_val}."
                        ),
                        fix=f"Update Consolidated D{c_row} to sum column D across all department tabs.",
                    )
                )

        for code_val, entries in dept_by_code.items():
            if code_val not in cons_by_code:
                for sheet_name, d_row, d_line, d_val in entries:
                    findings.append(
                        make_finding(
                            check="consistency",
                            severity="high",
                            sheet=sheet_name,
                            cell=f"D{d_row}",
                            code=code_val,
                            line=d_line,
                            content=format_value(d_val),
                            why=f"Code {code_val} exists on {sheet_name} but is missing from Consolidated.",
                            fix=f"Add account code {code_val} to Consolidated so it is included in totals.",
                        )
                    )

    return findings


# (3.5): Rule 5 - Required annual budget lines on Consolidated.
def check_required_lines(wb_formulas, wb_values) -> list[dict]:
    """Verify every required expense line exists on Consolidated with non-zero budget."""
    if CONSOLIDATED not in wb_values.sheetnames:
        return [
            make_finding(
                check="required_lines",
                severity="high",
                sheet=CONSOLIDATED,
                cell="",
                code=None,
                line="",
                content="",
                why="The Consolidated tab is missing, so required budget lines could not be verified.",
                fix="Restore the Consolidated tab in the budget master workbook.",
            )
        ]

    ws_val = wb_values[CONSOLIDATED]
    ws_form = wb_formulas[CONSOLIDATED]
    code_rows = {}
    for row in range(4, ws_val.max_row + 1):
        code_val = as_int(ws_val.cell(row=row, column=2).value)
        if code_val is not None and code_val not in code_rows:
            code_rows[code_val] = row

    findings = []
    for code, name in REQUIRED_LINES.items():
        if code not in code_rows:
            findings.append(
                make_finding(
                    check="required_lines",
                    severity="high",
                    sheet=CONSOLIDATED,
                    cell="",
                    code=code,
                    line=name,
                    content="",
                    why=f"No budget line for {name} ({code}).",
                    fix="Add this line to the appropriate department tab(s) and Consolidated, and budget it.",
                )
            )
        else:
            row = code_rows[code]
            d_val = ws_val.cell(row=row, column=4).value
            if d_val is None or (is_number(d_val) and d_val == 0):
                line_label = str(ws_val.cell(row=row, column=3).value or name).strip()
                findings.append(
                    make_finding(
                        check="required_lines",
                        severity="high",
                        sheet=CONSOLIDATED,
                        cell=f"D{row}",
                        code=code,
                        line=line_label,
                        content=format_cell(ws_form.cell(row=row, column=4)),
                        why=f"The {name} line ({code}) has no budget.",
                        fix="Budget this cost; it must be paid every year.",
                    )
                )

    return findings


##############################################
##  (4): Runner, Markdown report, and CLI.  ##
##############################################
# (4.1): Main entry point running all rules and sorting findings.
def finding_sort_key(
    finding: dict,
    sheet_order: dict[str, int],
) -> tuple[int, int, int, int, int]:
    """Sort key: high before review, sheet workbook order, row, then column."""
    severity_rank = 0 if finding["severity"] == "high" else 1
    sheet_rank = sheet_order.get(finding["sheet"], len(sheet_order))
    if finding["cell"]:
        row, col = coordinate_to_tuple(finding["cell"])
    else:
        row, col = (0, 0)
    check_rank = CHECK_ORDER.index(finding["check"])
    return (severity_rank, sheet_rank, row, col, check_rank)


def run_checks(path) -> list[dict]:
    """Load the workbook twice (formulas + cached values), run all rules, and sort."""
    if hasattr(path, "seek"):
        path.seek(0)
    wb_formulas = openpyxl.load_workbook(path, data_only=False)
    if hasattr(path, "seek"):
        path.seek(0)
    wb_values = openpyxl.load_workbook(path, data_only=True)

    try:
        sheet_order = {name: idx for idx, name in enumerate(wb_formulas.sheetnames)}
        findings = []
        findings.extend(check_parameters(wb_formulas, wb_values))
        findings.extend(check_rolled_forward(wb_formulas, wb_values))
        findings.extend(check_hard_coded(wb_formulas, wb_values))
        findings.extend(check_consistency(wb_formulas, wb_values))
        findings.extend(check_required_lines(wb_formulas, wb_values))
        findings.sort(key=lambda item: finding_sort_key(item, sheet_order))
        return findings
    finally:
        wb_formulas.close()
        wb_values.close()


# (4.2): Markdown report rendering helpers.
def escape_md_cell(text: str) -> str:
    """Escape pipe characters and collapse newlines for Markdown table cells."""
    single_line = text.replace("\r\n", " ").replace("\n", " ").replace("\r", " ")
    return single_line.replace("|", "\\|")


def format_md_code(content: str) -> str:
    """Wrap formula/value text in Markdown backticks after escaping pipes and newlines."""
    if content == "":
        return ""
    escaped = escape_md_cell(content)
    if "`" in escaped:
        return f"`` {escaped} ``"
    return f"`{escaped}`"


def section_explainer(check_name: str, driver_tabs: list[str]) -> str:
    """Return a plain-English 2-3 sentence explainer for each check section."""
    if check_name == "parameters":
        return (
            "This section checks whether rates, contracts, and assumptions on the "
            "Assumptions tab have a documented source, cover the full fiscal year, and "
            "match CPI inflation where applicable. It also flags claimed named ranges that "
            "do not exist yet and parameters not referenced by any budget formula. "
            "Review each item to confirm sources, dates, and links are complete."
        )
    if check_name == "rolled_forward":
        driver_list = ", ".join(driver_tabs) if driver_tabs else "none present"
        return (
            "This section flags department Annual Target formulas (column D) that start "
            "from last year's budget or actuals instead of being built from current-year "
            "drivers. Items marked high also apply a hard-coded multiplier rather than "
            "linking to an Assumptions rate. Driver tabs present in this workbook where "
            f"real calculations live: {driver_list}."
        )
    if check_name == "hard_coded":
        return (
            "This section identifies hard-coded numbers inside formulas, typed numbers "
            "sitting between formulas in the same row, and typed values that match an "
            "existing Assumptions parameter. Hard-coded numbers break automatic updates "
            "when rates or headcounts change. Replace typed constants with links to "
            "Assumptions or a supporting driver tab."
        )
    if check_name == "consistency":
        return (
            "This section checks internal arithmetic and coding integrity: whether "
            "Annual Budget equals the sum of the 12 months, whether Annual Target matches "
            "Annual Budget, whether department totals tie out to Consolidated, whether "
            "account codes appear in the Chart of Accounts, and whether text dashes sit in "
            "numeric cells. Fix high-severity mismatches before finalizing the budget."
        )
    return (
        "This section verifies that mandatory annual organizational expenses (such as "
        "statutory payroll deductions, audit fees, occupancy, insurance, and bank fees) "
        "exist on the Consolidated tab with a non-zero budget. Missing or zero lines "
        "indicate required costs that still need to be budgeted."
    )


def render_markdown(
    findings: list[dict],
    filename: str,
    generated_at: str,
    driver_tabs: list[str] | None = None,
) -> str:
    """Render findings into a structured Markdown report."""
    active_drivers = DRIVER_TABS if driver_tabs is None else driver_tabs
    lines = [
        "# Budget Integrity Check",
        "",
        f"**File:** {escape_md_cell(filename)}  ",
        f"**Generated:** {escape_md_cell(generated_at)}",
        "",
        (
            "This report checks the construction integrity of the budget workbook itself "
            "(formulas, hard-coded inputs, parameter validity, and internal consistency), "
            "rather than budget-vs-actuals variance. Items marked **high** are likely "
            "errors or unlinked hard-coded values that should be fixed; items marked "
            "**review** should be checked and confirmed."
        ),
        "",
        "## Summary",
        "",
        "| Check | High | Review |",
        "| --- | ---: | ---: |",
    ]

    grouped = {check: [] for check in CHECK_ORDER}
    for item in findings:
        grouped[item["check"]].append(item)

    for check in CHECK_ORDER:
        check_items = grouped[check]
        high_count = sum(1 for item in check_items if item["severity"] == "high")
        review_count = sum(1 for item in check_items if item["severity"] == "review")
        lines.append(f"| {CHECK_TITLES[check]} | {high_count} | {review_count} |")

    for check in CHECK_ORDER:
        lines.extend(
            [
                "",
                f"## {CHECK_TITLES[check]}",
                "",
                section_explainer(check, active_drivers),
                "",
            ]
        )
        check_items = grouped[check]
        if not check_items:
            lines.append("No findings.")
            continue

        lines.extend(
            [
                "| Severity | Cell | Code | Line | Formula / value | Why | Fix |",
                "| --- | --- | --- | --- | --- | --- | --- |",
            ]
        )
        for item in check_items:
            cell_ref = f"{item['sheet']}!{item['cell']}" if item["cell"] else item["sheet"]
            code_str = str(item["code"]) if item["code"] is not None else ""
            row_cells = [
                item["severity"],
                escape_md_cell(cell_ref),
                code_str,
                escape_md_cell(item["line"]),
                format_md_code(item["content"]),
                escape_md_cell(item["why"]),
                escape_md_cell(item["fix"]),
            ]
            lines.append(f"| {' | '.join(row_cells)} |")

    return "\n".join(lines) + "\n"


# (4.3): Command-line interface.
def main() -> None:
    """Parse CLI arguments, run checks, and write or print the Markdown report."""
    parser = argparse.ArgumentParser(
        description="Run Budget Integrity Checks on a GSS budget master workbook."
    )
    parser.add_argument("xlsx", help="Path to the budget master .xlsx workbook.")
    parser.add_argument(
        "-o",
        "--output",
        help="Optional path to write the Markdown report (prints to stdout if omitted).",
    )
    args = parser.parse_args()

    xlsx_path = Path(args.xlsx)
    findings = run_checks(xlsx_path)

    wb_names = openpyxl.load_workbook(xlsx_path, read_only=True, data_only=True)
    try:
        present_drivers = [name for name in DRIVER_TABS if name in wb_names.sheetnames]
    finally:
        wb_names.close()

    generated_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    report = render_markdown(
        findings,
        xlsx_path.name,
        generated_at,
        driver_tabs=present_drivers,
    )

    if args.output:
        out_path = Path(args.output)
        out_path.write_text(report, encoding="utf-8")
        high_count = sum(1 for item in findings if item["severity"] == "high")
        review_count = sum(1 for item in findings if item["severity"] == "review")
        print(
            f"Wrote {out_path}: {high_count} high, {review_count} review "
            f"({len(findings)} total)."
        )
    else:
        print(report, end="")


if __name__ == "__main__":
    main()
