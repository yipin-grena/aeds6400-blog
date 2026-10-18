# Blog Post 6

## How one year of income can mislead a study of mobility

This tutorial matches parents and children with SQL inside Python and asks how income measurement changes the estimated intergenerational elasticity. It uses a fully simulated panel so the underlying relationship is known.

**Published post:** https://yipin-grena.github.io/aeds6400-blog/posts/sql-income-mobility/

The article shows the matching query and explains the income comparisons. Expand the two Python examples to follow the query execution and estimation. The full runnable versions are `sql/match.sql` and `tutorial.py`; installation, database safeguards, and model details are documented below.

The post follows the Blog Post 6 prompt and the Class 12 SQL material. The prompt does not specify a dataset. No real people, surveys, administrative records, or U.S. mobility estimates are represented here. All income values are simulated in constant dollars, with no external data downloads or inflation adjustment needed. The simulation is an illustration of two measurement mechanisms, not evidence about their empirical size.

## Files

```text
sql-income-mobility/
├── index.qmd                   article with code read from the actual source files
├── README.md
├── requirements.txt           pinned analysis dependencies
├── run.py                     data generation, database, validation and figures
├── tutorial.py                SQL execution and regression shown in the article
├── build_preview.py           standalone local HTML preview
├── sql/
│   ├── schema.sql              tables, primary keys and foreign keys
│   └── match.sql               aggregate incomes, then match families
├── data/
│   ├── people.csv              one row per person
│   ├── links.csv               one row per parent and child relationship
│   ├── incomes.csv             one row per person and year
│   ├── latent-status.csv       hidden lasting income, for teaching checks only
│   ├── provenance.json         seed, source statement and CSV checksums
│   └── mobility.sqlite         generated locally, excluded from Git
├── results/
│   ├── tables/                estimates, age comparison and matched pairs
│   ├── figures/               two explanatory charts
│   ├── summary.json           numbers read by the article
│   ├── validation.json        checks actually run by run.py
│   └── environment.txt        Python, SQLite and package versions
└── preview/                   local review copy, excluded from Git
```

## Reproduce

