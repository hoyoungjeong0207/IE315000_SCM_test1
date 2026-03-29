"""
db.py — Google Sheets persistence layer.

Worksheets
──────────
submissions     — one row per submission
resubmit_tokens — one row per granted token (student_id only)

Streamlit secrets required (.streamlit/secrets.toml):
    [gcp_service_account]
    type = "service_account"
    project_id = "..."
    private_key_id = "..."
    private_key = "..."
    client_email = "..."
    ...

    [sheet]
    id = "YOUR_GOOGLE_SHEET_ID"
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import gspread
import streamlit as st
from google.oauth2.service_account import Credentials

# ── Constants ─────────────────────────────────────────────────────────────────

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# Streamlit secrets layout (two supported formats):
#
# Format A — JSON string (recommended, avoids TOML multiline issues):
#   gcp_json = '{"type":"service_account","private_key":"-----BEGIN...",...}'
#   [sheet]
#   id = "SHEET_ID"
#
# Format B — expanded TOML table (legacy):
#   [gcp_service_account]
#   type = "service_account"
#   private_key = "..."
#   ...
#   [sheet]
#   id = "SHEET_ID"

SUBMISSIONS_HEADERS = [
    "id", "student_id", "student_name", "submitted_at",
    "score", "objective_value", "penalty", "effective_cost",
    "is_feasible", "fixed_cost", "transport_sf", "transport_fc",
    "violation_count", "violation_json", "raw_csv",
]
TOKENS_HEADERS = ["student_id"]


# ── Connection (cached per session) ───────────────────────────────────────────

@st.cache_resource
def _get_spreadsheet():
    if "gcp_json" in st.secrets:
        # Format A: entire service account JSON stored as a string
        creds_info = json.loads(st.secrets["gcp_json"])
    else:
        # Format B: expanded TOML table
        creds_info = dict(st.secrets["gcp_service_account"])
    creds = Credentials.from_service_account_info(creds_info, scopes=SCOPES)
    client = gspread.authorize(creds)
    return client.open_by_key(st.secrets["sheet"]["id"])


def _submissions_ws() -> gspread.Worksheet:
    return _get_spreadsheet().worksheet("submissions")


def _tokens_ws() -> gspread.Worksheet:
    return _get_spreadsheet().worksheet("resubmit_tokens")


# ── Schema ────────────────────────────────────────────────────────────────────

def init_db() -> None:
    """Create worksheets with headers if they don't already exist."""
    sh = _get_spreadsheet()
    existing = [ws.title for ws in sh.worksheets()]

    if "submissions" not in existing:
        ws = sh.add_worksheet("submissions", rows=500, cols=len(SUBMISSIONS_HEADERS))
        ws.append_row(SUBMISSIONS_HEADERS, value_input_option="RAW")

    if "resubmit_tokens" not in existing:
        ws = sh.add_worksheet("resubmit_tokens", rows=200, cols=1)
        ws.append_row(TOKENS_HEADERS, value_input_option="RAW")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _all_submissions() -> list[dict]:
    """Return all submission rows as list of dicts (excludes header)."""
    return _submissions_ws().get_all_records()


def _next_id(rows: list[dict]) -> int:
    if not rows:
        return 1
    return max(int(r["id"]) for r in rows) + 1


# ── Write ─────────────────────────────────────────────────────────────────────

def save_submission(
    student_id:   str,
    student_name: str,
    score_result: dict,
    obj_result:   dict,
    feas_result:  dict,
    raw_csv:      str,
) -> int:
    """Append a submission row and return its id."""
    ws = _submissions_ws()
    rows = _all_submissions()
    new_id = _next_id(rows)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    row = [
        new_id,
        student_id,
        student_name,
        now,
        score_result["score"],
        obj_result["total_cost"],
        score_result["penalty"],
        score_result["effective_cost"],
        1 if feas_result["is_feasible"] else 0,
        obj_result["fixed_cost"],
        obj_result["transport_cost_sf"],
        obj_result["transport_cost_fc"],
        len(feas_result["violations"]),
        json.dumps(feas_result["violations"]),
        raw_csv,
    ]
    ws.append_row(row, value_input_option="RAW")
    return new_id


# ── Read ──────────────────────────────────────────────────────────────────────

