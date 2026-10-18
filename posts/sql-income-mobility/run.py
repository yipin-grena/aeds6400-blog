"""Generate a synthetic family panel, match with SQL, estimate and validate.

No real people or survey records are used. All monetary amounts are simulated
annual incomes in constant dollars. See README.md for the data generating model.
"""
import hashlib
import json
import platform
import sqlite3
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from tutorial import compare, ige, match

POST = Path(__file__).resolve().parent
DATA = POST / "data"
RESULTS = POST / "results"
SEED = 640006
N = 4000
BETA = 0.4
PARENT_SD = 0.6
CHILD_SD = 0.45


def generate():
    """One linked parent and adult child per family, with complete histories."""
    rng = np.random.default_rng(SEED)
    families = np.arange(1, N + 1)
    parent_id, child_id = 100000 + families, 200000 + families
    parent_status = rng.normal(0, 0.6, N)
    child_status = BETA * parent_status + rng.normal(0, 0.45, N)
    parent_log = np.log(60000) + parent_status
    child_log = np.log(65000) + child_status
    people = pd.concat([
        pd.DataFrame(dict(person_id=parent_id, family_id=families,
                          birth_year=1955, generation="parent")),
        pd.DataFrame(dict(person_id=child_id, family_id=families,
                          birth_year=1980, generation="child"))
    ], ignore_index=True)
    links = pd.DataFrame(dict(child_id=child_id, parent_id=parent_id,
                              family_id=families))
    panels = []
    for age in range(40, 45):
        shock = rng.normal(0, PARENT_SD, N)
        panels.append(pd.DataFrame(dict(
            person_id=parent_id, year=1955 + age,
            real_income=np.exp(parent_log + shock - PARENT_SD**2 / 2))))
    for age in range(25, 45):
        progress = min((age - 25) / 15, 1)
        loading = 0.45 + 0.55 * progress
        average_log = np.log(35000) + progress * np.log(65000 / 35000)
        shock = rng.normal(0, CHILD_SD, N)
        panels.append(pd.DataFrame(dict(
            person_id=child_id, year=1980 + age,
            real_income=np.exp(average_log + loading * child_status
                               + shock - CHILD_SD**2 / 2))))
    incomes = pd.concat(panels, ignore_index=True).sort_values(["person_id", "year"])
    latent = pd.DataFrame(dict(family_id=families, parent_id=parent_id,
                              child_id=child_id, parent_log=parent_log,
                              child_log=child_log))
    return people, links, incomes, latent


def write_database(people, links, incomes):
    """Build a new database with keys enforced before inserting records."""
    path = DATA / "mobility.sqlite"
    if path.exists():
        path.unlink()  # Only this generated local file is replaced.
    conn = sqlite3.connect(path)
    conn.executescript((POST / "sql/schema.sql").read_text())
    conn.executemany("INSERT INTO families VALUES (?)", [(i,) for i in range(1, N + 1)])
    conn.executemany("INSERT INTO people VALUES (?, ?, ?, ?)",
                     people.itertuples(index=False, name=None))
    conn.executemany("INSERT INTO links VALUES (?, ?, ?)",
                     links.itertuples(index=False, name=None))
    conn.executemany("INSERT INTO incomes VALUES (?, ?, ?)",
                     incomes.itertuples(index=False, name=None))
    conn.commit()
    return conn


