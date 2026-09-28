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

The first command imports the raw data and regenerates all aggregate tables, figures, and `results/analysis.rds`. Rendering uses those saved results, allowing readers to render the committed post without restricted microdata. Rerun the analysis after changing data or analysis code. The site output is under `docs/`. Package versions are in `results/session-info.txt`.

## Measurement and validation

The denominator is civilians age 16+ with LABFORCE 1 or 2 and positive finite WTFINL. Monthly participation is `sum(WTFINL * (LABFORCE == 2)) / sum(WTFINL)`. Annual estimates average 12 monthly rates equally. Counts are person-month observations, not unique people. The XML supplies column locations and implied decimal scaling; the importer applies scaling once.

Figure 1 compares changes from each age group’s 2019 rate on common percentage-point axes. This makes recovery paths easier to compare, while the text reports selected participation levels. Figure 2 compares 2024 with 2019 in percentage points. Figure 3 fixes the four age-group population shares to those of the matching calendar month in 2019, then averages standardized monthly rates. This is a descriptive composition adjustment, not a causal estimate; changes within age bands remain.

Before estimating rates, `analysis.R` checks that all 72 months are present, rejects duplicate YEAR/MONTH/SERIAL/PERNUM identifiers, excludes ASEC records, and requires March Basic flags. It also checks that all month/age cells exist, that rates are finite and between zero and one, and that the observed and standardized series agree in 2019. The sample counts at each filtering step are saved in `results/tables/audit.csv`.

The estimates are not seasonally adjusted and are not intended to reproduce official BLS series. The post describes differences without claiming statistical significance or causality.

## Data provenance

The analysis reads `cps_00001.dat` using its matching `cps_00001.xml` codebook, dated September 27, 2026. The extract covers January 2019–December 2024 Basic Monthly samples. The unchanged raw files are ignored by Git. Data SHA-256:

`c1706242d7704c44fc5360a2dc0da7797c9be1b7ec1ace42c71d8726579a6e5f`

Citation: Sarah Flood, Miriam King, Renae Rodgers, Steven Ruggles, J. Robert Warren, Daniel Backman, Etienne Breton, Grace Cooper, Julia A. Rivera Drew, Stephanie Richards, David Van Riper, and Kari C.W. Williams. IPUMS CPS: Version 13.0 [dataset]. Minneapolis, MN: IPUMS, 2025. https://doi.org/10.18128/D030.V13.0

## Files

- `index.qmd`: finished post with values drawn from analysis results.
- `R/analysis.R` and `run.R`: import, validation, analysis, and figures.
- `results/tables/`: monthly and annual estimates, changes, overall estimates, and sample audit.
- `results/figures/`: the three generated charts.
- `results/analysis.rds`: aggregate objects used by the post.
- `data/raw/`: private, unchanged microdata; excluded from Git.