def get_leaderboard(top_n: int = 30) -> list[dict]:
    """Return one row per student with their best score, ranked."""
    rows = _all_submissions()
    if not rows:
        return []

    # Group by student_id, keep row with highest score (tie-break: earliest time)
    best: dict[str, dict] = {}
    attempts: dict[str, int] = {}

    for r in rows:
        sid = str(r["student_id"])
        attempts[sid] = attempts.get(sid, 0) + 1
        score = int(r["score"])
        if sid not in best or score > int(best[sid]["score"]):
            best[sid] = r
        elif score == int(best[sid]["score"]):
            if str(r["submitted_at"]) < str(best[sid]["submitted_at"]):
                best[sid] = r

    ranked = sorted(
        best.values(),
        key=lambda r: (-int(r["score"]), str(r["submitted_at"])),
    )[:top_n]

    result = []
    for i, r in enumerate(ranked, start=1):
        sid = str(r["student_id"])
        result.append({
            "rank":           i,
            "student_id":     sid,
            "student_name":   r["student_name"],
            "best_score":     int(r["score"]),
            "best_objective": float(r["objective_value"]) if r["objective_value"] != "" else None,
            "best_feasible":  int(r["is_feasible"]),
            "attempts":       attempts.get(sid, 1),
            "best_at":        r["submitted_at"],
        })
    return result


def get_student_history(student_id: str) -> list[dict]:
    """Return all submissions for one student, newest first."""
    rows = _all_submissions()
    student_rows = [r for r in rows if str(r["student_id"]) == student_id]
    student_rows.sort(key=lambda r: str(r["submitted_at"]), reverse=True)
    return [
        {
            "id":              int(r["id"]),
            "submitted_at":    r["submitted_at"],
            "score":           int(r["score"]),
            "objective_value": float(r["objective_value"]) if r["objective_value"] != "" else None,
            "penalty":         float(r["penalty"]) if r["penalty"] != "" else None,
            "effective_cost":  float(r["effective_cost"]) if r["effective_cost"] != "" else None,
            "is_feasible":     int(r["is_feasible"]),
            "violation_count": int(r["violation_count"]) if r["violation_count"] != "" else 0,
        }
        for r in student_rows
    ]


def has_submitted(student_id: str) -> bool:
    rows = _all_submissions()
    return any(str(r["student_id"]) == student_id for r in rows)


def get_all_submissions() -> list[dict]:
    """Return every submission row for admin review, newest first."""
    rows = _all_submissions()
    rows_sorted = sorted(rows, key=lambda r: str(r["submitted_at"]), reverse=True)
    return [
        {
            "id":              int(r["id"]),
            "submitted_at":    r["submitted_at"],
            "student_id":      str(r["student_id"]),
            "student_name":    r["student_name"],
            "score":           int(r["score"]),
            "objective_value": float(r["objective_value"]) if r["objective_value"] != "" else None,
            "is_feasible":     int(r["is_feasible"]),
        }
        for r in rows_sorted
    ]


def delete_submissions(ids: list[int]) -> int:
    """Delete submissions by id list. Returns number of rows deleted."""
    if not ids:
        return 0

    ws = _submissions_ws()
    all_rows = ws.get_all_values()  # includes header row
    ids_set = {int(i) for i in ids}

    # Collect 1-based sheet row indices to delete (row 1 = header)
    to_delete = []
    for sheet_row_idx, row in enumerate(all_rows[1:], start=2):
        if row and str(row[0]).isdigit() and int(row[0]) in ids_set:
            to_delete.append(sheet_row_idx)

    # Delete from bottom to top so indices stay valid
    for row_idx in sorted(to_delete, reverse=True):
        ws.delete_rows(row_idx)

    return len(to_delete)


def get_rank(student_id: str) -> tuple[int, int]:
    """Return (rank, total_students) for the student's best score."""
    rows = _all_submissions()
    best_by_student: dict[str, int] = {}
    for r in rows:
        sid = str(r["student_id"])
        score = int(r["score"])
        if sid not in best_by_student or score > best_by_student[sid]:
            best_by_student[sid] = score

    sorted_sids = sorted(best_by_student, key=lambda s: -best_by_student[s])
    total = len(sorted_sids)
    try:
        rank = sorted_sids.index(student_id) + 1
    except ValueError:
        rank = 0
    return rank, total


# ── Resubmit tokens ───────────────────────────────────────────────────────────

def has_resubmit_token(student_id: str) -> bool:
    records = _tokens_ws().get_all_records()
    return any(str(r["student_id"]) == student_id for r in records)


def grant_resubmit(student_id: str) -> None:
    if not has_resubmit_token(student_id):
        _tokens_ws().append_row([student_id], value_input_option="RAW")


def consume_resubmit_token(student_id: str) -> None:
    ws = _tokens_ws()
    all_rows = ws.get_all_values()
    for sheet_row_idx, row in enumerate(all_rows[1:], start=2):
        if row and str(row[0]) == student_id:
            ws.delete_rows(sheet_row_idx)
            return


def get_resubmit_tokens() -> list[str]:
    records = _tokens_ws().get_all_records()
    return [str(r["student_id"]) for r in records]
