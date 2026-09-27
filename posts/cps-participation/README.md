# Blog Post 3: Did labor-force participation recover equally across age groups?

Completed analysis of the supplied IPUMS CPS extract, with three figures and a Quarto post. Publication is a separate step.

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

Figure 1 compares age-group levels on common 0–100% axes. Figure 2 compares 2024 with 2019 in percentage points. Figure 3 fixes the four age-group population shares to those of the matching calendar month in 2019, then averages standardized monthly rates. This is a descriptive composition adjustment, not a causal estimate; changes within age bands remain.

Validation confirms 72 months, 288 month/age cells, no duplicate YEAR/MONTH/SERIAL/PERNUM identifiers, March Basic flags, no ASEC records, and valid rates. The input has 7,582,963 records; 6,146,546 meet the age/status criteria, all with positive finite weights. Independent streaming calculations from the original data agree with all 24 annual age-group estimates within 1e-12. All three generated charts were visually inspected. These custom estimates are not seasonally adjusted and need not exactly match official BLS series. No statistical significance or causality is claimed.

## Data provenance

User-supplied `cps_00001.dat` and `cps_00001.xml`; XML creation date September 27, 2026. The extract covers January 2019–December 2024 Basic Monthly samples. The unchanged raw files are ignored by Git. Data SHA-256:

`c1706242d7704c44fc5360a2dc0da7797c9be1b7ec1ace42c71d8726579a6e5f`

Citation: Sarah Flood, Miriam King, Renae Rodgers, Steven Ruggles, J. Robert Warren, Daniel Backman, Etienne Breton, Grace Cooper, Julia A. Rivera Drew, Stephanie Richards, David Van Riper, and Kari C.W. Williams. IPUMS CPS: Version 13.0 [dataset]. Minneapolis, MN: IPUMS, 2025. https://doi.org/10.18128/D030.V13.0

## Files

- `index.qmd`: finished post with values drawn from analysis results.
- `R/analysis.R` and `run.R`: import, validation, analysis, and figures.
- `results/tables/`: monthly and annual estimates, changes, overall estimates, and sample audit.
- `results/figures/`: the three generated charts.
- `results/analysis.rds`: aggregate objects used by the post.
- `data/raw/`: private, unchanged microdata; excluded from Git.
