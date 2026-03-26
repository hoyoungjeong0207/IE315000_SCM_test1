"""
config.py — Problem instance definition and scoring parameters.

Modify this file to change the problem or adjust scoring weights.
Do NOT share this file with students (it contains penalty rates and reference cost).
"""

# ─── Problem Instance ──────────────────────────────────────────────────────────

PROBLEM = {
    # Set labels
    "suppliers":  ["S1", "S2"],
    "facilities": ["F1", "F2", "F3"],
    "customers":  ["C1", "C2", "C3", "C4"],

    # Supplier → max total outflow
    "supply_capacity": {
        "S1": 300,
        "S2": 250,
    },

    # Facility → max throughput (only if open)
    "facility_capacity": {
        "F1": 200,
        "F2": 250,
        "F3": 300,
    },

    # Fixed cost to open a facility
    "facility_fixed_cost": {
        "F1": 1000,
        "F2": 1500,
        "F3": 1200,
    },

    # Customer demand (must be fully satisfied)
    "demand": {
        "C1": 80,
        "C2": 120,
        "C3": 100,
        "C4": 90,
    },

    # Unit transport cost: supplier → facility
    # cost_sf[supplier][facility]
    "cost_sf": {
        "S1": {"F1": 2, "F2": 4, "F3": 3},
        "S2": {"F1": 5, "F2": 2, "F3": 4},
    },

    # Unit transport cost: facility → customer
    # cost_fc[facility][customer]
    "cost_fc": {
        "F1": {"C1": 3, "C2": 5, "C3": 7, "C4": 6},
        "F2": {"C1": 6, "C2": 2, "C3": 4, "C4": 5},
        "F3": {"C1": 5, "C2": 4, "C3": 2, "C4": 3},
    },

}

# ─── Scoring Parameters ─────────────────────────────────────────────────────────

SCORING = {
    # Known near-optimal total cost (used as score baseline).
    # score = min(10000, round(10000 * reference_cost / effective_cost))
    # A submission matching this cost exactly earns 10 000 points.
    "reference_cost": 4570,

    "max_score": 10000,

    # Penalty rates (per unit of violation)
    # Set high enough that infeasibility is always worse than feasibility.
    "penalty_demand_unit":   200,   # per unit of unmet / excess demand per customer
    "penalty_capacity_unit": 100,   # per unit over facility capacity
    "penalty_supply_unit":   100,   # per unit over supplier capacity
    "penalty_balance_unit":  150,   # per unit of flow imbalance at facility
    "penalty_binary":        500,   # flat per-facility penalty for non-binary y
}

# ─── Tolerance for float comparisons ────────────────────────────────────────────
EPSILON = 1e-6
