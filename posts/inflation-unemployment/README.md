# Blog Post 4: Inflation and unemployment

[Read the post](https://yipin-grena.github.io/aeds6400-blog/posts/inflation-unemployment/).

This post asks whether unemployment rose throughout the fall in inflation after 2022 or mainly later. It uses a new aggregate dataset from BLS/FRED, distinct from the IPUMS microdata in Post 3. Three charts examine timing, differences across calendar periods, and the quarterly path during 2022–2024.

## Reproduce

From the repository root, install these R packages once:

```r
install.packages(c("here", "dplyr", "tidyr", "ggplot2", "knitr", "rmarkdown"))
```

Then run:

```sh
Rscript posts/inflation-unemployment/run.R
quarto render
```

The default analysis uses the committed raw snapshots and makes no network requests. Quarto reads the generated aggregate R object and images. Run the analysis before rendering after changing inputs or analysis code. Package versions are recorded in `results/session-info.txt`.

To deliberately replace the snapshots with current FRED data:

```sh
Rscript posts/inflation-unemployment/run.R --refresh
```

The acquisition code uses R's `download.file()` with FRED's public CSV URLs, requesting each series by ID and date range. No API key is required. The acquisition script saves each CSV response and records its exact URL, UTC retrieval time, and MD5 checksum in `data/raw/provenance.csv`. Revised source data can change historical results, so keep the committed snapshots to reproduce this version.

For an independent calculation check using only Python’s standard library, run `python3 posts/inflation-unemployment/verify.py`. It verifies the raw-file checksums and recomputes every monthly inflation rate and quarterly mean.

## Data

Both series originate at the U.S. Bureau of Labor Statistics and are distributed by FRED, Federal Reserve Bank of St. Louis:

| Series | Definition | Frequency and units |
|---|---|---|
| [CPIAUCSL](https://fred.stlouisfed.org/series/CPIAUCSL) | All-items CPI for all urban consumers, U.S. city average | Monthly, seasonally adjusted, 1982–1984 = 100 |
| [UNRATE](https://fred.stlouisfed.org/series/UNRATE) | U-3 unemployment rate, civilian labor force age 16+ | Monthly, seasonally adjusted, percent |

The request covers January 2014–December 2024. The analysis begins in January 2015 because inflation needs twelve earlier months. The fixed endpoint defines a historical comparison rather than a current-conditions report. These are published aggregate estimates: no additional person-level survey weighting is applied.

## Transformations and checks

- Inflation: `100 * (CPI / lag(CPI, 12) - 1)`, calculated after ordering and checking a complete monthly sequence. This is not a month-to-month annualized rate, and it may differ from the usual annual CPI headline based on unadjusted data.
- Monthly data are matched by date with a one-to-one join. The script rejects missing or duplicate months, nonfinite observations, nonpositive CPI, and unemployment outside 0–100. It requires 120 analysis months.
- The periods 2015–2019, 2020–2021, and 2022–2024 are transparent calendar groupings, not estimated structural regimes.
- Each quarterly coordinate is the arithmetic mean of its three monthly rates. The script requires three observations per quarter. Quarterly inflation here is the mean year-over-year rate, not quarterly annualized price growth.
- Figure 1 focuses on 2022 through 2024 in aligned panels with a common vertical scale, marking peak inflation and the subsequent unemployment trough. Figure 2 distinguishes periods by both shape and color. Figure 3 connects quarters chronologically and explicitly labels its narrower unemployment axis.

The figures describe contemporaneous relationships. They do not estimate causal effects, a structural Phillips curve, or the unemployment cost of any particular policy. Serial dependence, omitted drivers, policy responses, data revisions, and the chosen time window limit interpretation.

The unemployment baseline comparison uses both the inflation peak and the subsequent monthly unemployment trough. The quarterly comparison point is chosen using inflation alone: the first quarter after the quarterly inflation peak to complete at least 50% of the decline to 2024 Q4. `results/tables/cutoff_sensitivity.csv` repeats the rule at 40% and 60%. This retrospective rule depends on the endpoint and does not estimate structural breaks. Selecting the unemployment minimum itself would partly predetermine subsequent increases. All differences use unrounded values before display rounding. No standard errors are calculated for quarterly differences, so small changes are not presented as statistically significant.


The 40% threshold selects 2023 Q1, while the 50% and 60% thresholds select 2023 Q2 in the saved data. All three comparisons show little early unemployment movement and a larger later increase. See [the sensitivity table](results/tables/cutoff_sensitivity.csv) for the unrounded calculations. Monthly unemployment estimates have [sampling uncertainty](https://www.bls.gov/cps/factsheets/understanding-standard-errors-and-confidence-intervals.htm); the analysis does not establish statistical significance for quarterly changes. The saved download vintage is recorded in `data/raw/provenance.csv` and does not represent the information available in real time during the episode.

Package versions are documented in the session information, but are not pinned by an `renv.lock` file.

## Files

- `R/acquire.R`: optional programmatic FRED downloads and provenance.
- `R/analysis.R`: validation, transformations, aggregate objects, and three plots.
- `run.R`: entry point for an offline reproduction or explicit refresh.
- `data/raw/`: unchanged CSV responses and provenance.
- `results/tables/`: monthly and quarterly analysis data.
- `results/analysis.rds`: values used by inline R in the post.
- `results/figures/`: generated charts.
- `index.qmd`: article source, captions, and dynamically generated numbers.

## Historical scope and external context

December 2024 closes the peak year and two full calendar years after the 2022 inflation peak. This is an explicit historical window, not the latest available observation, a claim that adjustment ended then, or a conclusion about 2025 or 2026. The soft landing interpretation is limited to the inflation and unemployment evidence through that endpoint.

The article cites [Powell’s August 2024 assessment](https://www.federalreserve.gov/newsevents/speech/powell20240823a.htm) for supply disruptions, energy shocks, and their reversal. Those mechanisms come from the cited assessment; the two plotted series do not identify causal contributions. Powell discusses PCE inflation in that speech, while this analysis consistently uses CPI inflation. No numerical PCE comparison is imported into the figures.

The [St. Louis Fed discussion of recession indicators](https://www.stlouisfed.org/on-the-economy/2025/may/making-sense-recession-probabilities) documents the July 2024 Sahm warning. This is external historical context, not a Sahm series calculated by this project. The rule compares the three month mean unemployment rate with the lowest three month mean over the preceding twelve months, with a 0.50 percentage point threshold. Our June 2022 to December 2024 change is a different statistic and must not be interpreted as that rule. The warning is not an official recession determination.

The linked [NBER business cycle chronology](https://www.nber.org/research/business-cycle-dating) lists no recession after the July 2024 warning through December 2024. This historical comparison supports the article’s interpretation; it is not an inference that the Sahm rule itself determines recession dates. The CPI used here includes energy, unlike a core index excluding food and energy.
