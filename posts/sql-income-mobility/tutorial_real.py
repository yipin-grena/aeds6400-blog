"""Run the article's main comparisons from two locally supplied workbooks.

Only aggregate estimates are printed. Normalized tables and matched records
remain in memory. Use real_analysis.py for the full saved tables and figures.
"""
from __future__ import annotations

# BEGIN setup
import argparse
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd

from real_analysis import (
    AGE_WINDOWS, POST, annual_cpi, check, load_memory_database, normalize,
    query_pairs, read_excel_local, read_waves, slope_and_cluster_se,
)


def setup_database(extract_path, fims_path):
    """Read both workbooks and load the four normalized tables into SQLite."""
    waves = read_waves(POST / "config/psid_waves.csv")
    cpi = annual_cpi(POST / "data/public/CPIAUCNS.csv")
    extract = read_excel_local(extract_path)
    fims = read_excel_local(fims_path)
    tables, _, _ = normalize(extract, fims, waves, cpi)
    return load_memory_database(tables)
# END setup


# BEGIN query
def compare(conn, args=None):
    """Estimate three comparisons using the article's final common sample."""
    if args is None:
        args = SimpleNamespace(birth_min=1960, birth_max=1978)
    matches = {ages: query_pairs(conn, ages, args) for ages in AGE_WINDOWS}
    common = matches[(40, 44)].index
    for pairs in matches.values():
        common = common.intersection(pairs.index)
    check(len(common) >= 100, "Fewer than 100 children match in all age windows.")
    mature = matches[(40, 44)].loc[common]
    positive_single = mature.parent_single.gt(0) & mature.child_single.gt(0)
    common = common[positive_single]
    check(len(common) >= 100, "Fewer than 100 children have positive single incomes.")
    mature = matches[(40, 44)].loc[common]
    groups = common.get_level_values("id68").to_numpy()
    models = {
        "one_year_each": (mature.parent_single, mature.child_single),
        "averaged_parent_one_year_child": (mature.parent_income, mature.child_single),
        "averaged_each_age40_44": (mature.parent_income, mature.child_income),
    }
    rows = []
    for measure, (parent, child) in models.items():
        parent, child = parent.to_numpy(), child.to_numpy()
        check(np.isfinite(parent).all() and np.isfinite(child).all()
              and (parent > 0).all() and (child > 0).all(),
              "Nonpositive or nonfinite regression inputs.")
        slope, se, clusters = slope_and_cluster_se(parent, child, groups)
        rows.append({"measure": measure, "children": len(common),
                     "origin_family_clusters": clusters, "ige": slope,
                     "cluster_se": se})
    return pd.DataFrame(rows)


def run_example(extract_path, fims_path):
    conn = setup_database(extract_path, fims_path)
    try:
        return compare(conn, SimpleNamespace(birth_min=1960, birth_max=1978))
    finally:
        conn.close()
# END query


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--extract", type=Path,
                        default=POST / "data/raw/J366591/J366591.xlsx")
    parser.add_argument("--fims", type=Path,
                        default=POST / "data/raw/fim16227_gid_BO_2_BAL.xlsx")
    args = parser.parse_args()
    estimates = run_example(args.extract, args.fims)
    print(estimates.to_string(index=False, float_format="%.3f"))


if __name__ == "__main__":
    main()
