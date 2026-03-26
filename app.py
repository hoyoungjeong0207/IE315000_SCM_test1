"""
app.py — Streamlit entry point for the SCM Competition Platform.

Run with:
    streamlit run app.py
"""

from __future__ import annotations

import io
import json

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

import db
import feasibility as feas_mod
import parser as csv_parser
import scoring as scoring_mod
from config import PROBLEM, SCORING

# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="SCM Optimization Competition",
    page_icon="🏭",
    layout="wide",
)

# ── Init DB ───────────────────────────────────────────────────────────────────

db.init_db()

# ── Helpers ───────────────────────────────────────────────────────────────────

def score_color(score: int) -> str:
    if score >= 9000:
        return "green"
    if score >= 7000:
        return "orange"
    return "red"


def feasibility_badge(is_feasible: bool) -> str:
    return "✅ Feasible" if is_feasible else "❌ Infeasible"


# ── Network diagram ───────────────────────────────────────────────────────────

def draw_network() -> plt.Figure:
    """Draw a three-tier supply chain network diagram."""
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.axis("off")
    fig.patch.set_facecolor("#0e1117")  # match Streamlit dark background
    ax.set_facecolor("#0e1117")

    # ── Node positions ────────────────────────────────────────────────────────
    suppliers  = {"S1": (1.2, 7.0), "S2": (1.2, 3.0)}
    facilities = {"F1": (5.0, 8.2), "F2": (5.0, 5.0), "F3": (5.0, 1.8)}
    customers  = {"C1": (8.8, 8.5), "C2": (8.8, 6.2), "C3": (8.8, 3.8), "C4": (8.8, 1.5)}

    NODE_R   = 0.52
    C_SUPPLY = "#4fc3f7"   # blue  — suppliers
    C_FAC    = "#81c784"   # green — facilities
    C_CUST   = "#ffb74d"   # amber — customers
    C_EDGE1  = "#4fc3f7"
    C_EDGE2  = "#ffb74d"
    TXT      = "white"

    def draw_node(pos, label, color, radius=NODE_R):
        circle = plt.Circle(pos, radius, color=color, zorder=3)
        ax.add_patch(circle)
        ax.text(pos[0], pos[1], label, ha="center", va="center",
                fontsize=11, fontweight="bold", color="#0e1117", zorder=4)

    def draw_arrow(src, dst, color, lw=1.4, alpha=0.55):
        dx = dst[0] - src[0]
        dy = dst[1] - src[1]
        dist = (dx**2 + dy**2) ** 0.5
        # shorten start and end by node radius
        ux, uy = dx / dist, dy / dist
        x0 = src[0] + ux * NODE_R
        y0 = src[1] + uy * NODE_R
        x1 = dst[0] - ux * NODE_R
        y1 = dst[1] - uy * NODE_R
        ax.annotate(
            "", xy=(x1, y1), xytext=(x0, y0),
            arrowprops=dict(
                arrowstyle="-|>", color=color,
                lw=lw, alpha=alpha,
                mutation_scale=14,
            ),
            zorder=2,
        )

    # ── Tier labels ───────────────────────────────────────────────────────────
    for x, label, col in [(1.2, "Suppliers", C_SUPPLY),
                           (5.0, "Facilities", C_FAC),
                           (8.8, "Customers", C_CUST)]:
        ax.text(x, 9.6, label, ha="center", va="center",
                fontsize=12, fontweight="bold", color=col)
        ax.plot([x - 0.9, x + 0.9], [9.25, 9.25], color=col, lw=1.5, alpha=0.6)

    # ── Edges: supplier → facility ────────────────────────────────────────────
    for spos in suppliers.values():
        for fpos in facilities.values():
            draw_arrow(spos, fpos, color=C_EDGE1)

    # ── Edges: facility → customer ────────────────────────────────────────────
    for fpos in facilities.values():
        for cpos in customers.values():
            draw_arrow(fpos, cpos, color=C_EDGE2)

    # ── Nodes ─────────────────────────────────────────────────────────────────
    for label, pos in suppliers.items():
        draw_node(pos, label, C_SUPPLY)
    for label, pos in facilities.items():
        draw_node(pos, label, C_FAC)
    for label, pos in customers.items():
        draw_node(pos, label, C_CUST)

    # ── Legend ────────────────────────────────────────────────────────────────
    legend_items = [
        mpatches.Patch(color=C_SUPPLY, label="Supplier  (fixed supply capacity)"),
        mpatches.Patch(color=C_FAC,    label="Facility  (open/close decision · capacity constraint)"),
        mpatches.Patch(color=C_CUST,   label="Customer  (fixed demand, must be fully met)"),
    ]
    ax.legend(handles=legend_items, loc="lower center",
              ncol=1, fontsize=9,
              facecolor="#1e2129", edgecolor="gray", labelcolor=TXT,
              bbox_to_anchor=(0.5, -0.04))

    # ── Variable annotations ──────────────────────────────────────────────────
    ax.text(3.1, 9.1, "x_Si_Fj", fontsize=8.5, color=C_EDGE1,
            ha="center", style="italic")
    ax.text(6.9, 9.1, "x_Fj_Ck", fontsize=8.5, color=C_EDGE2,
            ha="center", style="italic")
    ax.text(5.0, 4.35, "y_Fj ∈ {0,1}", fontsize=8, color=C_FAC,
            ha="center", style="italic")

    plt.tight_layout()
    return fig


