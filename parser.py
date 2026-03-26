"""
parser.py — CSV decision-variable parser.

Expected CSV format (two columns, header row required):

    variable,value
    y_F1,1
    y_F2,0
    y_F3,1
    x_S1_F1,200
    x_S1_F3,100
    x_S2_F3,90
    x_F1_C1,80
    x_F1_C2,120
    x_F3_C3,100
    x_F3_C4,90
    I_F1,0
    I_F3,0

Variable naming rules
─────────────────────
  y_{J}         Facility open decision  (J ∈ facilities)
  x_{A}_{B}     Flow from A to B
                  A ∈ suppliers  → B ∈ facilities   (supply flow)
                  A ∈ facilities → B ∈ customers    (demand flow)

Rules
─────
* Omitted variables default to 0.
* All y_{J} rows are REQUIRED (students must state each facility decision explicitly).
* Values must be numeric.
* y values must be 0 or 1 (integer).
* x values must be ≥ 0.
* Duplicate variable names are not allowed.
* Single-period model: no inventory variables.
"""

from __future__ import annotations

import io
import re
from typing import Any

import pandas as pd

from config import PROBLEM, EPSILON


# ── Public interface ──────────────────────────────────────────────────────────

def parse_csv(file_obj) -> tuple[bool, list[str], dict[str, Any]]:
    """
    Parse an uploaded CSV file into a structured solution dict.

    Parameters
    ----------
    file_obj : file-like object (from Streamlit st.file_uploader)

    Returns
    -------
    ok      : bool          — False if any hard error was found
    errors  : list[str]     — human-readable messages (errors + warnings)
    solution: dict          — structured solution; empty dict on hard error
    """
    errors: list[str] = []

    # ── 1. Read raw CSV ───────────────────────────────────────────────────────
    try:
        content = file_obj.read()
        if isinstance(content, bytes):
            content = content.decode("utf-8-sig")  # handle BOM
        df = pd.read_csv(io.StringIO(content))
    except Exception as exc:
        return False, [f"Cannot read CSV file: {exc}"], {}

    # ── 2. Column structure ───────────────────────────────────────────────────
    df.columns = [c.strip().lower() for c in df.columns]
    if list(df.columns) != ["variable", "value"]:
        return False, [
            f"CSV must have exactly two columns named 'variable' and 'value'. "
            f"Found: {list(df.columns)}"
        ], {}

    df["variable"] = df["variable"].astype(str).str.strip()
    df["value"]    = df["value"].astype(str).str.strip()

    if df.empty:
        return False, ["CSV file has no data rows."], {}

    # ── 3. Duplicate check ────────────────────────────────────────────────────
    dupes = df["variable"][df["variable"].duplicated()].tolist()
    if dupes:
        errors.append(f"Duplicate variable names found: {dupes}")
        return False, errors, {}

    # ── 4. Numeric value check ────────────────────────────────────────────────
    def to_float(val: str) -> tuple[bool, float]:
        try:
            return True, float(val)
        except ValueError:
            return False, 0.0

    rows: dict[str, float] = {}
    bad_values = []
    for _, row in df.iterrows():
        ok_num, fval = to_float(row["value"])
        if not ok_num:
            bad_values.append(f"  '{row['variable']}' = '{row['value']}' (not a number)")
        else:
            rows[row["variable"]] = fval

    if bad_values:
        errors.append("Non-numeric values:\n" + "\n".join(bad_values))
        return False, errors, {}

    # ── 5. Classify variables ─────────────────────────────────────────────────
    suppliers  = set(PROBLEM["suppliers"])
    facilities = set(PROBLEM["facilities"])
    customers  = set(PROBLEM["customers"])

    # Valid name patterns
    y_pattern   = re.compile(r"^y_([A-Z0-9]+)$")
    x_pattern   = re.compile(r"^x_([A-Z0-9]+)_([A-Z0-9]+)$")
    inv_pattern = re.compile(r"^I_([A-Z0-9]+)$")

    y_vars:   dict[str, float] = {}
    xsf_vars: dict[str, dict[str, float]] = {s: {} for s in suppliers}
    xfc_vars: dict[str, dict[str, float]] = {f: {} for f in facilities}
    unknown:  list[str] = []

    for var, val in rows.items():
        m_y = y_pattern.match(var)
        m_x = x_pattern.match(var)

        if m_y:
            j = m_y.group(1)
            if j not in facilities:
                unknown.append(f"  '{var}' — '{j}' is not a known facility")
            else:
                y_vars[j] = val

        elif m_x:
            a, b = m_x.group(1), m_x.group(2)
            if a in suppliers and b in facilities:
                xsf_vars[a][b] = val
            elif a in facilities and b in customers:
                xfc_vars[a][b] = val
            else:
                unknown.append(
                    f"  '{var}' — '{a}'→'{b}' is not a valid supplier→facility "
                    f"or facility→customer pair"
                )

        elif inv_pattern.match(var):
            unknown.append(
                f"  '{var}' — inventory variables are not used in this single-period model"
            )

        else:
            unknown.append(f"  '{var}' — unrecognised variable name")

    if unknown:
        errors.append("Unknown or invalid variable names:\n" + "\n".join(unknown))
        return False, errors, {}

    # ── 6. Required variables ─────────────────────────────────────────────────
    missing_y = [f"y_{j}" for j in facilities if j not in y_vars]
    if missing_y:
        errors.append(
            f"All facility open-decision variables are required. Missing: {missing_y}"
        )
        return False, errors, {}

    # ── 7. Domain checks ──────────────────────────────────────────────────────
    domain_errors = []

    for j, val in y_vars.items():
        if val not in (0.0, 1.0):
            domain_errors.append(f"  y_{j} = {val}  (must be 0 or 1)")

    for s, fdict in xsf_vars.items():
        for f, val in fdict.items():
            if val < -EPSILON:
                domain_errors.append(f"  x_{s}_{f} = {val}  (must be ≥ 0)")

    for f, cdict in xfc_vars.items():
        for c, val in cdict.items():
            if val < -EPSILON:
                domain_errors.append(f"  x_{f}_{c} = {val}  (must be ≥ 0)")

    if domain_errors:
        errors.append("Domain violations:\n" + "\n".join(domain_errors))
        return False, errors, {}

    # ── 8. Fill defaults (missing = 0) ────────────────────────────────────────
    for j in facilities:
        for s in suppliers:
            if j not in xsf_vars[s]:
                xsf_vars[s][j] = 0.0
        for c in customers:
            if c not in xfc_vars[j]:
                xfc_vars[j][c] = 0.0

    solution = {
        "y":    y_vars,    # {facility: 0|1}
        "x_sf": xsf_vars,  # {supplier: {facility: float}}
        "x_fc": xfc_vars,  # {facility: {customer: float}}
    }

    return True, errors, solution
