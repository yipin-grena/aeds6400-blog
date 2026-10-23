"""Analyze locally supplied PSID/FIMS extracts; save aggregate results only.

The four normalized tables and matched records exist only in memory. This
script does not render or publish the blog and does not modify either workbook.
See README-real.md for the sample, timing, income conventions and limitations.
"""
from __future__ import annotations

import argparse
import hashlib
from io import BytesIO
import json
from pathlib import Path
import platform
import re
import shutil
import sqlite3
import subprocess
import zipfile

import numpy as np
import pandas as pd

POST = Path(__file__).resolve().parent
KEY = ["id68", "pn"]
AGE_WINDOWS = [(25, 29), (30, 34), (35, 39), (40, 44)]


def check(condition, message):
    """Fail without printing individual records or identifier values."""
    if not condition:
        raise ValueError(message)


def read_excel_local(path):
    """Use pandas, repairing a legacy display attribute in memory if needed.

    Some PSID Excel exports spell syncVertical/syncHorizontal with an extra h.
    openpyxl rejects those attributes. Only these worksheet display attributes
    are removed, and only in an in-memory copy. Cell data are not rewritten.
    """
    try:
        return pd.read_excel(path, sheet_name="Data", engine="openpyxl")
    except TypeError as exc:
        if "unexpected keyword argument 'synch" not in str(exc):
            raise
    buffer = BytesIO()
    with zipfile.ZipFile(path) as source:
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_STORED) as target:
            for entry in source.infolist():
                data = source.read(entry.filename)
                if entry.filename.startswith("xl/worksheets/"):
                    data = re.sub(rb'\s+synch(?:Vertical|Horizontal)="[^"]*"', b"", data)
                target.writestr(entry.filename, data)
    buffer.seek(0)
    return pd.read_excel(buffer, sheet_name="Data", engine="openpyxl")


def annual_cpi(path):
    """Annual means of the 12 monthly, unadjusted CPI-U observations."""
    data = pd.read_csv(path)
    dates = pd.to_datetime(data.iloc[:, 0])
    values = pd.to_numeric(data["CPIAUCNS"], errors="raise")
    check(not dates.duplicated().any(), "Duplicate CPI dates.")
    grouped = pd.DataFrame({"year": dates.dt.year, "cpi": values}).groupby("year").cpi
    check(grouped.count().eq(12).all(), "CPI must have 12 observations in each year.")
    annual = grouped.mean()
    check((annual > 0).all() and 2022 in annual.index, "Invalid CPI base year.")
    return annual


def read_waves(path):
    waves = pd.read_csv(path)
    check(not waves.survey_year.duplicated().any(), "Duplicate waves in mapping.")
    check((waves.income_year == waves.survey_year - 1).all(), "Unexpected income timing.")
    return waves


def as_integer(frame, columns):
    for column in columns:
        values = pd.to_numeric(frame[column], errors="raise")
        check(values.notna().all() and (values % 1 == 0).all(),
              f"Missing or noninteger values in identifier/code column {column}.")
        frame[column] = values.astype("int64")