Use Python 3.9 or later. From this post's folder, a clean environment can be created with

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python run.py
python tutorial.py
```

On Windows, activate with `.venv\Scripts\activate` instead. SQLite is included with Python. `run.py` regenerates the synthetic CSVs and database, validates all comparisons, and saves the tables, figures, and summary. It resolves paths relative to itself, so it can also be invoked from the repository root. `tutorial.py` runs the article's three comparisons on the generated database. No API key or network request is needed after installing packages.

To create the review copy, install Quarto, R, and the R packages `knitr` and `jsonlite`, then run

```sh
python build_preview.py
```

If Quarto is not on your path, supply `--quarto /path/to/quarto`. The script copies only this post's inputs into a temporary standalone project and writes `preview/Blog-Post-6.html`. It does not render the website or modify `docs/`; the published page is built with `quarto render` from the repository root. HTML uses the saved Python outputs; rerun `run.py` before rendering after changing the analysis. R only inserts generated values, figures and source code into the article. It performs no income analysis.

## Database and matching decisions

There are 4,000 independent families, 8,000 people and 100,000 annual income records. Each family has exactly one parent born in 1955 and one child born in 1980. The parent is observed at ages 40 through 44, in 1995 through 1999. The child is observed at ages 25 through 44, in 2005 through 2024. These dates are teaching choices, not a historical dataset.

`family_id` is a stable family of origin identifier, not the household in which someone currently lives. Globally unique `person_id` values follow individuals across years. `links` explicitly names the parent and child; shared family membership alone does not establish the relationship. Composite foreign keys require both people to belong to the named family. The schema also enforces a unique person and year income record. `families` provides the family key registry; its rows are generated from the IDs.

`match.sql` first aggregates each generation separately, grouping by family and person. Named parameters specify the inclusive age windows. `HAVING` requires the expected number of nonmissing annual incomes and distinct years. The final inner joins use both family and person IDs and produce one row per child. Generations are not joined on calendar year. Aggregation before matching avoids a many to many join of their annual records.

The analysis always uses one selected parent's individual income and the child's own adult income. It does not combine two parents' incomes or estimate household income mobility. All specifications use the same 4,000 pairs. Real panels can contain multiple parents and siblings, changing household IDs, attrition and incomplete windows. The relationship definition, income concept, inclusion rules and any clustered uncertainty calculation would need to be chosen for that dataset. This synthetic population is equally weighted; no survey weights apply.

## Simulation assumptions

The seed is `640006`; it was fixed before examining results. NumPy's default generator creates independent draws. For family i, define persistent parent status P with standard deviation 0.6, and an independent child component E with standard deviation 0.45. Both have mean zero and normal distributions. The lasting log incomes are

```text
parent_log = log(60000) + P
child_log  = log(65000) + 0.4 * P + E
```

The population elasticity is therefore 0.4. The slope realized in these 4,000 latent pairs is also reported in `results/summary.json` and may differ from 0.4 because E and P need not have exactly zero sample covariance. The latent values are used for validation and reference, never as a predictor in the reported matched income regressions.

Parent income at each age from 40 through 44 is `exp(parent_log + u - 0.6^2/2)`, where each u is independent normal noise with standard deviation 0.6. For children, let t increase linearly from zero at age 25 to one at age 40 and remain one afterward. Define

```text
age_loading = 0.45 + 0.55 * t
age_level   = log(35000) + t * log(65000 / 35000)
income      = exp(age_level + age_loading * (0.4 * P + E) + v - 0.45^2/2)
```

Each v is independent normal noise with standard deviation 0.45. Subtracting half the shock variance makes the multiplicative annual shock have mean one. At age 40 and above the expected child income equals `exp(child_log)`. Before 40, the loading compresses income gaps associated with lasting status. A common age profile alone would only change the intercept; it is the changing loading on centered status that generates the life cycle bias here. The parameters and maturity age illustrate mechanisms and are not fitted to Haider and Solon or any U.S. data.

Every income is positive and each window is complete by construction. Real data would require a documented treatment of zero, negative and missing incomes. Restricting a real sample to complete positive income histories can change the population being studied. The tutorial does not silently apply such a restriction to a survey.

## What the comparisons identify in this model

All estimates use ordinary least squares with an intercept, taking the natural log of the arithmetic average of annual real income amounts. Averaging logs would define a different income measure.

* Age 40 for both generations versus ages 40 through 44 for both isolates averaging after the child loading has reached one. Temporary error in parental income lowers the expected slope. Averaging reduces that error but does not remove it. Independent child income noise chiefly adds imprecision.
* The child age curve always uses the parent's ages 40 through 44 average. Only the age of the child's single observation changes, holding families and the parent measure fixed.
* Averaging the child's ages 25 through 29 leaves the early career loading below one. It reduces annual noise without solving the age mismatch.

The figures report estimates from one fixed simulated sample, not confidence intervals or empirical causal estimates. The dashed value 0.4 is the population simulation parameter. Finite sample variation and residual income noise explain why a five year average does not land exactly on it.

## Checks performed

`run.py` performs the following checks before saving figures.

* Database integrity and foreign key checks, unique person IDs and person and year observations, and positive finite incomes.
* A left join audit checks that each link finds both people, assigns their roles correctly and has the expected birth year gap. There are no unmatched links in this constructed panel.
* Each of 23 specifications is independently reconstructed using pandas grouping and ID mapping. Its SQL means must agree within the numeric tolerance in the code, with the same 4,000 child IDs and complete observation counts.
* Every regression slope is checked against the independent covariance divided by variance formula with an intercept.
* A control without annual shocks verifies that multiplying centered child status by 0.45 multiplies the latent slope by 0.45. This isolates the life cycle mechanism from temporary income noise.

The actual checks and their results are saved in `results/validation.json`. Code checks data construction and arithmetic; it does not validate the model as an account of actual mobility.

## References

* Haider, Steven, and Gary Solon. 2006. [Life-Cycle Variation in the Association between Current and Lifetime Earnings](https://www.nber.org/papers/w11943). NBER Working Paper 11943; published in the American Economic Review 96(4), 1308 to 1320. [Published article DOI](https://doi.org/10.1257/aer.96.4.1308).
* [Python sqlite3 documentation](https://docs.python.org/3/library/sqlite3.html) for connections, foreign key enforcement through SQLite statements, and parameter binding.
* [pandas read_sql_query documentation](https://pandas.pydata.org/docs/reference/api/pandas.read_sql_query.html) for retrieving query results as DataFrames.
* AEDS 6400 Class 12, SQL for Economists, for the structure of the query and validation workflow.
