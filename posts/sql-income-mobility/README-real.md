# Real PSID analysis for Blog Post 6

`real_analysis.py` reads the locally supplied PSID and FIMS workbooks with pandas, constructs four tables, matches generations in SQLite, and estimates the relationship between parental and adult child family income. Only aggregate results are written to `results/real/`. The workbooks, normalized tables and matched children are not exported. SQLite runs in memory.

The published article uses this real-data analysis. The original simulation in `run.py` and `tutorial.py` is an optional separate example documented in `README-simulation.md`. Running the analysis does not render or publish the website; rendering uses the saved aggregate results.

## Run locally

Use Python 3.12 and install the analysis dependencies in an isolated environment.

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-real.txt
python real_analysis.py
python -m unittest discover -s tests -p 'test_real*.py'
```

The default input paths, relative to this post, are

* `data/raw/J366591/J366591.xlsx`
* `data/raw/fim16227_gid_BO_2_BAL.xlsx`

Both workbooks contain a `Data` sheet. Use `--extract` and `--fims` to supply different local paths. The program never modifies either workbook. Some exports contain invalid worksheet display attributes named `synchVertical` or `synchHorizontal`. If the Excel reader rejects those attributes, the program removes only those attributes from an in-memory copy and reads that copy. It does not alter cell values or write a replacement workbook.

Use `--no-figures` to run without matplotlib. The default run uses 1,000 bootstrap repetitions and seed 6400. `--bootstrap` changes that count and `--output` changes the aggregate output folder.

PSID's [Conditions of Use](https://simba.isr.umich.edu/U/CondUse.aspx) apply. They restrict redistribution and explicitly prohibit AI use with PSID data. Keeping records local and saving aggregates does not establish an exemption. The source workbooks and any respondent-level derivatives must not be committed or uploaded to GitHub.

## Inputs and four tables

The PSID extract is already a combined, wide individual file. Its family income fields repeat on family members' rows. `config/psid_waves.csv` maps survey years 1975 through 2023 to the relevant interview identifier, sequence number, relationship, age and total family income variables. It also records income years and codebook-specific income limits. Earlier variables in the supplied workbook are not used for this demonstration.

| Table | One row represents | Key |
| --- | --- | --- |
| `people` | One person in the supplied extract | `id68`, `pn` |
| `parent_links` | One child and a biological mother or father | Child's `id68`, `pn`, and parent type |
| `person_years` | A current family member in a survey wave | `id68`, `pn`, `survey_year` |
| `family_years` | A family observed in a survey wave | `survey_year`, `interview_number` |

`ER30001` and `ER30002` supply stable person identifiers. FIMS columns `ID68`, `PN`, `ID68P`, `PNP` and `PTYPE` supply complete child and parent identifiers and the mother/father distinction. Links whose people are absent from the extract are counted and excluded. A balanced FIMS map guarantees a known relationship, not complete income histories. See the [FIMS user manual](https://simba.isr.umich.edu/FIMS/FIMS_UG.pdf).

Current family membership requires a positive interview number and sequence number from 1 through 20. Reference persons require sequence 1 and the corresponding relationship code. Spouses or partners require sequence 2 and the relationship codes listed for that wave, including the historical husband codes. Movers and deceased members must not be treated as current reference persons merely because their relationship code is retained. See the [PSID FAQ](https://psidonline.isr.umich.edu/Guide/FAQ.aspx).

The program verifies that repeated income values agree within every family and wave before retaining one copy. Conflicts cause a failure. A release number is never used as a family identifier.

## Timing, amounts and sample

Income is for the calendar year before the interview. For example, the 2023 survey reports 2022 family income. `income_age` is interview age minus one, an approximation because this extract lacks birth month. Valid reported ages are 1 through 125; 999 is missing in the supplied codebook. A birth year proxy is the modal value of survey year minus reported age, with ties resolved to the earlier year. Age windows use each wave's reported age, not the inferred birth year.

The demonstration selects approximate birth cohorts 1960 through 1978. These cohorts allow adolescence and adulthood through age 44 to fall within the available history. Rules were selected before examining the regression coefficients.

* Parental income is measured when the child was approximately 15 through 19, with at least three valid income years. A linked parent must be a reference person or spouse/partner living in the same family as the child at interview. When both parents qualify in that family, `SELECT DISTINCT` counts the family income once. Income from a separate parental household is not added.
* Adult child income is measured when the child is a reference person or spouse/partner. Each age window, 25 through 29, 30 through 34, 35 through 39, and 40 through 44, requires at least two valid income years.
* A single observation is chosen nearest the midpoint of the relevant window, with ties resolved toward the earlier income year. This makes the single observation comparable in age to the average. It is not necessarily the same calendar year for everyone.
* Every headline estimate uses the intersection of children observed in all four adult windows, with positive parental and mature child single-year incomes. Window averages must also be positive for logarithms. Changing sample composition therefore cannot explain differences between these specifications.

The PSID's main interviews are biennial from 1999. These are averages over available observations within age windows, not five consecutive annual observations. Reported age inconsistencies and interview timing can also create more observations than the nominal width of an age range. `coverage.csv` reports the actual counts, ages and income-year coverage. A separate sensitivity excludes children whose implied birth years differ by more than two years across their observed waves.

Income handling follows `J366591_codebook.pdf` rather than a universal missing-value rule. Before 1994, the value 1 combines very low, zero and negative incomes and cannot be recovered precisely; it is excluded as unknown. Valid zero and negative incomes in later waves remain in the arithmetic average. Only the final average and selected single observations must be positive for the corresponding log regression. Valid upper caps are retained at the reported cap, so the upper tail remains censored. In particular, 9,999,999 means a Latino sample exclusion in the 1994 and 1995 family income variables, rather than unusually high income. The mapping excludes it in those waves.

Before averaging, each income is multiplied by the ratio of 2022 annual CPI to its income-year annual CPI. The public file `data/public/CPIAUCNS.csv` contains monthly, unadjusted CPI-U from the Bureau of Labor Statistics via [FRED](https://fred.stlouisfed.org/series/CPIAUCNS). Annual CPI is the mean of all twelve monthly values. It was acquired programmatically from

```text
https://fred.stlouisfed.org/graph/fredgraph.csv?id=CPIAUCNS&cosd=1974-01-01&coed=2022-12-31
```

## SQL and estimation

`sql/schema_real.sql` defines keys and foreign keys. `sql/match_real.sql` implements the matching, age restrictions, household deduplication, midpoint selection and aggregation. Python binds named parameters to the SQL query and reads the resulting matches into memory. The existing simulation query is retained separately so simulated and real outputs cannot be confused.

IGE is the OLS slope in

```text
log(adult child family income) = intercept + IGE * log(parental family income) + residual
```

Each average is taken in real dollar levels before taking its logarithm. The intermediate specification averages parental income while holding the selected adult child year fixed, which separates that change from averaging adult income too.

Standard errors cluster on the child's 1968 family identifier. The 95% intervals are percentile intervals from resampling these origin families. The same bootstrap draw is used across models, including intervals for differences between slopes. These are not full PSID survey-design standard errors. A supplementary model adjusts for linear birth year and sex; it is not a model with birth-cohort fixed effects. A missing-sex indicator is included if needed.

The extract contains no survey weights. These are unweighted associations for the retained sample, not estimates of a national population IGE. `ER32006` indicates sample membership and is not a weight. Family income includes other household members' resources and therefore differs from individual earnings. Household membership at interview can differ from membership during the previous income year. Attrition, missing parental links, co-residence restrictions and observed income requirements all select the sample. Topcoding and imputation remain features of the source data.

Differences across adult age windows also reflect different calendar periods and observation counts. They show sensitivity to measurement age, not an independently identified amount of lifecycle bias. There is no known true IGE in these real data, and the simulation's 0.4 benchmark is not used.

## Matching other years

1. Obtain a new individual-format extract and an appropriate FIMS map through your own PSID account. Include both stable person identifiers, the selected wave's family interview identifier, sequence, relationship, age and income variables.
2. Add or revise rows in `config/psid_waves.csv` using that extract's codebook. Verify both income timing and missing/censoring conventions; variable names and codes change across years. Extend the CPI file if the income years change.
3. Set the desired cohorts with `--birth-min` and `--birth-max`. For other age windows, change `AGE_WINDOWS` and the explicit parent-window and minimum-count parameters in `query_pairs`. Choose windows before reviewing results and ensure coverage exists.
4. Rerun the tests and the analysis. Review matching losses and `coverage.csv`. An unbalanced extract may have far fewer retained children, and an empty or very small common sample is reported as an error rather than silently relaxed.

## Aggregate outputs and verification

* `estimates.csv` contains slopes, clustered standard errors, bootstrap intervals and the cohort/sex sensitivity.
* `contrasts.csv` contains paired differences and bootstrap intervals.
* `sample-flow.csv`, `coverage.csv` and `wave-validation.csv` document exclusions, observation coverage and normalization checks.
* `age-quality-sensitivity.csv` repeats the comparisons after restricting age inconsistency.
* `validation.json` records input checksums, software versions, settings and aggregate validation counts.
* Two PNG figures visualize aggregate estimates only.

The tests use invented data only. They check separate households, repeated interview numbers in different years, duplicate parent links to the same family, incomplete and biennial histories, valid negative amounts, deflation, missing codes, fixed keys, regression arithmetic and paired bootstrap resampling. Runtime checks additionally verify foreign keys, unique records, income consistency, common samples and finite positive regression inputs. The simple OLS slope is checked independently against its covariance formula.

PSID data citation. Panel Study of Income Dynamics, public use dataset. Produced and distributed by the Survey Research Center, Institute for Social Research, University of Michigan, Ann Arbor, MI (2026).