# ── Navigation ────────────────────────────────────────────────────────────────

tab_submit, tab_leaderboard, tab_problem = st.tabs([
    "📤 Submit Solution", "🏆 Leaderboard", "📋 Problem Description"
])


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1 — SUBMIT
# ═══════════════════════════════════════════════════════════════════════════════

with tab_submit:
    st.header("Submit Your Solution")

    # ── Student information ───────────────────────────────────────────────────
    col_id, col_name = st.columns(2)
    with col_id:
        student_id = st.text_input(
            "Student ID *",
            placeholder="e.g. 2021123456",
            max_chars=20,
        ).strip()
    with col_name:
        student_name = st.text_input(
            "Student Name *",
            placeholder="e.g. Kim Minjun",
            max_chars=50,
        ).strip()

    # ── File upload ───────────────────────────────────────────────────────────
    uploaded = st.file_uploader(
        "Upload decision-variable CSV *",
        type=["csv"],
        help="Two columns: 'variable' and 'value'. See the Problem tab for format.",
    )

    submit_btn = st.button("🚀 Submit", type="primary", use_container_width=True)

    if submit_btn:
        # ── Input validation ──────────────────────────────────────────────────
        input_errors = []
        if not student_id:
            input_errors.append("Student ID is required.")
        if not student_name:
            input_errors.append("Student Name is required.")
        if uploaded is None:
            input_errors.append("Please upload a CSV file.")

        if input_errors:
            for e in input_errors:
                st.error(e)
            st.stop()

        # ── Save raw CSV text ─────────────────────────────────────────────────
        raw_bytes = uploaded.read()
        raw_csv   = raw_bytes.decode("utf-8-sig", errors="replace")
        uploaded.seek(0)  # reset for parser

        # ── Pipeline ──────────────────────────────────────────────────────────
        with st.spinner("Parsing and evaluating your submission…"):

            # Step 1 — Parse
            ok, parse_errors, solution = csv_parser.parse_csv(uploaded)

            if not ok:
                st.error("### ❌ CSV Parse Error")
                for e in parse_errors:
                    st.error(e)
                st.stop()

            if parse_errors:  # warnings only
                for w in parse_errors:
                    st.warning(w)

            # Step 2 — Feasibility
            feas_result = feas_mod.check_feasibility(solution)

            # Step 3 — Objective
            obj_result = scoring_mod.compute_objective(solution)

            # Step 4 — Score
            score_result = scoring_mod.compute_score(obj_result, feas_result)

            # Step 5 — Persist
            submission_id = db.save_submission(
                student_id   = student_id,
                student_name = student_name,
                score_result = score_result,
                obj_result   = obj_result,
                feas_result  = feas_result,
                raw_csv      = raw_csv,
            )

            rank, total = db.get_rank(student_id)

        # ── Results display ────────────────────────────────────────────────────
        st.markdown("---")
        st.subheader("📊 Submission Results")

        # Score + rank highlight
        c1, c2, c3 = st.columns(3)
        sc = score_result["score"]
        c1.metric("Final Score", f"{sc:,} / 10,000")
        c2.metric("Feasibility", feasibility_badge(feas_result["is_feasible"]))
        c3.metric(
            "Leaderboard Rank",
            f"#{rank} of {total}" if rank else "N/A",
        )

        # Objective breakdown
        st.markdown("#### Cost Breakdown")
        cost_df = pd.DataFrame([
            {"Component": "Fixed facility cost",          "Value": obj_result["fixed_cost"]},
            {"Component": "Transport: supplier→facility", "Value": obj_result["transport_cost_sf"]},
            {"Component": "Transport: facility→customer", "Value": obj_result["transport_cost_fc"]},
            {"Component": "**Total objective cost**",     "Value": obj_result["total_cost"]},
            {"Component": "Infeasibility penalty",        "Value": score_result["penalty"]},
            {"Component": "**Effective cost (scored)**",  "Value": score_result["effective_cost"]},
        ])
        st.dataframe(cost_df, use_container_width=True, hide_index=True)

        # Open facilities summary
        open_facs = [j for j, v in solution["y"].items() if v == 1]
        st.markdown(f"**Open facilities:** {', '.join(open_facs) if open_facs else 'None'}")

        # Feasibility violations
        if feas_result["violations"]:
            st.markdown("#### ⚠️ Constraint Violations")
            st.warning(
                f"{len(feas_result['violations'])} violation(s) found. "
                f"Total penalty: **{score_result['penalty']:,.0f}**"
            )
            viol_df = pd.DataFrame(feas_result["violations"])
            st.dataframe(viol_df, use_container_width=True, hide_index=True)
        else:
            st.success("All constraints satisfied — solution is feasible.")

        # History for this student
        history = db.get_student_history(student_id)
        if len(history) > 1:
            st.markdown("#### 📈 Your Submission History")
            hist_df = pd.DataFrame(history)
            hist_df = hist_df.rename(columns={
                "submitted_at":    "Time",
                "score":           "Score",
                "objective_value": "Obj. Cost",
                "penalty":         "Penalty",
                "is_feasible":     "Feasible",
                "violation_count": "Violations",
            })
            hist_df["Feasible"] = hist_df["Feasible"].map({1: "✅", 0: "❌"})
            st.dataframe(hist_df[["Time","Score","Obj. Cost","Penalty","Feasible","Violations"]],
                         use_container_width=True, hide_index=True)


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2 — LEADERBOARD
# ═══════════════════════════════════════════════════════════════════════════════