def validate(conn, people, links, incomes):
    """Independently verify SQL means, relationships, samples and OLS."""
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert not conn.execute("PRAGMA foreign_key_check").fetchall()
    assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert people.person_id.is_unique
    assert not incomes.duplicated(["person_id", "year"]).any()
    assert links.child_id.is_unique and links.family_id.is_unique
    assert np.isfinite(incomes.real_income).all() and (incomes.real_income > 0).all()

    audit = pd.read_sql_query("""
        SELECT l.child_id, p.person_id AS found_parent, c.person_id AS found_child,
               p.generation AS parent_role, c.generation AS child_role,
               c.birth_year - p.birth_year AS birth_gap
        FROM links AS l
        LEFT JOIN people AS p ON p.family_id = l.family_id AND p.person_id = l.parent_id
        LEFT JOIN people AS c ON c.family_id = l.family_id AND c.person_id = l.child_id
    """, conn)
    unmatched = int(audit[["found_parent", "found_child"]].isna().any(axis=1).sum())
    assert unmatched == 0 and len(audit) == N
    assert (audit.parent_role == "parent").all() and (audit.child_role == "child").all()
    assert (audit.birth_gap == 25).all()

    panel = incomes.merge(people, on="person_id", validate="many_to_one")
    panel["age"] = panel.year - panel.birth_year
    specifications = [((40, 40), (40, 40)), ((40, 44), (40, 44)),
                      ((40, 44), (25, 29))]
    specifications += [((40, 44), (age, age)) for age in range(25, 45)]
    maximum_error = 0.0
    for parent_ages, child_ages in specifications:
        sql_pairs = match(conn, parent_ages, child_ages)
        expected = links.sort_values("child_id").copy()
        for role, ages in [("parent", parent_ages), ("child", child_ages)]:
            part = panel[(panel.generation == role) & panel.age.between(*ages)]
            counts = part.groupby("person_id").size()
            assert (counts == ages[1] - ages[0] + 1).all() and len(counts) == N
            means = part.groupby("person_id").real_income.mean()
            expected[role + "_income"] = expected[role + "_id"].map(means)
        expected = expected[sql_pairs.columns].reset_index(drop=True)
        assert len(sql_pairs) == N and sql_pairs.child_id.is_unique
        pd.testing.assert_frame_equal(sql_pairs, expected, check_exact=False,
                                      rtol=1e-12, atol=1e-8)
        for column in ("parent_income", "child_income"):
            relative = np.abs((sql_pairs[column] - expected[column]) / expected[column])
            maximum_error = max(maximum_error, float(relative.max()))
        x, y = np.log(expected.parent_income), np.log(expected.child_income)
        manual_slope = ((x - x.mean()) * (y - y.mean())).sum() / ((x - x.mean())**2).sum()
        assert np.isclose(ige(sql_pairs), manual_slope, rtol=1e-12)
    # Without temporary shocks, the age loading alone scales the latent slope.
    latent = pd.read_csv(DATA / "latent-status.csv")
    x = latent.parent_log.to_numpy()
    centered_child = latent.child_log.to_numpy() - np.log(65000)
    X = np.column_stack([np.ones(N), x])
    mature = np.linalg.lstsq(X, centered_child, rcond=None)[0][1]
    young = np.linalg.lstsq(X, 0.45 * centered_child, rcond=None)[0][1]
    assert np.isclose(young, 0.45 * mature, rtol=1e-12)
    return dict(families=N, people=len(people), income_records=len(incomes),
                unmatched_links=unmatched, specifications_checked=len(specifications),
                max_relative_mean_error=maximum_error,
                sql_means_match_pandas=True, slopes_match_covariance_formula=True,
                same_pair_ids=True, no_shock_lifecycle_control=True)


