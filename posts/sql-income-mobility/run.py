"""Generate a synthetic PSID-style family panel, match with SQL, estimate and validate.

No real people or survey records are used, and no PSID data are read. The
simplified table layout is inspired by the PSID's public documentation; every
value is simulated. All monetary amounts are annual family incomes in constant dollars.
See README.md for the data generating model.
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
N_FAMILIES = 4000
BETA = 0.4
PARENT_SD = 0.6
CHILD_SD = 0.45
TWO_PARENT_SHARE = 0.85
PARENT_YEARS = range(1990, 2000)   # covers every child's ages 15 to 19
CHILD_AGES = range(25, 45)
QUALIFYING = ("reference person", "spouse")


def interview_numbers(rng, count):
    """Draw distinct family interview numbers, valid for one survey year."""
    return rng.choice(np.arange(1, 30001), size=count, replace=False)


def generate():
    """Families with one or two linked parents and one to three adult children."""
    rng = np.random.default_rng(SEED)
    id68 = 1001 + np.arange(N_FAMILIES)
    two_parent = rng.random(N_FAMILIES) < TWO_PARENT_SHARE
    kids_per_family = rng.choice([1, 2, 3], size=N_FAMILIES, p=[.4, .4, .2])
    family_status = rng.normal(0, 0.6, N_FAMILIES)
    parent_log = np.log(60000) + family_status

    # Parents are original 1968 sample members. In two-parent families the
    # father is person 1 and reference person; the mother is person 2.
    father_birth = rng.integers(1940, 1956, N_FAMILIES)
    mother_birth = np.clip(father_birth + rng.integers(-3, 4, N_FAMILIES), 1940, 1955)
    people, links, person_years = [], [], []
    for f in range(N_FAMILIES):
        if two_parent[f]:
            parents = [(1, "male", father_birth[f], "F", 1, "reference person"),
                       (2, "female", mother_birth[f], "M", 2, "spouse")]
        else:
            parents = [(1, "female", mother_birth[f], "M", 1, "reference person")]
        for pn, sex, born, _, _, _ in parents:
            people.append((id68[f], pn, int(born), sex))
        for k in range(kids_per_family[f]):
            child_pn = 30 + k   # children born into the sample start at 030
            people.append((id68[f], child_pn, 0, ""))   # birth year and sex set below
            for parent_pn, _, _, parent_type, _, _ in parents:
                links.append((id68[f], child_pn, id68[f], parent_pn, parent_type))
    individuals = pd.DataFrame(people, columns=["id68", "pn", "birth_year", "sex"])
    parent_links = pd.DataFrame(links, columns=["child_id68", "child_pn", "parent_id68",
                                                "parent_pn", "parent_type"])
    is_child = individuals.pn >= 30
    n_children = int(is_child.sum())
    individuals.loc[is_child, "birth_year"] = rng.integers(1975, 1981, n_children)
    individuals.loc[is_child, "sex"] = rng.choice(["female", "male"], n_children)

    children = individuals[is_child].reset_index(drop=True).copy()
    family_index = (children.id68 - 1001).to_numpy()
    children["parent_log"] = parent_log[family_index]
    children["child_status"] = (BETA * family_status[family_index]
                                + rng.normal(0, 0.45, n_children))
    children["child_log"] = np.log(65000) + children.child_status
    # As adults, children head or join their own split-off families.
    children["own_sequence"] = rng.choice([1, 2], n_children)

    family_rows = []
    for year in PARENT_YEARS:
        numbers = interview_numbers(rng, N_FAMILIES)
        shock = rng.normal(0, PARENT_SD, N_FAMILIES)
        income = np.exp(parent_log + shock - PARENT_SD**2 / 2)
        family_rows.append(pd.DataFrame(dict(year=year, interview_number=numbers,
                                             family_income=income)))
        for f in range(N_FAMILIES):
            for pn, sequence, relation in ([(1, 1, "reference person"), (2, 2, "spouse")]
                                           if two_parent[f] else
                                           [(1, 1, "reference person")]):
                person_years.append((id68[f], pn, year, int(numbers[f]), sequence, relation))
    for year in range(2000, 2025):
        adults = children[(year - children.birth_year).isin(CHILD_AGES)]
        age = (year - adults.birth_year).to_numpy()
        progress = np.minimum((age - 25) / 15, 1)
        loading = 0.45 + 0.55 * progress
        average_log = np.log(35000) + progress * np.log(65000 / 35000)
        shock = rng.normal(0, CHILD_SD, len(adults))
        income = np.exp(average_log + loading * adults.child_status.to_numpy()
                        + shock - CHILD_SD**2 / 2)
        numbers = interview_numbers(rng, len(adults))
        family_rows.append(pd.DataFrame(dict(year=year, interview_number=numbers,
                                             family_income=income)))
        for row, number in zip(adults.itertuples(index=False), numbers):
            relation = "reference person" if row.own_sequence == 1 else "spouse"
            person_years.append((row.id68, row.pn, year, int(number),
                                 int(row.own_sequence), relation))
    family_years = pd.concat(family_rows, ignore_index=True).sort_values(
        ["year", "interview_number"]).reset_index(drop=True)
    individual_years = pd.DataFrame(person_years, columns=[
        "id68", "pn", "year", "interview_number", "sequence_number", "relation_to_rp"]
    ).sort_values(["id68", "pn", "year"]).reset_index(drop=True)
    latent = children[["id68", "pn", "parent_log", "child_log"]]
    return individuals, parent_links, family_years, individual_years, latent


def write_database(tables):
    """Build a new database with keys enforced before inserting records."""
    path = DATA / "mobility.sqlite"
    if path.exists():
        path.unlink()  # Only this generated local file is replaced.
    conn = sqlite3.connect(path)
    conn.executescript((POST / "sql/schema.sql").read_text())
    for name in ("individuals", "parent_links", "family_years", "individual_years"):
        frame = tables[name]
        marks = ", ".join("?" * frame.shape[1])
        conn.executemany(f"INSERT INTO {name} VALUES ({marks})",
                         frame.astype(object).itertuples(index=False, name=None))
    conn.commit()
    return conn


def expected_pairs(tables, parent_window, child_ages):
    """Rebuild the SQL match with pandas, as an independent check."""
    links, people = tables["parent_links"], tables["individuals"]
    years = tables["individual_years"].merge(
        tables["family_years"], on=["year", "interview_number"], validate="many_to_one")
    years = years[years.sequence_number.isin([1, 2]) & years.relation_to_rp.isin(QUALIFYING)]
    births = people.rename(columns={"id68": "child_id68", "pn": "child_pn"})[
        ["child_id68", "child_pn", "birth_year"]]
    parents = (links.merge(years, left_on=["parent_id68", "parent_pn"],
                           right_on=["id68", "pn"])
                    .merge(births, on=["child_id68", "child_pn"]))
    parents = parents[(parents.year - parents.birth_year).between(*parent_window)]
    parents = parents.drop_duplicates(["child_id68", "child_pn", "year", "interview_number"])
    p_years = parent_window[1] - parent_window[0] + 1
    grouped = parents.groupby(["child_id68", "child_pn"])
    counts = grouped.size()
    assert counts.eq(p_years).all() and grouped.year.nunique().eq(p_years).all()
    parent_income = grouped.family_income.mean().rename("parent_income")

    own = years.merge(people[["id68", "pn", "birth_year"]], on=["id68", "pn"])
    own = own[(own.year - own.birth_year).between(*child_ages)]
    own = own.merge(links[["child_id68", "child_pn"]].drop_duplicates(),
                    left_on=["id68", "pn"], right_on=["child_id68", "child_pn"])
    c_years = child_ages[1] - child_ages[0] + 1
    grouped = own.groupby(["child_id68", "child_pn"])
    assert grouped.size().eq(c_years).all()
    child_income = grouped.family_income.mean().rename("child_income")
    pairs = pd.concat([parent_income, child_income], axis=1, join="inner").reset_index()
    pairs = pairs.rename(columns={"child_id68": "id68", "child_pn": "pn"})
    return pairs.sort_values(["id68", "pn"]).reset_index(drop=True)


def validate(conn, tables):
    """Independently verify keys, links, SQL means, duplication and OLS."""
    people, links = tables["individuals"], tables["parent_links"]
    family_years, years = tables["family_years"], tables["individual_years"]
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert not conn.execute("PRAGMA foreign_key_check").fetchall()
    assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert not people.duplicated(["id68", "pn"]).any()
    assert not years.duplicated(["id68", "pn", "year"]).any()
    assert not family_years.duplicated(["year", "interview_number"]).any()
    assert np.isfinite(family_years.family_income).all()
    assert (family_years.family_income > 0).all()

    audit = pd.read_sql_query("""
        SELECT l.child_id68, l.child_pn, l.parent_type,
               p.sex AS parent_sex, c.birth_year - p.birth_year AS age_at_birth
        FROM parent_links AS l
        LEFT JOIN individuals AS p
          ON p.id68 = l.parent_id68 AND p.pn = l.parent_pn
        LEFT JOIN individuals AS c
          ON c.id68 = l.child_id68 AND c.pn = l.child_pn
    """, conn)
    assert audit.notna().all().all()
    assert ((audit.parent_type == "M") == (audit.parent_sex == "female")).all()
    assert audit.age_at_birth.between(18, 45).all()
    parents_per_child = links.groupby(["child_id68", "child_pn"]).size()
    assert parents_per_child.isin([1, 2]).all()
    n_children = len(parents_per_child)
    n_two_parent = int((parents_per_child == 2).sum())
    excluded_rows = int((~(years.sequence_number.isin([1, 2])
                           & years.relation_to_rp.isin(QUALIFYING))).sum())

    specifications = [((15, 15), (40, 40)), ((15, 19), (40, 44)), ((15, 19), (25, 29))]
    specifications += [((15, 19), (age, age)) for age in CHILD_AGES]
    maximum_error = 0.0
    for parent_window, child_ages in specifications:
        sql_pairs = match(conn, parent_window, child_ages)
        expected = expected_pairs(tables, parent_window, child_ages)
        assert len(sql_pairs) == n_children
        pd.testing.assert_frame_equal(sql_pairs, expected[sql_pairs.columns],
                                      check_exact=False, rtol=1e-12, atol=1e-8,
                                      check_dtype=False)
        for column in ("parent_income", "child_income"):
            relative = np.abs((sql_pairs[column] - expected[column]) / expected[column])
            maximum_error = max(maximum_error, float(relative.max()))
        x, y = np.log(expected.parent_income), np.log(expected.child_income)
        manual_slope = ((x - x.mean()) * (y - y.mean())).sum() / ((x - x.mean())**2).sum()
        assert np.isclose(ige(sql_pairs), manual_slope, rtol=1e-12)

    # Without DISTINCT, a mother row and a father row in the same family repeat
    # each family-year, so the completeness check drops every two-parent child.
    query = (POST / "sql/match.sql").read_text()
    assert query.count("SELECT DISTINCT") == 1
    naive = pd.read_sql_query(query.replace("SELECT DISTINCT", "SELECT"), conn,
                              params=dict(p_start=15, p_end=19, p_years=5,
                                          c_start=40, c_end=44, c_years=5))
    assert len(naive) == n_children - n_two_parent

    # Without temporary shocks, the age loading alone scales the latent slope.
    latent = tables["latent"]
    X = np.column_stack([np.ones(len(latent)), latent.parent_log])
    centered_child = latent.child_log.to_numpy() - np.log(65000)
    mature = np.linalg.lstsq(X, centered_child, rcond=None)[0][1]
    young = np.linalg.lstsq(X, 0.45 * centered_child, rcond=None)[0][1]
    assert np.isclose(young, 0.45 * mature, rtol=1e-12)
    return dict(families=N_FAMILIES, people=len(people), children=n_children,
                two_parent_children=n_two_parent, parent_links=len(links),
                individual_years=len(years), family_years=len(family_years),
                rows_removed_by_sequence_filter=excluded_rows,
                children_kept_without_distinct=len(naive),
                specifications_checked=len(specifications),
                max_relative_mean_error=maximum_error,
                sql_means_match_pandas=True, slopes_match_covariance_formula=True,
                same_children_in_every_comparison=True, no_shock_lifecycle_control=True)


def make_figures(estimates, ages, n_children):
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
    fig.text(.04, .85, "Simulated families | Parents: child aged 15, or 15 to 19 | "
             "Child: age 40, or 40 to 44", fontsize=10, color="#536b73")
    values = estimates.ige.iloc[:2].to_numpy()
    ax.barh([1, 0], values, color=["#a9b8be", "#267780"], height=.4)
    for y, v in zip([1, 0], values):
        ax.text(v + .009, y, f"{v:.3f}", va="center", fontsize=12, weight="bold")
    ax.set_yticks([1, 0], ["One year", "Five-year average"])
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
    fig.text(.04, .04, f"Same {n_children:,} children in both estimates. "
             "Smaller values suggest more mobility.", fontsize=10, color="#536b73")
    fig.savefig(RESULTS / "figures/income-averages.png", dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(9.3, 5.25))
    fig.subplots_adjust(left=.1, right=.94, bottom=.2, top=.76)
    fig.text(.04, .95, "Measuring children earlier makes mobility look stronger",
             fontsize=15, weight="bold", va="top")
    fig.text(.04, .86, "Simulated families | Parental income always averaged over "
             "the child's ages 15 to 19", fontsize=10, color="#536b73")
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
    individuals, links, family_years, individual_years, latent = generate()
    tables = dict(individuals=individuals, parent_links=links, family_years=family_years,
                  individual_years=individual_years, latent=latent)
    for name, frame in [("individuals", individuals), ("parent-links", links),
                        ("family-years", family_years), ("individual-years", individual_years),
                        ("latent-status", latent)]:
        frame.to_csv(DATA / f"{name}.csv", index=False)
    conn = write_database(tables)
    try:
        checks = validate(conn, tables)
        estimates = compare(conn)
        estimates.to_csv(RESULTS / "tables/estimates.csv", index=False)
        ages = pd.DataFrame([dict(child_age=age, ige=ige(match(conn, (15, 19), (age, age))))
                             for age in CHILD_AGES])
        ages.to_csv(RESULTS / "tables/child-age.csv", index=False)
        pairs = match(conn, (15, 19), (40, 44))
        pairs.to_csv(RESULTS / "tables/matched-pairs.csv", index=False)
        pairs.head(3).to_csv(RESULTS / "tables/example-pairs.csv", index=False)
        latent_slope = np.linalg.lstsq(
            np.column_stack([np.ones(len(latent)), latent.parent_log]),
            latent.child_log, rcond=None)[0][1]
        summary = dict(families=N_FAMILIES, children=checks["children"],
                       two_parent_children=checks["two_parent_children"],
                       kept_without_distinct=checks["children_kept_without_distinct"],
                       seed=SEED, true_ige=BETA, latent_sample_ige=float(latent_slope),
                       single=float(estimates.ige.iloc[0]), averaged=float(estimates.ige.iloc[1]),
                       young_average=float(estimates.ige.iloc[2]),
                       child25=float(ages.ige.iloc[0]), child40=float(ages.ige.iloc[15]))
        (RESULTS / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
        (RESULTS / "validation.json").write_text(json.dumps(checks, indent=2) + "\n")
        make_figures(estimates, ages, checks["children"])
        files = {str(p.relative_to(POST)): hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in sorted(DATA.glob("*.csv"))}
        (DATA / "provenance.json").write_text(json.dumps(dict(
            source=("Synthetic teaching data generated by run.py; no real individuals "
                    "and no PSID data. The simplified layout is inspired by PSID public documentation."),
            seed=SEED, families=N_FAMILIES, sha256=files), indent=2) + "\n")
        (RESULTS / "environment.txt").write_text(
            f"Python {platform.python_version()}\nSQLite {sqlite3.sqlite_version}\n"
            f"numpy {np.__version__}\npandas {pd.__version__}\nmatplotlib {matplotlib.__version__}\n")
        print(estimates.to_string(index=False, float_format="%.3f"))
        print(f"Validated {checks['specifications_checked']} specifications and "
              f"{checks['children']:,} matched children.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
