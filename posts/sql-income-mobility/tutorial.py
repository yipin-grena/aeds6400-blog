"""Run the tutorial against the database created by run.py."""
# BEGIN setup
from pathlib import Path
import sqlite3
import numpy as np
import pandas as pd

POST = Path(__file__).resolve().parent
query = (POST / "sql/match.sql").read_text()

def match(conn, parent_ages, child_ages):
    p0, p1 = parent_ages
    c0, c1 = child_ages
    params = dict(p_start=p0, p_end=p1, p_years=p1 - p0 + 1,
                  c_start=c0, c_end=c1, c_years=c1 - c0 + 1)
    return pd.read_sql_query(query, conn, params=params)
# END setup

# BEGIN estimate
def ige(pairs):
    x = np.log(pairs["parent_income"].to_numpy())
    y = np.log(pairs["child_income"].to_numpy())
    X = np.column_stack([np.ones(len(x)), x])
    intercept, slope = np.linalg.lstsq(X, y, rcond=None)[0]
    return float(slope)

def compare(conn):
    single = match(conn, (40, 40), (40, 40))
    averaged = match(conn, (40, 44), (40, 44))
    young = match(conn, (40, 44), (25, 29))
    for pairs in (single, averaged, young):
        assert pairs["child_id"].is_unique
        assert pairs["child_id"].equals(single["child_id"])
        assert (pairs[["parent_income", "child_income"]] > 0).all().all()
    return pd.DataFrame({
        "measure": ["Age 40 for both", "Ages 40 to 44 for both",
                    "Parent 40 to 44, child 25 to 29"],
        "pairs": [len(single), len(averaged), len(young)],
        "ige": [ige(single), ige(averaged), ige(young)]
    })

if __name__ == "__main__":
    with sqlite3.connect(POST / "data/mobility.sqlite") as conn:
        print(compare(conn).to_string(index=False, float_format="%.3f"))
# END estimate