def normalize(extract, fims, waves, cpi):
    """Create four DataFrames with audited, explicit compound keys."""
    required = {"ER30001", "ER30002", "ER32000", "ER32006"}
    for name in ["interview", "sequence", "relation", "age", "income"]:
        required.update(waves[name])
    check(required.issubset(extract.columns), "Extract lacks mapped variables.")
    check({"ID68", "PN", "ID68P", "PNP", "PTYPE"}.issubset(fims.columns),
          "FIMS needs the long biological parent map columns.")
    as_integer(extract, ["ER30001", "ER30002"])
    check(not extract.duplicated(["ER30001", "ER30002"]).any(),
          "Combined PSID extract has duplicate person keys.")
    check((extract[["ER30001", "ER30002"]] > 0).all().all(), "Invalid person keys.")
    people = extract[["ER30001", "ER30002", "ER32000", "ER32006"]].rename(columns={
        "ER30001": "id68", "ER30002": "pn", "ER32000": "sex", "ER32006": "sample_member"})
    people["sex"] = people.sex.where(people.sex.isin([1, 2]))
    people["birth_year_proxy"] = pd.Series(pd.NA, index=people.index, dtype="Int64")
    person_frames, family_frames, flow = [], [], []
    for wave in waves.itertuples(index=False):
        data = extract[["ER30001", "ER30002", wave.interview, wave.sequence,
                        wave.relation, wave.age, wave.income]].rename(columns={
            "ER30001": "id68", "ER30002": "pn", wave.interview: "interview_number",
            wave.sequence: "sequence_number", wave.relation: "relation_code",
            wave.age: "age", wave.income: "family_income_nominal"}).copy()
        for col in data:
            data[col] = pd.to_numeric(data[col], errors="raise")
        current = (data.interview_number > 0) & data.sequence_number.between(1, 20)
        data = data.loc[current].copy()
        as_integer(data, KEY + ["interview_number", "sequence_number", "relation_code"])
        data["survey_year"] = wave.survey_year
        data["income_year"] = wave.income_year
        # In a combined individual-format extract the same family income repeats.
        # Check agreement BEFORE collapsing it to one family/year observation.
        conflicts = data.groupby("interview_number").family_income_nominal.nunique(dropna=False)
        check(conflicts.le(1).all(), f"Conflicting family incomes in wave {wave.survey_year}.")
        families = data[["survey_year", "income_year", "interview_number",
                         "family_income_nominal"]].drop_duplicates("interview_number").copy()
        values = families.family_income_nominal
        valid = values.between(wave.min_income, wave.max_income)
        # Before 1994, $1 combines true small amounts with zero/negative income.
        # It cannot be reconstructed. Keep it missing rather than call it $1.
        bottomcoded = (values == 1) & bool(wave.exclude_one)
        valid &= ~bottomcoded
        families["family_income"] = values.where(valid) * cpi.loc[2022] / cpi.loc[wave.income_year]
        families["family_income_nominal"] = values.where(valid)
        good_age = data.age.between(1, 125) & data.age.mod(1).eq(0)
        data["age"] = data.age.where(good_age).astype("Int64")
        data["income_age"] = data.age - 1  # Approximate age in the prior calendar year.
        rp = (data.sequence_number == 1) & (data.relation_code == wave.rp_code)
        partner = (data.sequence_number == 2) & data.relation_code.isin(
            [int(x) for x in str(wave.partner_codes).split(";")])
        data["is_reference_or_partner"] = (rp | partner).astype(int)
        person_frames.append(data[KEY + ["survey_year", "interview_number", "age", "income_age",
                                       "sequence_number", "relation_code", "is_reference_or_partner"]])
        family_frames.append(families)
        flow.append({"survey_year": wave.survey_year, "income_year": wave.income_year,
                     "current_members": len(data), "family_units": len(families),
                     "income_missing_or_out_of_range": int((~valid & ~bottomcoded).sum()),
                     "bottomcoded_income_excluded": int(bottomcoded.sum()),
                     "topcoded_income_retained_at_cap": int(values.eq(wave.topcode).sum()),
                     "valid_nonpositive_income": int((valid & values.le(0)).sum()),
                     "missing_person_age": int((~good_age).sum()), "conflicting_family_incomes": 0})
    person_years = pd.concat(person_frames, ignore_index=True)
    family_years = pd.concat(family_frames, ignore_index=True)
    check(not person_years.duplicated(KEY + ["survey_year"]).any(), "Duplicate person-years.")
    check(not family_years.duplicated(["survey_year", "interview_number"]).any(), "Duplicate family-years.")
    # Reported age lacks a birth month. The mode resolves adjacent possible years;
    # tie goes to earlier year. Window membership still uses each reported age.
    inferred = person_years.loc[person_years.age.notna(), KEY + ["survey_year", "age"]].copy()
    inferred["birth_year_proxy"] = inferred.survey_year - inferred.age
    counts = inferred.groupby(KEY + ["birth_year_proxy"]).size().rename("n").reset_index()
    modal = counts.sort_values(KEY + ["n", "birth_year_proxy"], ascending=[True, True, False, True])
    modal = modal.drop_duplicates(KEY)[KEY + ["birth_year_proxy"]]
    spread = inferred.groupby(KEY).birth_year_proxy.agg(lambda x: x.max() - x.min())
    people = people.drop(columns="birth_year_proxy").merge(modal, on=KEY, how="left", validate="one_to_one")
    people["birth_year_proxy"] = people.birth_year_proxy.astype("Int64")
    links = fims[["ID68", "PN", "ID68P", "PNP", "PTYPE"]].rename(columns={
        "ID68": "child_id68", "PN": "child_pn", "ID68P": "parent_id68",
        "PNP": "parent_pn", "PTYPE": "parent_type"}).copy()
    as_integer(links, ["child_id68", "child_pn", "parent_id68", "parent_pn"])
    links["parent_type"] = links.parent_type.astype(str).str.strip().str.upper()
    check(links.parent_type.isin(["M", "F"]).all(), "Unexpected FIMS parent type.")
    valid_keys = links[["child_id68", "child_pn", "parent_id68", "parent_pn"]].gt(0).all(axis=1)
    input_links = len(links)
    links = links.loc[valid_keys].drop_duplicates()
    check(not links.duplicated(["child_id68", "child_pn", "parent_type"]).any(),
          "Conflicting parent identifiers in FIMS.")
    check(~((links.child_id68 == links.parent_id68) & (links.child_pn == links.parent_pn)).any(),
          "FIMS self-parent link.")
    n_clean_links = len(links)
    links = links.merge(people[KEY].rename(columns={"id68": "child_id68", "pn": "child_pn"}),
                        on=["child_id68", "child_pn"], validate="many_to_one")
    n_child_present = len(links)
    links = links.merge(people[KEY].rename(columns={"id68": "parent_id68", "pn": "parent_pn"}),
                        on=["parent_id68", "parent_pn"], validate="many_to_one")
    audits = {"extract_people": len(people), "fims_rows": input_links,
              "clean_unique_fims_links": n_clean_links,
              "fims_links_child_present": n_child_present, "fims_links_both_people_present": len(links),
              "children_with_parent_link": len(links[["child_id68", "child_pn"]].drop_duplicates()),
              "people_with_birth_proxy_spread_over_two_years": int(spread.gt(2).sum()),
              "family_income_conflicts": 0, "duplicate_person_years": 0,
              "duplicate_family_years": 0}
    tables = {"people": people, "parent_links": links,
              "person_years": person_years, "family_years": family_years}
    return tables, pd.DataFrame(flow), audits