def make_figures(estimates, ages):
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11,
                         "axes.spines.top": False, "axes.spines.right": False,
                         "axes.spines.left": False, "axes.edgecolor": "#b7c4ca",
                         "text.color": "#203b45", "axes.labelcolor": "#203b45",
                         "xtick.color": "#49626b", "ytick.color": "#49626b",
                         "figure.facecolor": "#fffefa", "axes.facecolor": "#fffefa"})
    fig, ax = plt.subplots(figsize=(9.3, 4.7))
    fig.subplots_adjust(left=.28, right=.94, bottom=.2, top=.74)
    fig.text(.04, .94, "Averaging brings the estimate closer to the known relationship",
             fontsize=14, weight="bold", va="top")
    fig.text(.04, .85, "Simulated families | Both generations measured at age 40 or ages 40 to 44",
             fontsize=10, color="#536b73")
    values = estimates.ige.iloc[:2].to_numpy()
    ax.barh([1, 0], values, color=["#a9b8be", "#267780"], height=.4)
    for y, v in zip([1, 0], values):
        ax.text(v + .009, y, f"{v:.3f}", va="center", fontsize=12, weight="bold")
    ax.set_yticks([1, 0], ["One year", "Five year average"])
    ax.tick_params(axis="y", length=0, pad=12)
    ax.set_xlim(0, .47)
    ax.set_ylim(-.55, 1.55)
    ax.set_xticks(np.arange(0, .5, .1))
    ax.set_xlabel("Estimated intergenerational elasticity", labelpad=10)
    ax.axvline(BETA, color="#be7732", linestyle=(0, (4, 3)), linewidth=1.6)
    ax.text(BETA, 1.5, f"Model value {BETA:.2f}", ha="center", va="bottom",
            color="#97602a", fontsize=10)
    ax.set_axisbelow(True)
    ax.grid(axis="x", color="#e4e8e8", linewidth=.7)
    fig.text(.04, .04, f"Same {N:,} pairs in both estimates. Smaller values suggest more mobility.",
             fontsize=10, color="#536b73")
    fig.savefig(RESULTS / "figures/income-averages.png", dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(9.3, 5.25))
    fig.subplots_adjust(left=.1, right=.94, bottom=.2, top=.76)
    fig.text(.04, .95, "Measuring children earlier makes mobility look stronger",
             fontsize=15, weight="bold", va="top")
    fig.text(.04, .86, "Simulated families | Parent income is always averaged over ages 40 to 44",
             fontsize=10, color="#536b73")
    ax.plot(ages.child_age, ages.ige, color="#267780", linewidth=2,
            marker="o", markersize=4)
    ax.axvspan(40, 44, color="#267780", alpha=.06)
    ax.axhline(BETA, color="#be7732", linestyle=(0, (4, 3)), linewidth=1.4)
    ax.text(44, BETA + .012, f"Model value {BETA:.2f}", ha="right", color="#97602a", fontsize=10)
    for age in [25, 40]:
        value = float(ages.loc[ages.child_age == age, "ige"].iloc[0])
        ax.annotate(f"{value:.3f}", (age, value), xytext=(0, 11),
                    textcoords="offset points", ha="center", fontsize=10, weight="bold")
    ax.set_xlim(24.5, 44.5)
    ax.set_ylim(0, .45)
    ax.set_xticks([25, 30, 35, 40, 44])
    ax.set_xlabel("Age when the child's single year of income is measured", labelpad=10)
    ax.set_ylabel("Estimated elasticity", labelpad=12)
    ax.set_axisbelow(True)
    ax.grid(axis="y", color="#e4e8e8", linewidth=.7)
    fig.text(.04, .04, "The age pattern is built into this teaching model. It is not a U.S. estimate.",
             fontsize=10, color="#536b73")
    fig.savefig(RESULTS / "figures/child-age.png", dpi=180)
    plt.close(fig)


def main():
    for path in (DATA, RESULTS / "tables", RESULTS / "figures"):
        path.mkdir(parents=True, exist_ok=True)
    people, links, incomes, latent = generate()
    for name, frame in [("people", people), ("links", links), ("incomes", incomes),
                        ("latent-status", latent)]:
        frame.to_csv(DATA / f"{name}.csv", index=False)
    conn = write_database(people, links, incomes)
    try:
        checks = validate(conn, people, links, incomes)
        estimates = compare(conn)
        estimates.to_csv(RESULTS / "tables/estimates.csv", index=False)
        ages = pd.DataFrame([dict(child_age=age, ige=ige(match(conn, (40, 44), (age, age))))
                             for age in range(25, 45)])
        ages.to_csv(RESULTS / "tables/child-age.csv", index=False)
        pairs = match(conn, (40, 44), (40, 44))
        pairs.to_csv(RESULTS / "tables/matched-pairs.csv", index=False)
        pairs.head(3).to_csv(RESULTS / "tables/example-pairs.csv", index=False)
        latent_slope = np.linalg.lstsq(
            np.column_stack([np.ones(N), latent.parent_log]), latent.child_log, rcond=None)[0][1]
        summary = dict(n=N, seed=SEED, true_ige=BETA, latent_sample_ige=float(latent_slope),
                       single=float(estimates.ige.iloc[0]), averaged=float(estimates.ige.iloc[1]),
                       young_average=float(estimates.ige.iloc[2]),
                       child25=float(ages.ige.iloc[0]), child40=float(ages.ige.iloc[15]))
        (RESULTS / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
        (RESULTS / "validation.json").write_text(json.dumps(checks, indent=2) + "\n")
        make_figures(estimates, ages)
        files = {str(p.relative_to(POST)): hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in sorted(DATA.glob("*.csv"))}
        (DATA / "provenance.json").write_text(json.dumps(dict(
            source="Synthetic teaching data generated by run.py; no real individuals",
            seed=SEED, families=N, sha256=files), indent=2) + "\n")
        (RESULTS / "environment.txt").write_text(
            f"Python {platform.python_version()}\nSQLite {sqlite3.sqlite_version}\n"
            f"numpy {np.__version__}\npandas {pd.__version__}\nmatplotlib {matplotlib.__version__}\n")
        print(estimates.to_string(index=False, float_format="%.3f"))
        print(f"Validated {checks['specifications_checked']} specifications and {N:,} matched pairs.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
