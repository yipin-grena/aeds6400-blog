# Blog Post 6

## How one year of income can mislead a study of mobility

This tutorial uses real PSID records and a FIMS biological parent map to match parents and children with SQL inside Python. It compares intergenerational family income elasticities using single observations, averages and different adult age windows. The income averaging comparison uses the same 1,522 adult children from 952 families of origin. The single-observation career-stage comparison uses a fixed subset of 1,504 children with positive selected incomes at every stage. SQL matching and IGE estimation use Python; aggregate validation, figures and the results report use R.

[Published article](https://yipin-grena.github.io/aeds6400-blog/posts/sql-income-mobility/) · [Detailed data and method guide](README-real.md) · [Aggregate results](results/real/REPORT.md)

## Reproduce the analysis

Use Python 3.12 and R with the `jsonlite` package. From this post's folder run

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-real.txt
Rscript -e 'install.packages("jsonlite", repos="https://cloud.r-project.org")'
python real_analysis.py
python -m unittest discover -s tests -p 'test_*.py'
Rscript R/validate-results.R
```

The two required local workbooks are not included in Git. Each user must obtain their own data through their PSID account and follow the [PSID Conditions of Use](https://simba.isr.umich.edu/U/CondUse.aspx), including its restrictions on redistribution and AI use.

The default paths are `data/raw/J366591/J366591.xlsx` and `data/raw/fim16227_gid_BO_2_BAL.xlsx`. Both use a `Data` sheet. Supply other paths with `--extract` and `--fims`. [README-real.md](README-real.md) gives the exact variable mapping, FIMS columns, income codes and instructions for matching other years. Do not upload respondent records or derived matched samples to GitHub.

The script reads both workbooks with pandas, constructs four tables, executes `sql/match_real.sql` in an in-memory SQLite database, and estimates all slopes and paired bootstrap intervals in Python. It then calls `R/render-results.R` to validate the aggregate tables, draw the figures and write the results report. Only aggregate results are saved. `--no-figures` omits plotting; `--bootstrap` changes the default 1,000 resamples. The random seed is 6400. Supply `--rscript /path/to/Rscript` if R is not on the path. Annual CPI is computed from the committed public BLS/FRED monthly CPI file.

For the complete setup-and-call tutorial shown in the article, run `python tutorial_real.py`. Its `--extract` and `--fims` arguments accept local paths. To redraw the figures without reopening any PSID records, run `Rscript R/render-results.R`.

## Files

```text
sql-income-mobility/
├── index.qmd                   article; reads aggregate results and actual code
├── real_analysis.py            pandas normalization, SQLite matching and estimation
├── tutorial_real.py            complete Python setup and main comparison example
├── R/                          aggregate checks, figures and results report
├── requirements-real.txt       tested analysis dependencies
├── README-real.md              complete method and matching other years
├── config/psid_waves.csv        wave-specific identifiers, ages and income codes
├── sql/schema_real.sql         people, parent links, person-years and family-years
├── sql/match_real.sql           parameterized parent and child income match
├── data/raw/                   private local workbooks, excluded from Git
├── data/public/CPIAUCNS.csv     public CPI observations for inflation adjustment
├── results/real/                aggregate estimates, checks, tables and two figures
├── tests/                      invented fixtures for matching and numerical checks
└── build_preview.py            standalone HTML review using aggregates only
```

## Design and limits

The sample uses approximate birth cohorts 1960 through 1978. Parental income is the child's co-resident family income at ages 15 through 19, requiring at least three observations. Adult child income requires reference person or spouse/partner status and at least two observations in each age window. The single-observation career-stage comparison selects one child income closest to ages 27, 32, 37 and 42. It additionally requires positive selected incomes at all four stages and uses that same child sample and parental average across ages. The averaged age-window sensitivity is saved on this same subset. Both full person identifiers are used in every person join, while family incomes are keyed by survey year and interview number. Two parents in one family must not duplicate its income.

Income refers to the previous calendar year. Reported interview age minus one approximates income age. Each amount is converted to 2022 dollars before averaging and taking logarithms. The observations are not five consecutive annual incomes; the PSID became biennial after 1997. Valid zero and negative incomes remain in averages, with positive final values required for log regressions. Missing codes and censored incomes follow the variable-specific codebook.

No survey weights were supplied. The estimates describe retained linked families, not a national population IGE. Family income differs from personal earnings. The new single-observation age comparison fixes the number of observations at one per stage. Calendar periods and family circumstances still change with age, so it cannot identify the true lifetime relationship. The paired oldest-versus-youngest difference interval includes zero. The article therefore reports inconclusive age evidence and uses an explicitly hypothetical log-income compression example to explain how lifecycle bias can arise. Standard errors cluster by the child's 1968 family identifier; intervals use paired family bootstrap draws and are not full PSID survey-design intervals.

`results/real/validation.json` records input checksums, software versions, settings and aggregate checks. The 34 Python tests use invented records only. They cover compound keys, family-income consistency, duplicate parent links, separate households, missing/biennial observations, income codes, deflation, regression arithmetic and bootstrap resampling.

## Render the article

Rendering the article needs Quarto, R and `knitr`; it uses committed aggregate files and does not need the private workbooks. R draws the figures, writes the results report and inserts values and source excerpts into the article. The record-level matching, regressions and bootstrap remain in Python as required by the assignment. `results/real/r-environment.txt` records the R rendering environment.

For a standalone review copy run `python build_preview.py`, supplying `--quarto /path/to/quarto` if needed. To prepare the site, render `posts/sql-income-mobility/index.qmd` and the root `index.qmd` with Quarto from the repository root. Review the generated `docs/` files before publishing.

## Optional simulation

`run.py`, `tutorial.py`, the original SQL files and the older result folders preserve an optional simulated example. They do not produce the current article's empirical results. See [README-simulation.md](README-simulation.md).

## Sources

* Panel Study of Income Dynamics, public use dataset. Produced and distributed by the Survey Research Center, Institute for Social Research, University of Michigan, Ann Arbor, MI (2026).
* [PSID FAQ](https://psidonline.isr.umich.edu/Guide/FAQ.aspx) and [FIMS user manual](https://simba.isr.umich.edu/FIMS/FIMS_UG.pdf) for identifiers, family membership and parent mapping.
* [BLS CPI-U via FRED](https://fred.stlouisfed.org/series/CPIAUCNS) for inflation adjustment.
* Haider, Steven, and Gary Solon. 2006. [Life-Cycle Variation in the Association between Current and Lifetime Earnings](https://doi.org/10.1257/aer.96.4.1308). American Economic Review 96(4), 1308 to 1320.
