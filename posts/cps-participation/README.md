# Blog Post 3: Did labor-force participation recover equally across age groups?

This post asks whether labor-force participation returned to its 2019 level equally across age groups. It uses Basic Monthly CPS data from 2019 through 2024 and three figures to connect recovery within age groups to changes in the overall population mix.

## Reproduce

From the repository root, install R dependencies once:

```r
install.packages(c("xml2", "dplyr", "tidyr", "ggplot2", "readr", "knitr", "rmarkdown", "here"))
```

Place the matching fixed-width data and XML codebook in `posts/cps-participation/data/raw/`. See `EXTRACT-INSTRUCTIONS.md` for sample selection. Then run:

```sh
Rscript posts/cps-participation/run.R
quarto render posts/cps-participation/index.qmd
```

The first command imports the raw data and regenerates all aggregate tables, figures, and `results/analysis.rds`. Rendering uses those saved results. Readers without the restricted microdata can regenerate the derived tables and figures from the committed monthly aggregates:

```sh
Rscript posts/cps-participation/run.R --from-aggregates
quarto render posts/cps-participation/index.qmd
```

This route reads `results/tables/monthly.csv` and the saved sample audit. It uses the same summary and plotting functions as the raw-data route, but does not repeat record-level import or sample checks. Rerun the full analysis after changing raw data, sample selection, or monthly calculations. The site output is under `docs/`. Package versions are in `results/session-info.txt`.

## Measurement and validation

The denominator is civilians age 16+ with [LABFORCE](https://cps.ipums.org/cps-action/variables/LABFORCE) 1 or 2 and positive finite [WTFINL](https://cps.ipums.org/cps-action/variables/WTFINL). Monthly participation is `sum(WTFINL * (LABFORCE == 2)) / sum(WTFINL)`. Annual estimates average 12 monthly rates equally. Counts are person-month observations, not unique people. The XML supplies column locations and implied decimal scaling; the importer applies scaling once.

The sample includes March Basic observations (`ASECFLAG = 2`) and excludes the separate ASEC supplement (`ASECFLAG = 1`). WTFINL is the Basic Monthly person weight used here. IPUMS recommends [COMPWT](https://cps.ipums.org/cps-action/variables/COMPWT) for replicating published BLS labor-force estimates; WTFINL is appropriate for most Basic Monthly analyses. These estimates are not seasonally adjusted and need not match BLS headline figures.

The three figures answer different questions:

- Figure 1, `trends.png`, compares participation changes from each age group's 2019 rate on common percentage-point axes. The text reports the 2024 changes and selected participation levels.
- Figure 2, `age_shares.png`, shows changes in population shares from 2019 to 2024. Monthly shares are weighted group populations divided by the total eligible population. The code averages the twelve monthly shares for each year, then takes the difference. It uses the `share` column in `monthly.csv`, rather than the raw number of survey respondents. The derived values are saved in `annual_shares.csv` and `share_changes.csv`.
- Figure 3, `age_mix.png`, compares overall participation with a calculation that fixes the age mix at its 2019 values. Both lines show changes from the common 2019 baseline.

For age group $g$, year $y$, and calendar month $m$, let $s_{g,y,m}$ be the weighted population share and $p_{g,y,m}$ its participation rate. The observed monthly rate is $P_{y,m}=\sum_g s_{g,y,m}p_{g,y,m}$. The fixed-mix rate is $P^{\mathrm{fixed}}_{y,m}=\sum_g s_{g,2019,m}p_{g,y,m}$. For example, January 2024 uses January 2019 shares. Each annual rate is the equal-weight average of its twelve monthly rates. Multiplying annual average shares by annual average participation rates would generally give a different answer.

The difference between the two annual rates is the average of $\sum_g(s_{g,2019,m}-s_{g,y,m})p_{g,y,m}$ across the twelve months, multiplied by 100 to express it in percentage points. Only the age shares change between the two calculations. This is a descriptive composition adjustment, not a causal estimate; changes within age bands remain.

Before estimating rates from raw data, `analysis.R` checks that all 72 months are present, rejects duplicate YEAR/MONTH/SERIAL/PERNUM identifiers, excludes ASEC records, and requires March Basic flags. It also checks that all month/age cells exist, that rates are finite and between zero and one, and that the observed and standardized series agree in 2019. Population shares must sum to one in each year, and the four share changes must sum to zero. The sample counts at each filtering step are saved in `results/tables/audit.csv`.

The post describes differences without claiming statistical significance or causality.

## Data provenance

The analysis reads `cps_00001.dat` using its matching `cps_00001.xml` codebook, dated September 27, 2026. The extract covers January 2019 through December 2024 Basic Monthly samples. The unchanged raw files are ignored by Git. Data SHA-256:

`c1706242d7704c44fc5360a2dc0da7797c9be1b7ec1ace42c71d8726579a6e5f`

Citation: Sarah Flood, Miriam King, Renae Rodgers, Steven Ruggles, J. Robert Warren, Daniel Backman, Etienne Breton, Grace Cooper, Julia A. Rivera Drew, Stephanie Richards, David Van Riper, and Kari C.W. Williams. IPUMS CPS: Version 13.0 [dataset]. Minneapolis, MN: IPUMS, 2025. https://doi.org/10.18128/D030.V13.0

## Files

- `index.qmd`: finished post with values drawn from analysis results.
- `R/analysis.R` and `run.R`: import, validation, analysis, and figures.
- `results/tables/`: monthly and annual participation estimates, annual population shares, both sets of changes, overall estimates, and sample audit.
- `results/figures/`: the three generated charts, `trends.png`, `age_shares.png`, and `age_mix.png`.
- `results/analysis.rds`: aggregate objects used by the post.
- `data/raw/`: private, unchanged microdata; excluded from Git.
