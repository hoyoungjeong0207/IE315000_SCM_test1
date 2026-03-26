"""
db.py — SQLite persistence layer.

Tables
──────
submissions
    id              INTEGER PK AUTOINCREMENT
    student_id      TEXT NOT NULL
    student_name    TEXT NOT NULL
    submitted_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    score           INTEGER NOT NULL
    objective_value REAL
    penalty         REAL
    effective_cost  REAL
    is_feasible     INTEGER   (0 or 1)
    fixed_cost      REAL
    transport_sf    REAL
    transport_fc    REAL
    holding_cost    REAL
    violation_count INTEGER
    violation_json  TEXT      (JSON array of violation dicts)
    raw_csv         TEXT      (original uploaded content)
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "submissions.db"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _connect(db_path: Path = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


# ── Schema ────────────────────────────────────────────────────────────────────

def init_db(db_path: Path = DB_PATH) -> None:
    """Create tables if they don't already exist."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with _connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS submissions (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id      TEXT    NOT NULL,
                student_name    TEXT    NOT NULL,
                submitted_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                score           INTEGER NOT NULL,
                objective_value REAL,
                penalty         REAL,
                effective_cost  REAL,
                is_feasible     INTEGER,
                fixed_cost      REAL,
                transport_sf    REAL,
                transport_fc    REAL,
                violation_count INTEGER,
                violation_json  TEXT,
                raw_csv         TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS resubmit_tokens (
                student_id TEXT PRIMARY KEY
            )
        """)
        conn.commit()


# ── Write ─────────────────────────────────────────────────────────────────────

def save_submission(
    student_id:    str,
    student_name:  str,
    score_result:  dict,
    obj_result:    dict,
    feas_result:   dict,
    raw_csv:       str,
    db_path: Path = DB_PATH,
) -> int:
    """Insert a submission row and return the new row id."""
    with _connect(db_path) as conn:
        cursor = conn.execute("""
            INSERT INTO submissions
                (student_id, student_name, score, objective_value, penalty,
                 effective_cost, is_feasible, fixed_cost, transport_sf,
                 transport_fc, violation_count, violation_json, raw_csv)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            student_id,
            student_name,
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
        ))
        conn.commit()
        return cursor.lastrowid


# ── Read ──────────────────────────────────────────────────────────────────────

def get_leaderboard(top_n: int = 30, db_path: Path = DB_PATH) -> list[dict]:
    """
    Return one row per student showing their best score.
    Ranked by best score descending, then by earliest best submission time.
    """
    with _connect(db_path) as conn:
        rows = conn.execute("""
            SELECT
                ROW_NUMBER() OVER (ORDER BY best_score DESC, best_at ASC) AS rank,
                student_id,
                student_name,
                best_score,
                best_objective,
                best_feasible,
                attempts,
                best_at
            FROM (
                SELECT
                    s.student_id,
                    s.student_name,
                    s.score           AS best_score,
                    s.objective_value AS best_objective,
                    s.is_feasible     AS best_feasible,
                    c.attempts,
                    s.submitted_at    AS best_at
                FROM submissions s
                JOIN (
                    SELECT student_id, MAX(score) AS max_score, COUNT(*) AS attempts
                    FROM submissions
                    GROUP BY student_id
                ) c ON s.student_id = c.student_id AND s.score = c.max_score
                GROUP BY s.student_id
            )
            LIMIT ?
        """, (top_n,)).fetchall()
    return [dict(r) for r in rows]


def get_student_history(student_id: str, db_path: Path = DB_PATH) -> list[dict]:
    """Return all submissions for one student, newest first."""
    with _connect(db_path) as conn:
        rows = conn.execute("""
            SELECT id, submitted_at, score, objective_value, penalty,
                   effective_cost, is_feasible, violation_count
            FROM submissions
            WHERE student_id = ?
            ORDER BY submitted_at DESC
        """, (student_id,)).fetchall()
    return [dict(r) for r in rows]


def has_submitted(student_id: str, db_path: Path = DB_PATH) -> bool:
    """Return True if student has at least one submission."""
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT 1 FROM submissions WHERE student_id = ? LIMIT 1", (student_id,)
        ).fetchone()
    return row is not None


def has_resubmit_token(student_id: str, db_path: Path = DB_PATH) -> bool:
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT 1 FROM resubmit_tokens WHERE student_id = ?", (student_id,)
        ).fetchone()
    return row is not None


def grant_resubmit(student_id: str, db_path: Path = DB_PATH) -> None:
    with _connect(db_path) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO resubmit_tokens (student_id) VALUES (?)", (student_id,)
        )
        conn.commit()


def consume_resubmit_token(student_id: str, db_path: Path = DB_PATH) -> None:
    with _connect(db_path) as conn:
        conn.execute("DELETE FROM resubmit_tokens WHERE student_id = ?", (student_id,))
        conn.commit()


def get_resubmit_tokens(db_path: Path = DB_PATH) -> list[str]:
    with _connect(db_path) as conn:
        rows = conn.execute("SELECT student_id FROM resubmit_tokens").fetchall()
    return [r["student_id"] for r in rows]


def get_all_submissions(db_path: Path = DB_PATH) -> list[dict]:
    """Return every submission row for admin review, newest first."""
    with _connect(db_path) as conn:
        rows = conn.execute("""
            SELECT id, submitted_at, student_id, student_name,
                   score, objective_value, is_feasible
            FROM submissions
            ORDER BY submitted_at DESC
        """).fetchall()
    return [dict(r) for r in rows]


def delete_submissions(ids: list[int], db_path: Path = DB_PATH) -> int:
    """Delete submissions by row id list. Returns number of rows deleted."""
    if not ids:
        return 0
    placeholders = ",".join("?" * len(ids))
    with _connect(db_path) as conn:
        cursor = conn.execute(
            f"DELETE FROM submissions WHERE id IN ({placeholders})", ids
        )
        conn.commit()
    return cursor.rowcount


def get_rank(student_id: str, db_path: Path = DB_PATH) -> tuple[int, int]:
    """
    Return (rank, total_students) for the student's best score.
    Returns (0, total) if not found.
    """
    with _connect(db_path) as conn:
        best_scores = conn.execute("""
            SELECT student_id, MAX(score) AS best_score
            FROM submissions
            GROUP BY student_id
            ORDER BY best_score DESC
        """).fetchall()

    student_ids = [r["student_id"] for r in best_scores]
    total = len(student_ids)
    try:
        rank = student_ids.index(student_id) + 1
    except ValueError:
        rank = 0
    return rank, total
