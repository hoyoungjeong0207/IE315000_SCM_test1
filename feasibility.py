"""
feasibility.py — Constraint checking for submitted solutions.

Constraints checked (in order)
───────────────────────────────
C1  Non-negativity         x_sf, x_fc ≥ 0               (already done in parser)
C2  Binary facility        y_j ∈ {0, 1}                 (already done in parser)
C3  Demand satisfaction    Σ_j x_fc[j][k] = d[k]        for each customer k
C4  Flow balance           Σ_i x_sf[i][j] = Σ_k x_fc[j][k]  for each facility j  (single-period: no inventory)
C5  Facility capacity      Σ_k x_fc[j][k] ≤ cap_f[j] · y[j]  for each facility j
C6  Inflow capacity        Σ_i x_sf[i][j] ≤ cap_f[j] · y[j]  for each facility j
C7  Supply capacity        Σ_j x_sf[i][j] ≤ cap_s[i]          for each supplier i
"""

from __future__ import annotations

from config import PROBLEM, SCORING, EPSILON


# ── Data classes (plain dicts to stay dependency-free) ──────────────────────

def _violation(constraint: str, description: str, amount: float) -> dict:
    return {"constraint": constraint, "description": description, "amount": round(amount, 4)}


# ── Public interface ─────────────────────────────────────────────────────────

def check_feasibility(solution: dict) -> dict:
    """
    Check all constraints and compute total penalty.

    Returns
    -------
    {
        'is_feasible':   bool,
        'violations':    list[dict],   # each has constraint, description, amount
        'total_penalty': float,
    }
    """
    p = PROBLEM
    s = SCORING
    violations: list[dict] = []

    y    = solution["y"]
    x_sf = solution["x_sf"]
    x_fc = solution["x_fc"]

    # ── C3 Demand satisfaction ────────────────────────────────────────────────
    for k in p["customers"]:
        delivered = sum(x_fc[j].get(k, 0.0) for j in p["facilities"])
        diff = abs(delivered - p["demand"][k])
        if diff > EPSILON:
            violations.append(_violation(
                "C3-Demand",
                f"Customer {k}: delivered={delivered:.2f}, required={p['demand'][k]}",
                diff,
            ))

    # ── C4 Flow balance at each facility (single-period: inflow = outflow) ───
    for j in p["facilities"]:
        inflow  = sum(x_sf[i].get(j, 0.0) for i in p["suppliers"])
        outflow = sum(x_fc[j].get(k, 0.0) for k in p["customers"])
        imbal   = abs(inflow - outflow)
        if imbal > EPSILON:
            violations.append(_violation(
                "C4-Balance",
                f"Facility {j}: inflow={inflow:.2f} ≠ outflow={outflow:.2f} "
                f"(imbalance={imbal:.4f})",
                imbal,
            ))

    # ── C5 Facility outflow capacity ─────────────────────────────────────────
    for j in p["facilities"]:
        outflow = sum(x_fc[j].get(k, 0.0) for k in p["customers"])
        limit   = p["facility_capacity"][j] * y[j]
        excess  = outflow - limit
        if excess > EPSILON:
            violations.append(_violation(
                "C5-FacilityCapacity",
                f"Facility {j} outflow={outflow:.2f} exceeds capacity "
                f"{p['facility_capacity'][j]}×y={y[j]} = {limit:.0f}",
                excess,
            ))

    # ── C6 Facility inflow capacity ───────────────────────────────────────────
    for j in p["facilities"]:
        inflow = sum(x_sf[i].get(j, 0.0) for i in p["suppliers"])
        limit  = p["facility_capacity"][j] * y[j]
        excess = inflow - limit
        if excess > EPSILON:
            violations.append(_violation(
                "C6-InflowCapacity",
                f"Facility {j} inflow={inflow:.2f} exceeds capacity "
                f"{p['facility_capacity'][j]}×y={y[j]} = {limit:.0f}",
                excess,
            ))

    # ── C7 Supplier capacity ──────────────────────────────────────────────────
    for i in p["suppliers"]:
        total_out = sum(x_sf[i].get(j, 0.0) for j in p["facilities"])
        cap       = p["supply_capacity"][i]
        excess    = total_out - cap
        if excess > EPSILON:
            violations.append(_violation(
                "C7-SupplyCapacity",
                f"Supplier {i}: total flow={total_out:.2f} exceeds capacity={cap}",
                excess,
            ))

    # ── Penalty calculation ────────────────────────────────────────────────────
    penalty = 0.0
    for v in violations:
        c = v["constraint"]
        a = v["amount"]
        if c.startswith("C3"):
            penalty += a * s["penalty_demand_unit"]
        elif c.startswith("C4"):
            penalty += a * s["penalty_balance_unit"]
        elif c.startswith("C5") or c.startswith("C6"):
            penalty += a * s["penalty_capacity_unit"]
        elif c.startswith("C7"):
            penalty += a * s["penalty_supply_unit"]

    return {
        "is_feasible":   len(violations) == 0,
        "violations":    violations,
        "total_penalty": round(penalty, 4),
    }
