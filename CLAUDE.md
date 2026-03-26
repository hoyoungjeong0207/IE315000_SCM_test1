# SCM Optimization Competition Platform

Streamlit-based student competition platform for a university Supply Chain Management final project.

## Quick start

```bash
pip install -r requirements.txt
streamlit run app.py
```

## File map

| File | Purpose |
|------|---------|
| `app.py` | Streamlit UI — three tabs: Submit, Leaderboard, Problem |
| `config.py` | Problem instance data + scoring parameters (keep server-side) |
| `parser.py` | CSV ingestion, variable classification, domain checks |
| `feasibility.py` | Constraint checking, violation amounts, penalty computation |
| `scoring.py` | Objective value, final score formula |
| `db.py` | SQLite read/write; leaderboard query |
| `data/submissions.db` | Auto-created SQLite database |
| `sample/example_submission.csv` | Reference valid submission |

## Problem

Supply chain network design (facility opening + flow + inventory).

- **Sets**: 2 suppliers, 3 candidate facilities, 4 customers
- **Variables**: y (binary open), x_sf (supply flow), x_fc (demand flow), I (inventory)
- **Objective**: minimise fixed + transport + holding cost
- **Score**: `min(10000, round(10000 × reference_cost / effective_cost))`

## CSV schema

```
variable,value
y_F1,1          # required — facility open decision
y_F2,0
y_F3,1
x_S1_F1,200     # supplier→facility flow
x_F1_C1,80      # facility→customer flow
I_F1,0          # inventory (optional, defaults to 0)
```

## Key design rules

- Never execute student code — only CSV upload.
- Scoring logic lives entirely in `config.py` + `scoring.py` (hidden from students).
- Higher score = better. Infeasibility incurs large per-unit penalties.
- All three `y_F*` rows are required; other zero-valued rows may be omitted.
