# Blog Post 6

## How one year of income can mislead a study of mobility

This tutorial matches parents and children with SQL inside Python and asks how income measurement changes the estimated intergenerational elasticity. It uses a fully simulated panel, laid out like the Panel Study of Income Dynamics (PSID), so the underlying relationship is known.

**Published post:** https://yipin-grena.github.io/aeds6400-blog/posts/sql-income-mobility/

The article shows the matching query and explains the income comparisons. Expand the two Python examples to follow the query execution and estimation. The full runnable versions are `sql/match.sql` and `tutorial.py`; installation, database safeguards, and model details are documented below.

The post follows the Blog Post 6 prompt and the Class 12 SQL material. No real people, surveys, administrative records, or U.S. mobility estimates are represented here, and **no PSID data are used**. All income values are simulated in constant dollars, with no external data downloads or inflation adjustment needed. The simulation illustrates two measurement mechanisms; it is not evidence about their empirical size.

## Files

```text
sql-income-mobility/
├── index.qmd                   article with code read from the actual source files
├── README.md
├── requirements.txt            pinned analysis dependencies
├── run.py                      data generation, database, validation and figures
├── tutorial.py                 SQL execution and regression shown in the article
├── build_preview.py            standalone local HTML preview
├── sql/
│   ├── schema.sql              PSID-style tables, composite keys and foreign keys
│   └── match.sql               find family incomes, remove duplicates, then match
├── data/
│   ├── individuals.csv         one row per person (id68, pn)
│   ├── parent-links.csv        one row per child and parent, with parent type M or F
│   ├── individual-years.csv    one row per person and survey year
│   ├── family-years.csv        one row per family and survey year, with family income
│   ├── latent-status.csv       hidden lasting income, for teaching checks only
│   ├── provenance.json         seed, source statement and CSV checksums
│   └── mobility.sqlite         generated locally, excluded from Git
├── results/
│   ├── tables/                 estimates, age comparison and matched pairs
│   ├── figures/                two explanatory charts
│   ├── summary.json            numbers read by the article
│   ├── validation.json         checks actually run by run.py
│   └── environment.txt         Python, SQLite and package versions
└── preview/                    local review copy, excluded from Git
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

On Windows, activate with `.venv\Scripts\activate` instead. SQLite is included with Python. `run.py` regenerates the synthetic CSVs and database, validates all comparisons, and saves the tables, figures, and summary. The same seed reproduces every file exactly. It resolves paths relative to itself, so it can also be invoked from the repository root. `tutorial.py` runs the article's three comparisons on the generated database. No API key or network request is needed after installing packages.

To create the review copy, install Quarto, R, and the R packages `knitr` and `jsonlite`, then run

```sh
python build_preview.py
```

If Quarto is not on your path, supply `--quarto /path/to/quarto`. The script copies only this post's inputs into a temporary standalone project and writes `preview/Blog-Post-6.html`. It does not render the website or modify `docs/`; the published page is built with `quarto render` from the repository root. HTML uses the saved Python outputs; rerun `run.py` before rendering after changing the analysis. R only inserts generated values, figures and source code into the article. It performs no income analysis.

## How the tables mirror the PSID

The layout follows the PSID's public [FAQ](https://psidonline.isr.umich.edu/Guide/FAQ.aspx) and [FIMS documentation](https://simba.isr.umich.edu/FIMS/default.aspx). Every value is simulated.

* **Person identifiers.** As in the PSID, the 1968 family ID (`id68`) and person number (`pn`) together identify an individual. The PSID FAQ suggests combining them as `id68 * 1000 + pn` when one number is needed. Every join here uses both columns.
* **Parent links.** `parent_links` has one row per child and parent, with `parent_type` M (mother) or F (father), like a FIMS parent map. A child in a two-parent family therefore has two rows.
* **Person numbers.** Parents are original sample members with person numbers 1 and 2. Children born into the sample start at 030, matching the PSID's born-in range of 030 to 169.
* **Family income by year.** Income lives in `family_years`, keyed by `year` and `interview_number`. As the FAQ explains, a family's interview number is valid for that survey year only, so each person's yearly row in `individual_years` records that year's interview number.
* **Reference person and spouse.** The query keeps years in which a person is the reference person or spouse, using both the sequence number (1 or 2) and the relationship. In the PSID, relationship is a numeric code: 10 for the reference person from 1983 onward, and 20 or 22 for a spouse or partner, according to the FAQ. This simulation stores the labels instead. Every adult here is a reference person or spouse, so the filter removes no rows; in real data it excludes people living in someone else's family and movers-out.

Simplifications, compared with real PSID data:

* annual waves throughout, although the PSID became biennial after 1997
* no divorces, so co-resident parents share one family in every measured year
* no spouses entering the sample, no attrition and no missing years
* no survey weights

## Database and matching decisions

There are 4,000 original families with 14,566 people:

* **Parents:** 85% of families have both a mother and a father linked; the rest have only a mother.
* **Children:** each family has one to three children, born from 1975 through 1980, for 7,166 children in all, 6,095 of them with two linked parents.
* **Survey years:** parents' families are observed from 1990 through 1999, covering every child's ages 15 to 19. Each adult child forms a split-off family observed at ages 25 through 44, in 2000 through 2024.
* **Rows:** 13,261 parent links, 217,320 person-year rows and 183,320 family-year rows.

These dates and shares are teaching choices, not a historical dataset.

How `match.sql` builds each comparison:

* **Parental income.** It joins each child's parent links to the parents' person-years and then to family incomes. `SELECT DISTINCT` removes the second copy that two co-resident parents create for the same family-year, and averaging then uses the years when the child was in the requested age window. `HAVING` requires exactly one family for each requested year.
* **Child income.** It averages the child's own family income over the requested ages, with the same completeness check.
* **Joining.** The final inner join uses the child's `id68` and `pn` and produces one row per child. Generations are not joined on calendar year, and aggregating before matching avoids a many-to-many join of their annual records.
* **What DISTINCT prevents.** `run.py` checks that removing `DISTINCT` would keep only the 1,071 one-parent children. Every two-parent child would fail the completeness check.

The analysis uses parental family income and the child's own adult family income. Siblings share parental income in years that overlap, so their observations are not independent. Standard errors are not reported, and real work would cluster them by family. All specifications use the same 7,166 children.

## Simulation assumptions

The seed is `640006`; it was fixed before examining results. NumPy's default generator creates independent draws.

For family f, persistent parental status P has standard deviation 0.6. Each child i has an independent component E with standard deviation 0.45. Both have mean zero and normal distributions. The lasting log incomes are

```text
parent_log = log(60000) + P_f
child_log  = log(65000) + 0.4 * P_f + E_i
```

The population elasticity is therefore 0.4. The slope realized in these 7,166 latent pairs is also reported in `results/summary.json`. It may differ from 0.4 because E and P need not have exactly zero sample covariance. The latent values are used for validation and reference, never as a predictor in the reported matched income regressions.

Parental family income in each year is `exp(parent_log + u - 0.6^2/2)`, where each u is independent normal noise with standard deviation 0.6, shared by both parents because they live in one family.

For children, let t increase linearly from zero at age 25 to one at age 40 and remain one afterward. Define

```text
age_loading = 0.45 + 0.55 * t
age_level   = log(35000) + t * log(65000 / 35000)
income      = exp(age_level + age_loading * (0.4 * P_f + E_i) + v - 0.45^2/2)
```

Each v is independent normal noise with standard deviation 0.45. Subtracting half the shock variance makes the multiplicative annual shock have mean one. At age 40 and above the expected child income equals `exp(child_log)`.

Before 40, the loading compresses income gaps associated with lasting status. A common age profile alone would only change the intercept; it is the changing loading on centered status that generates the life-cycle bias here. The parameters and maturity age illustrate mechanisms and are not fitted to Haider and Solon or any U.S. data.

Every income is positive and each window is complete by construction. Real data would require a documented treatment of zero, negative and missing incomes. Restricting a real sample to complete positive-income histories can change the population being studied. The tutorial does not silently apply such a restriction to a survey.

## What the comparisons identify in this model

All estimates use ordinary least squares with an intercept, taking the natural log of the arithmetic average of annual real family income. Averaging logs would define a different income measure.

* **One year versus five-year averages.** One year for each generation (parents when the child was 15, child at 40) versus five-year averages (child aged 15 to 19, and 40 to 44) isolates averaging after the child loading has reached one. Temporary error in parental income lowers the expected slope; averaging reduces that error but does not remove it. Independent child income noise chiefly adds imprecision.
* **The child age curve.** It always uses parental income over the child's ages 15 to 19. Only the age of the child's single observation changes, holding the children and the parent measure fixed.
* **Early-career averages.** Averaging the child's ages 25 through 29 leaves the early-career loading below one. It reduces annual noise without solving the age mismatch.

The figures report estimates from one fixed simulated sample, not confidence intervals or empirical causal estimates. The dashed value 0.4 is the population simulation parameter. Finite-sample variation and residual income noise explain why a five-year average does not land exactly on it.

## Checks performed

`run.py` performs the following checks before saving figures:

* **Data integrity.** Database integrity and foreign key checks, unique person, person-year and family-year keys, and positive finite incomes.
* **Link audit.** A left join checks that every link finds both people, that mothers are female and fathers male, that parents' ages at the child's birth are plausible, and that every child has one or two parents.
* **Independent reconstruction.** Each of 23 specifications is rebuilt with pandas merges and duplicate removal. Its SQL means must agree within the numeric tolerance in the code, with the same 7,166 children and complete year counts.
* **The DISTINCT check.** The query without `DISTINCT` must keep exactly the 1,071 one-parent children.
* **Regression slopes.** Every slope is checked against the independent covariance divided by variance formula with an intercept.
* **Life-cycle control.** A control without annual shocks verifies that multiplying centered child status by 0.45 multiplies the latent slope by 0.45. This isolates the life-cycle mechanism from temporary income noise.

The actual checks and their results are saved in `results/validation.json`. Code checks data construction and arithmetic; it does not validate the model as an account of actual mobility.

## Using the real PSID instead

The same query structure applies to real PSID data, but those data cannot be placed in this repository.

* **Access.** Users must register with the PSID themselves and download the cross-year individual file, family files and a FIMS parent map.
* **Conditions of use.** The [PSID conditions of use](https://simba.isr.umich.edu/U/CondUse.aspx) forbid transferring public data or user-created extracts to third parties. They also prohibit using AI programs or large language models in conjunction with PSID data.
* **What could be shared.** A real-data version would publish only code and aggregate results, never raw or person-level files.

## References

* Haider, Steven, and Gary Solon. 2006. [Life-Cycle Variation in the Association between Current and Lifetime Earnings](https://www.nber.org/papers/w11943). NBER Working Paper 11943; published in the American Economic Review 96(4), 1308 to 1320. [Published article DOI](https://doi.org/10.1257/aer.96.4.1308).
* Mazumder, Bhashkar. 2005. [Fortunate Sons: New Estimates of Intergenerational Mobility in the United States Using Social Security Earnings Data](https://ideas.repec.org/a/tpr/restat/v87y2005i2p235-255.html). Review of Economics and Statistics 87(2), 235 to 255. Cited in the article for the downward bias from short averages of fathers' earnings.
* Panel Study of Income Dynamics. [Frequently Asked Questions](https://psidonline.isr.umich.edu/Guide/FAQ.aspx) and [Family Identification Mapping System](https://simba.isr.umich.edu/FIMS/default.aspx), Survey Research Center, Institute for Social Research, University of Michigan. Used only for the table layout; no PSID data were downloaded.
* Solon, Gary. 1992. [Intergenerational Income Mobility in the United States](https://ideas.repec.org/a/aea/aecrev/v82y1992i3p393-408.html). American Economic Review 82(3), 393 to 408. Cited in the article for the downward bias in earlier U.S. estimates.
* [Python sqlite3 documentation](https://docs.python.org/3/library/sqlite3.html) for connections, foreign key enforcement through SQLite statements, and parameter binding.
* [pandas read_sql_query documentation](https://pandas.pydata.org/docs/reference/api/pandas.read_sql_query.html) for retrieving query results as DataFrames.
* AEDS 6400 Class 12, SQL for Economists, for the structure of the query and validation workflow.
