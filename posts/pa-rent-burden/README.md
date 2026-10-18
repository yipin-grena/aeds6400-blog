# Blog Post 5 · Pennsylvania rent burden

This post compares the share and number of renter households under housing cost pressure across Pennsylvania. It uses a county choropleth and a comparison chart to examine Centre, Monroe, Philadelphia, and other counties.

[Read the published article](https://yipin-grena.github.io/aeds6400-blog/posts/pa-rent-burden/).

## Reproduce without publishing

Python 3.9 or later is required. From this folder, create an environment and run:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python run.py
.venv/bin/python build_preview.py
```

The analysis uses saved raw files by default and makes no network requests. `--refresh` downloads the three original public Census files again and updates their UTC retrieval timestamps and SHA256 checksums. The public downloads do not require an API key. Quarto, R, `knitr`, and `jsonlite` are needed only to render the article. `build_preview.py` accepts `--quarto /path/to/quarto` if Quarto is not on PATH. It creates a self-contained `preview/Blog-Post-5.html` without writing to the site's `docs/` folder. It never commits, pushes, or publishes. Its review banner identifies the local copy; the website version is rendered from `index.qmd`.

## Sources and period

* [2020–2024 ACS B25070 county variance replicate table](https://www2.census.gov/programs-surveys/acs/replicate_estimates/2024/data/5-year/050/B25070.csv.zip).
* [The corresponding Pennsylvania state estimate](https://www2.census.gov/programs-surveys/acs/replicate_estimates/2024/data/5-year/040/B25070.csv.zip), selected from the state download.
* [2024 county cartographic boundaries, 1:500,000](https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_us_county_500k.zip).
* [Census variable labels](https://api.census.gov/data/2024/acs/acs5/groups/B25070.html) and [2024 subject definitions, gross rent section](https://www2.census.gov/programs-surveys/acs/tech_docs/subject_definitions/2024_ACSSubjectDefinitions.pdf).
* [Census variance replicate method documentation](https://www2.census.gov/programs-surveys/acs/replicate_estimates/2024/documentation/5-year/2020-2024_Variance_Replicate_Table_Documentation.pdf).

The five year estimates describe 2020 through 2024, not 2024 alone or October 2026. They provide comparable coverage of all 67 counties. These published ACS estimates already incorporate Census survey weighting; no additional person weights are applied. The nationwide ZIP files are preserved unchanged. `data/raw/provenance.json` documents the original downloads. CSV text uses Latin-1 encoding.

## Measure and denominator

B25070 reports gross rent as a percentage of household income. Gross rent includes contract rent plus separately paid utilities and fuels. Its total includes renter occupied households, including no-cash-rent households. The eligible denominator is the sum of categories 002 through 010, or total 001 minus not-computed category 011. The numerator for at least 30% is categories 007 through 010. The numerator for at least 50% is category 010. The rate uses **at least** 30%, not strictly more than 30%.

The not-computed category includes no rent paid and zero or negative household income. These exclusions mean the article cannot describe the rate among all renter households. They are saved separately for every county. The excluded share is particularly high in some small counties, so low displayed burden should not be read as an absence of hardship. The 30% benchmark is a descriptive spending threshold, not a universal minimum budget or eligibility rule.

The Pennsylvania reference comes from the published state table, rather than an unweighted average of county rates. The outside-Philadelphia rate subtracts Philadelphia's numerator and eligible denominator from the state counts before dividing. Counts refer to households, not people. The map does not measure rent levels or housing supply.

## Uncertainty and geographic interpretation

For each derived rate, the code calculates the ratio for the published estimate and independently for each of the 80 matching variance replicates. Variance is `4/80 * sum((replicate_rate - published_rate)**2)`, and the 90% margin is `1.645 * sqrt(variance)`. This retains the covariance between numerator and denominator. The state reference uses state replicate estimates. The intervals are pointwise, not simultaneous intervals for rankings. No causal model or ranking significance test is performed.

The chart selects six counties with the highest point estimates, plus Allegheny as a western urban comparison. This is not a claim about their true rank. Centre and Monroe are nearly tied, and nearby estimates can overlap substantially. The full table includes every county, not only those highlighted.

The map does not display uncertainty. The article flags Forest, Cameron, and Elk as examples of small counties with relatively imprecise estimates. Their 90% margins of error are approximately 11.1, 11.2, and 8.2 percentage points respectively, available in the full results table. A color category is not an exact ranking or evidence of a precise difference between counties. Narrative household counts are rounded to the nearest hundred; the chart and tables preserve the underlying estimates.

County records join to boundaries by five digit GEOID with a one-to-one validation. The map uses EPSG:5070, an equal-area projection appropriate for the contiguous United States. Polygons are generalized cartographic boundaries. Fixed bins are below 40%, 40% to below 45%, 45% to below 50%, 50% to below 55%, and at least 55%; these are displayed categories, not estimated clusters. County area does not represent the number of renters. Labels are county names, placed at polygon representative points. Different geographic units could reveal different patterns within the counties.

## Context for interpreting the map

The following primary local sources provide context rather than additional inputs to the estimates.

* [Centre County's 2023 Housing Needs Assessment](https://centrecountypa.gov/DocumentCenter/View/25310/Centre-County-2023-HNA_Final_6_20_2023), printed page 64, describes low incomes and high rental cost burdens in student areas of State College and Patton Township. Centre County includes, but is not identical to, State College. The ACS county table does not identify students or quantify their contribution to the county rate. The article does not assume students have outside support or experience less hardship.
* [Monroe County's 2023 Comprehensive Affordable Housing Study](https://www.monroecountypa.gov/getmedia/963f4915-2714-4d21-a7d8-449339ca3b9b/20230922_1_AffHousing.pdf), printed page 4, describes relocation from New York and New Jersey and rental housing mismatches across income groups. It supplies possible context, not a causal estimate of migration's effect on the county rate.
* [Lehigh Valley Planning Commission's housing strategy](https://lvpc.org/housing) describes housing construction lagging population growth. The regional context covers Lehigh and Northampton counties together; the article does not treat it as a Lehigh County causal estimate or apply it to Delaware County.

These sources were checked on October 17, 2026. The article does not infer rent growth since 2020 from a single five year snapshot.

## Checks performed by run.py

* Raw download SHA256 hashes match the manifest before offline analysis.
* Every selected geography has exactly 11 table rows and 80 finite, nonnegative replicates.
* Total equals categories 002 through 011 for the estimate and all replicates.
* Eligible denominators are positive; burden rates are between 0% and 100%; severe burden does not exceed total burden.
* All 67 counties are unique, their estimated counts sum to the state totals, and none is lost or duplicated in the boundary join.
* All geometries are valid and nonempty; the saved GeoPackage reopens with 67 records and EPSG:5070.

Narrative results are computed from `results/summary.json` during rendering. `results/tables/` includes all county rates, intervals, excluded counts, the state reference, and the chart selection. `results/environment.json` records versions.

## Files

* `run.py` acquires optional fresh data, validates, analyzes, and draws both figures.
* `build_preview.py` renders a local HTML preview in an isolated temporary project.
* `requirements.txt` pins the direct Python dependencies used for this post.
* `index.qmd` contains the article, linked sources, captions, and inline calculations.
* `data/raw/` contains unchanged downloads and their provenance.
* `results/` contains the spatial dataset, tables, summary, environment record, and figures.
* `preview/` contains local review output and is excluded from Git.