with tab_leaderboard:
    st.header("🏆 Leaderboard")
    st.caption("Showing each student's best submission. Refreshes on page reload.")

    if st.button("🔄 Refresh"):
        st.rerun()

    rows = db.get_leaderboard(top_n=50)

    if not rows:
        st.info("No submissions yet.")
    else:
        lb_df = pd.DataFrame(rows)
        lb_df = lb_df.rename(columns={
            "rank":           "Rank",
            "student_id":     "Student ID",
            "student_name":   "Name",
            "best_score":     "Best Score",
            "best_objective": "Best Obj. Cost",
            "best_feasible":  "Feasible",
            "attempts":       "Attempts",
            "best_at":        "Achieved At",
        })
        lb_df["Feasible"] = lb_df["Feasible"].map({1: "✅", 0: "❌"})

        # Highlight top 3
        def row_style(row):
            if row["Rank"] == 1:
                return ["background-color: #ffd700"] * len(row)
            if row["Rank"] == 2:
                return ["background-color: #c0c0c0"] * len(row)
            if row["Rank"] == 3:
                return ["background-color: #cd7f32"] * len(row)
            return [""] * len(row)

        st.dataframe(
            lb_df[["Rank","Student ID","Name","Best Score","Best Obj. Cost",
                   "Feasible","Attempts","Achieved At"]],
            use_container_width=True,
            hide_index=True,
        )

        st.markdown(f"**Total participants:** {len(rows)}")


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3 — PROBLEM DESCRIPTION
# ═══════════════════════════════════════════════════════════════════════════════

