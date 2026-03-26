"""
scoring.py — Objective value computation and final score calculation.

Objective (minimization) — single-period model
───────────────────────────────────────────────
  min  Σ_j  f[j] · y[j]                         (fixed facility cost)
     + Σ_ij c_sf[i][j] · x_sf[i][j]             (supplier → facility transport)
     + Σ_jk c_fc[j][k] · x_fc[j][k]             (facility → customer transport)

Score formula (higher = better)
─────────────────────────────────
  effective_cost = total_cost + total_penalty
  score = min(max_score, round(max_score × reference_cost / effective_cost))

  • A submission at or below reference cost earns max_score (10 000).
  • Infeasible submissions accumulate large penalties, collapsing their score.
"""

from __future__ import annotations

from config import PROBLEM, SCORING


# ── Public interface ──────────────────────────────────────────────────────────

def compute_objective(solution: dict) -> dict:
    """
    Compute the four cost components and total objective value.

    Returns
    -------
    {
        'fixed_cost':         float,
        'transport_cost_sf':  float,
        'transport_cost_fc':  float,
        'holding_cost':       float,
        'total_cost':         float,
    }
    """
    p = PROBLEM
    y    = solution["y"]
    x_sf = solution["x_sf"]
    x_fc = solution["x_fc"]

    fixed = sum(
        p["facility_fixed_cost"][j] * y[j]
        for j in p["facilities"]
    )

    transport_sf = sum(
        p["cost_sf"][i][j] * x_sf[i].get(j, 0.0)
        for i in p["suppliers"]
        for j in p["facilities"]
    )

    transport_fc = sum(
        p["cost_fc"][j][k] * x_fc[j].get(k, 0.0)
        for j in p["facilities"]
        for k in p["customers"]
    )

    total = fixed + transport_sf + transport_fc

    return {
        "fixed_cost":        round(fixed, 4),
        "transport_cost_sf": round(transport_sf, 4),
        "transport_cost_fc": round(transport_fc, 4),
        "total_cost":        round(total, 4),
    }


def compute_score(objective: dict, feasibility: dict) -> dict:
    """
    Combine objective value and feasibility penalty into a final score.

    Returns
    -------
    {
        'objective_value': float,
        'penalty':         float,
        'effective_cost':  float,
        'score':           int,
    }
    """
    ref      = SCORING["reference_cost"]
    max_sc   = SCORING["max_score"]
    obj_val  = objective["total_cost"]
    penalty  = feasibility["total_penalty"]
    eff_cost = obj_val + penalty

    if eff_cost <= 0:
        score = max_sc
    else:
        score = min(max_sc, round(max_sc * ref / eff_cost))

    return {
        "objective_value": round(obj_val, 4),
        "penalty":         round(penalty, 4),
        "effective_cost":  round(eff_cost, 4),
        "score":           score,
    }