def load_memory_database(tables):
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA temp_store = MEMORY")
    conn.executescript((POST / "sql/schema_real.sql").read_text())
    for name in ["people", "parent_links", "family_years", "person_years"]:
        tables[name].to_sql(name, conn, if_exists="append", index=False, chunksize=5000)
    check(not conn.execute("PRAGMA foreign_key_check").fetchall(), "SQLite foreign key check failed.")
    return conn


def query_pairs(conn, age_window, args):
    start, end = age_window
    params = {"birth_min": args.birth_min, "birth_max": args.birth_max,
              "p_start": 15, "p_end": 19, "p_min_obs": 3, "p_midpoint": 17,
              "c_start": start, "c_end": end, "c_min_obs": 2, "c_midpoint": (start + end) // 2}
    pairs = pd.read_sql_query((POST / "sql/match_real.sql").read_text(), conn, params=params)
    check(not pairs.duplicated(KEY).any(), "SQL returned duplicate children.")
    return pairs.set_index(KEY).sort_index()


def slope_and_cluster_se(parent, child, groups, controls=None):
    x, y = np.log(parent), np.log(child)
    X = np.column_stack([np.ones(len(x)), x])
    if controls is not None:
        X = np.column_stack([X, controls])
    check(np.linalg.matrix_rank(X) == X.shape[1], "Regression design is rank deficient.")
    beta = np.linalg.lstsq(X, y, rcond=None)[0]
    residual = y - X @ beta
    codes, labels = pd.factorize(groups)
    G, N, K = len(labels), len(y), X.shape[1]
    check(G > 1 and N > K, "Insufficient observations or clusters.")
    scores = np.zeros((G, K))
    np.add.at(scores, codes, X * residual[:, None])
    bread = np.linalg.inv(X.T @ X)
    variance = (G / (G - 1)) * ((N - 1) / (N - K)) * bread @ (scores.T @ scores) @ bread
    # Independent scalar covariance identity cross-checks the simple OLS slope.
    if controls is None:
        independent = np.sum((x - x.mean()) * (y - y.mean())) / np.sum((x - x.mean()) ** 2)
        check(np.isclose(beta[1], independent, rtol=1e-11), "OLS cross-check failed.")
    return float(beta[1]), float(np.sqrt(max(variance[1, 1], 0))), G


def bootstrap_slopes(models, groups, repetitions, seed=6400):
    """Resample origin families; the same draw is used for every specification."""
    codes, labels = pd.factorize(groups)
    G = len(labels)
    sufficient = []
    for parent, child in models.values():
        x, y = np.log(parent), np.log(child)
        stats = np.column_stack([np.ones(len(x)), x, y, x*x, x*y])
        sums = np.zeros((G, 5)); np.add.at(sums, codes, stats)
        sufficient.append(sums)
    rng = np.random.default_rng(seed)
    draws = np.empty((repetitions, len(models)))
    for b in range(repetitions):
        weights = np.bincount(rng.integers(0, G, G), minlength=G)
        for j, sums in enumerate(sufficient):
            n, sx, sy, sxx, sxy = weights @ sums
            draws[b, j] = (sxy - sx*sy/n) / (sxx - sx*sx/n)
    check(np.isfinite(draws).all(), "Nonfinite cluster bootstrap draws.")
    return draws


def covariate_counts(metadata):
    """Save sample composition as counts without person-level output."""
    return {"children": len(metadata),
            "birth_year_proxy_nonmissing": int(metadata.birth_year_proxy.notna().sum()),
            "sex_known": int(metadata.sex.isin([1, 2]).sum()),
            "sex_missing": int(metadata.sex.isna().sum()),
            "female_children": int(metadata.sex.eq(2).sum())}


def model_controls(metadata):
    controls = np.column_stack([metadata.birth_year_proxy.to_numpy(dtype=float) - 1969,
                                metadata.sex.eq(2).to_numpy(dtype=float)])
    if metadata.sex.isna().any():
        controls = np.column_stack([controls, metadata.sex.isna().to_numpy(dtype=float)])
    return controls


def lifecycle_outputs(selected, metadata, repetitions):
    """Compare one observation near each midpoint on identical positive cases.

    The earlier averaged-window comparison is retained as a sensitivity on
    this exact sample. All eight models share the same origin-family draws.
    """
    check(not metadata.index.duplicated().any(), "Duplicate lifecycle metadata keys.")
    aligned = {}
    valid = pd.Series(True, index=metadata.index)
    parent_reference = None
    for ages in AGE_WINDOWS:
        pairs = selected[ages]
        check(not pairs.index.duplicated().any(), "Duplicate lifecycle child keys.")
        check(metadata.index.isin(pairs.index).all(), "Lifecycle window lacks a common child.")
        pairs = pairs.loc[metadata.index]
        aligned[ages] = pairs
        if parent_reference is None:
            parent_reference = pairs.parent_income
        else:
            check(np.allclose(pairs.parent_income, parent_reference),
                  "Lifecycle windows use different parental income.")
        valid &= pairs.child_single.gt(0) & np.isfinite(pairs.child_single)
    common = metadata.index[valid]
    check(len(common) >= 100, "Fewer than 100 common children have positive single observations at every age.")
    people = metadata.loc[common]
    groups = common.get_level_values("id68").to_numpy()
    parent = aligned[(40, 44)].loc[common].parent_income.to_numpy()
    check(np.isfinite(parent).all() and (parent > 0).all(), "Invalid lifecycle parental averages.")
    models = {}
    for kind, column in [("single", "child_single"), ("average", "child_income")]:
        for ages in AGE_WINDOWS:
            child = aligned[ages].loc[common, column].to_numpy()
            check(np.isfinite(child).all() and (child > 0).all(), "Invalid lifecycle regression inputs.")
            models[f"child_{kind}_age{ages[0]}_{ages[1]}"] = (parent, child)
    draws = bootstrap_slopes(models, groups, repetitions)
    controls = model_controls(people)
    rows = []
    for j, (label, (x, y)) in enumerate(models.items()):
        slope, se, clusters = slope_and_cluster_se(x, y, groups)
        adjusted, adjusted_se, _ = slope_and_cluster_se(x, y, groups, controls)
        low, high = np.quantile(draws[:, j], [0.025, 0.975])
        rows.append({"measure": label, "children": len(common), "origin_family_clusters": clusters,
                     "ige": slope, "cluster_se": se, "ci_lower": low, "ci_upper": high,
                     "cohort_sex_adjusted_ige": adjusted, "cohort_sex_adjusted_cluster_se": adjusted_se})
    all_estimates = pd.DataFrame(rows)
    labels = list(models)
    comparisons = [("child_single_age40_44", "child_single_age25_29"),
                   ("child_average_age40_44", "child_average_age25_29")]
    comparisons.extend((f"child_average_age{a}_{b}", f"child_single_age{a}_{b}")
                       for a, b in AGE_WINDOWS)
    contrasts = []
    for after, before in comparisons:
        i, j = labels.index(after), labels.index(before)
        low, high = np.quantile(draws[:, i] - draws[:, j], [0.025, 0.975])
        contrasts.append({"comparison": f"{after} minus {before}",
                          "ige_difference": rows[i]["ige"] - rows[j]["ige"],
                          "ci_lower": low, "ci_upper": high})
    coverage = []
    for (start, end), frame in aligned.items():
        pairs = frame.loc[common]
        coverage.append({"age_start": start, "age_end": end, "children": len(common),
                         "min_selected_age": int(pairs.child_single_age.min()),
                         "mean_selected_age": float(pairs.child_single_age.mean()),
                         "max_selected_age": int(pairs.child_single_age.max()),
                         "first_income_year": int(pairs.child_single_year.min()),
                         "last_income_year": int(pairs.child_single_year.max())})
    frames = {"lifecycle-estimates": all_estimates.iloc[:4].reset_index(drop=True),
              "lifecycle-averages": all_estimates.iloc[4:].reset_index(drop=True),
              "lifecycle-contrasts": pd.DataFrame(contrasts),
              "lifecycle-coverage": pd.DataFrame(coverage)}
    audit = {"base_children": len(metadata), "children": len(common),
             "excluded_single_incomes": int((~valid).sum()),
             "origin_family_clusters": int(pd.Index(groups).nunique()),
             "covariates": covariate_counts(people)}
    return frames, audit


def analyze(conn, tables, args):
    matches = {ages: query_pairs(conn, ages, args) for ages in AGE_WINDOWS}
    counts = [{"stage": f"Matched positive averages, child ages {a} to {b}", "children": len(v)}
              for (a, b), v in matches.items()]
    common = matches[(40, 44)].index
    for pairs in matches.values():
        common = common.intersection(pairs.index)
    check(len(common) >= 100, "Fewer than 100 common children; inspect aggregate matching losses.")
    mature = matches[(40, 44)].loc[common]
    positive_single = mature.parent_single.gt(0) & mature.child_single.gt(0)
    counts.append({"stage": "Same children observed in all four adult age windows", "children": len(common)})
    common = common[positive_single]
    check(len(common) >= 100, "Fewer than 100 children have positive single-year incomes.")
    counts.append({"stage": "Final common sample with positive single-year incomes", "children": len(common)})
    selected = {ages: pairs.loc[common] for ages, pairs in matches.items()}
    mature = selected[(40, 44)]
    for pairs in selected.values():
        check(pairs.index.equals(mature.index), "Comparisons must use identical children.")
        check(np.allclose(pairs.parent_income, mature.parent_income), "Parent measure differs across ages.")
    groups = common.get_level_values("id68").to_numpy()
    p = mature.parent_income.to_numpy()
    models = {
        "one_year_each": (mature.parent_single.to_numpy(), mature.child_single.to_numpy()),
        "averaged_parent_one_year_child": (p, mature.child_single.to_numpy()),
        "averaged_each_age40_44": (p, mature.child_income.to_numpy()),
    }
    for ages in AGE_WINDOWS[:-1]:
        models[f"averaged_each_age{ages[0]}_{ages[1]}"] = (p, selected[ages].child_income.to_numpy())
    for x, y in models.values():
        check(np.isfinite(x).all() and np.isfinite(y).all() and (x > 0).all() and (y > 0).all(),
              "Nonpositive or nonfinite regression inputs.")
    draws = bootstrap_slopes(models, groups, args.bootstrap)
    metadata = tables["people"].set_index(KEY).loc[common]
    age_records = tables["person_years"].set_index(KEY).loc[common].reset_index()
    age_records["implied_birth"] = age_records.survey_year - age_records.age
    age_spread = age_records.groupby(KEY).implied_birth.agg(lambda x: x.max() - x.min()).reindex(common)
    stable_ages = age_spread.le(2).to_numpy()
    counts.append({"stage": "Common sample with implied birth years no more than two years apart",
                   "children": int(stable_ages.sum())})
    # Explicit missing-sex indicator keeps the sensitivity on exactly the same people.
    controls = model_controls(metadata)
    rows, sensitivity = [], []
    for j, (label, (parent, child)) in enumerate(models.items()):
        slope, se, clusters = slope_and_cluster_se(parent, child, groups)
        adjusted, adjusted_se, _ = slope_and_cluster_se(parent, child, groups, controls)
        low, high = np.quantile(draws[:, j], [0.025, 0.975])
        rows.append({"measure": label, "children": len(common), "origin_family_clusters": clusters,
                     "ige": slope, "cluster_se": se, "ci_lower": low, "ci_upper": high,
                     "cohort_sex_adjusted_ige": adjusted, "cohort_sex_adjusted_cluster_se": adjusted_se})
        if stable_ages.sum() >= 100:
            age_slope, age_se, age_clusters = slope_and_cluster_se(
                parent[stable_ages], child[stable_ages], groups[stable_ages])
            sensitivity.append({"restriction": "Implied birth-year spread at most two years",
                                "measure": label, "children": int(stable_ages.sum()),
                                "origin_family_clusters": age_clusters, "ige": age_slope,
                                "cluster_se": age_se})
    labels = list(models)
    contrasts = []
    for after, before in [("averaged_parent_one_year_child", "one_year_each"),
                          ("averaged_each_age40_44", "one_year_each"),
                          ("averaged_each_age40_44", "averaged_each_age25_29")]:
        i, j = labels.index(after), labels.index(before)
        low, high = np.quantile(draws[:, i] - draws[:, j], [0.025, 0.975])
        contrasts.append({"comparison": f"{after} minus {before}",
                          "ige_difference": rows[i]["ige"] - rows[j]["ige"],
                          "ci_lower": low, "ci_upper": high})
    coverage = []
    for ages, pairs in selected.items():
        for prefix in ["parent", "child"]:
            if prefix == "parent" and ages != (40, 44):
                continue
            coverage.append({"measure": "parent_15_19" if prefix == "parent" else f"child_{ages[0]}_{ages[1]}",
                             "children": len(pairs), "min_observations": int(pairs[f"{prefix}_n"].min()),
                             "median_observations": float(pairs[f"{prefix}_n"].median()),
                             "max_observations": int(pairs[f"{prefix}_n"].max()),
                             "mean_measurement_age": float(pairs[f"{prefix}_mean_age"].mean()),
                             "mean_single_measurement_age": float(pairs[f"{prefix}_single_age"].mean()),
                             "earliest_income_year": int(pairs[f"{prefix}_first_year"].min()),
                             "latest_income_year": int(pairs[f"{prefix}_last_year"].max())})
    lifecycle_frames, lifecycle_audit = lifecycle_outputs(selected, metadata, args.bootstrap)
    counts.append({"stage": "Positive single child income in all four age windows",
                   "children": lifecycle_audit["children"]})
    return (pd.DataFrame(rows), pd.DataFrame(contrasts), pd.DataFrame(counts),
            pd.DataFrame(coverage), pd.DataFrame(sensitivity, columns=[
                "restriction", "measure", "children", "origin_family_clusters", "ige", "cluster_se"]),
            lifecycle_frames, lifecycle_audit, covariate_counts(metadata))




def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()




def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--extract", type=Path, default=POST / "data/raw/J366591/J366591.xlsx")
    parser.add_argument("--fims", type=Path, default=POST / "data/raw/fim16227_gid_BO_2_BAL.xlsx")
    parser.add_argument("--birth-min", type=int, default=1960)
    parser.add_argument("--birth-max", type=int, default=1978)
    parser.add_argument("--bootstrap", type=int, default=1000)
    parser.add_argument("--output", type=Path, default=POST / "results/real")
    parser.add_argument("--no-figures", action="store_true", help="Save aggregate tables and report without plotting.")
    parser.add_argument("--rscript", default="Rscript", help="Rscript executable for aggregate figures and report.")
    args = parser.parse_args()
    check(args.birth_min <= args.birth_max, "Invalid cohort range.")
    check(args.bootstrap >= 200, "Use at least 200 bootstrap repetitions.")
    rscript = shutil.which(args.rscript)
    if rscript is None and args.rscript == "Rscript":
        candidate = Path("/usr/local/bin/Rscript")
        rscript = str(candidate) if candidate.is_file() else None
    check(rscript is not None, "Rscript was not found; install R or supply --rscript /path/to/Rscript.")
    waves = read_waves(POST / "config/psid_waves.csv")
    cpi_path = POST / "data/public/CPIAUCNS.csv"
    cpi = annual_cpi(cpi_path)
    print("Reading the two local workbooks; individual records are not displayed.", flush=True)
    fims = read_excel_local(args.fims)
    extract = read_excel_local(args.extract)
    print("Building and validating the four tables in memory.", flush=True)
    tables, wave_flow, audit = normalize(extract, fims, waves, cpi)
    del extract, fims
    print("Matching with SQL and estimating on the common sample.", flush=True)
    conn = load_memory_database(tables)
    try:
        (estimates, contrasts, sample_flow, coverage, sensitivity,
         lifecycle_frames, lifecycle_audit, main_covariates) = analyze(conn, tables, args)
    finally:
        conn.close()
    for name, frame in tables.items(): audit[f"{name}_rows"] = len(frame)
    del tables
    args.output.mkdir(parents=True, exist_ok=True)
    frames = {"estimates": estimates, "contrasts": contrasts, "sample-flow": sample_flow,
              "coverage": coverage, "wave-validation": wave_flow, "age-quality-sensitivity": sensitivity,
              **lifecycle_frames}
    for name, frame in frames.items():
        frame.to_csv(args.output / f"{name}.csv", index=False)
    report = {"data_kind": "real PSID public-use extract and FIMS biological parent map",
              "source_files": {args.extract.name: sha256(args.extract), args.fims.name: sha256(args.fims)},
              "cpi_sha256": sha256(cpi_path), "cpi_series": "CPIAUCNS",
              "birth_year_proxy_min": args.birth_min, "birth_year_proxy_max": args.birth_max,
              "parent_income_ages": [15, 19], "parent_min_observations": 3,
              "child_min_observations": 2, "age_windows": AGE_WINDOWS,
              "dollar_base_year": 2022, "weighting": "unweighted; no survey weight supplied",
              "bootstrap_repetitions": args.bootstrap, "bootstrap_seed": 6400,
              "cluster": "child 1968 family identifier", "validation": audit,
              "lifecycle": lifecycle_audit,
              "covariates": {"main": main_covariates, "lifecycle": lifecycle_audit["covariates"]},
              "python": platform.python_version(), "pandas": pd.__version__, "numpy": np.__version__,
              "sqlite": sqlite3.sqlite_version,
              "checks": {"common_sample_across_specifications": True,
                         "positive_finite_regression_inputs": True,
                         "simple_ols_independently_verified": True,
                         "foreign_keys_valid": True,
                         "respondent_level_outputs_saved": False}}
    (args.output / "validation.json").write_text(json.dumps(report, indent=2) + "\n")
    command = [rscript, str(POST / "R/render-results.R"), "--output", str(args.output.resolve())]
    if args.no_figures:
        command.append("--no-figures")
    subprocess.run(command, check=True)
    print(estimates[["measure", "children", "ige", "ci_lower", "ci_upper"]].to_string(index=False), flush=True)
    print(lifecycle_frames["lifecycle-estimates"][["measure", "children", "ige", "ci_lower", "ci_upper"]]
          .to_string(index=False), flush=True)
    print(f"Aggregate results saved to {args.output}. No website was rendered or published.", flush=True)


if __name__ == "__main__":
    main()