with tab_problem:
    st.header("📋 Problem Description")

    st.markdown("## Supply Chain Network Design")
    st.markdown("Design a distribution network to **minimise total cost** while satisfying all customer demands.")
    st.pyplot(draw_network(), use_container_width=True)
    st.markdown("---")
    st.markdown("""
### Sets

| Symbol | Elements |
|--------|----------|
| **S** (Suppliers)  | S1, S2 |
| **F** (Facilities) | F1, F2, F3 |
| **C** (Customers)  | C1, C2, C3, C4 |

---
### Decision Variables

| Variable | Type | Description |
|----------|------|-------------|
| `y_Fj` | Binary {0,1} | Open facility Fj (1=open, 0=closed) |
| `x_Si_Fj` | Real ≥ 0 | Flow from supplier Si to facility Fj |
| `x_Fj_Ck` | Real ≥ 0 | Flow from facility Fj to customer Ck |

---
### Objective (minimise)

```
Total Cost = Σ_j f[j]·y[j]                   (fixed opening cost)
           + Σ_{i,j} c_sf[i][j]·x_sf[i][j]   (supplier→facility transport)
           + Σ_{j,k} c_fc[j][k]·x_fc[j][k]   (facility→customer transport)
```

---
### Constraints

1. **Demand satisfaction**: each customer's demand must be fully met
2. **Flow balance**: inflow = outflow at every facility (single-period, no inventory)
3. **Facility capacity**: throughput ≤ capacity × y[j]
4. **Supply capacity**: total outflow per supplier ≤ its capacity

---
### Scoring

```
effective_cost = total_cost + infeasibility_penalty
score = min(10000, round(10000 × reference_cost / effective_cost))
```

A **perfectly feasible, optimal** solution earns **10,000 points**.
Infeasible constraints incur large per-unit penalties.

---
""")

    # Problem data tables
    p = PROBLEM

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("#### Demand")
        st.dataframe(
            pd.DataFrame(list(p["demand"].items()), columns=["Customer", "Demand"]),
            hide_index=True, use_container_width=True,
        )
        st.markdown("#### Supply Capacity")
        st.dataframe(
            pd.DataFrame(list(p["supply_capacity"].items()), columns=["Supplier","Capacity"]),
            hide_index=True, use_container_width=True,
        )

    with col_b:
        st.markdown("#### Facility Parameters")
        fac_data = [
            {
                "Facility": j,
                "Fixed Cost": p["facility_fixed_cost"][j],
                "Capacity": p["facility_capacity"][j],
            }
            for j in p["facilities"]
        ]
        st.dataframe(pd.DataFrame(fac_data), hide_index=True, use_container_width=True)

    st.markdown("#### Transport Cost: Supplier → Facility")
    sf_df = pd.DataFrame(p["cost_sf"]).T
    st.dataframe(sf_df, use_container_width=True)

    st.markdown("#### Transport Cost: Facility → Customer")
    fc_df = pd.DataFrame(p["cost_fc"]).T
    st.dataframe(fc_df, use_container_width=True)

    # ── CSV format guide ──────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### CSV Submission Format")
    st.markdown("""
Your CSV must have exactly **two columns**: `variable` and `value`.

**Variable naming:**
- `y_F1`, `y_F2`, `y_F3` — facility open decisions (**all three required**)
- `x_S1_F1`, `x_S2_F3`, … — supplier-to-facility flows
- `x_F1_C1`, `x_F3_C4`, … — facility-to-customer flows

Variables with value 0 may be omitted (they default to 0),
**except** all three `y_F*` rows which must always be present.
""")

    st.markdown("#### Example valid submission")
    example_csv = """\
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
x_F3_C4,90"""
    st.code(example_csv, language="csv")

    st.download_button(
        label="⬇️ Download example CSV",
        data=example_csv,
        file_name="example_submission.csv",
        mime="text/csv",
    )
