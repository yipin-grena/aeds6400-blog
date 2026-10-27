# Blog Post 7: everyday prices and annual inflation

**Status: published post.** [Read Blog Post 7](https://yipin-grena.github.io/aeds6400-blog/posts/everyday-prices/). `index.qmd` has `draft: false`. The optional preview builder renders an isolated review copy without changing the website's `docs/` directory or other posts.

## Question and scope

Which of five selected everyday categories was furthest above its December 2019 price level by December 2024, and how does that differ from annual inflation? One Plotly figure switches between cumulative percentage changes and year-over-year changes; category controls and date zoom let readers explore different paths. No universal three-figure minimum applies to Post 7.

The endpoint is deliberately historical. This is not an assessment of current prices or affordability. The five categories illustrate different spending areas and are not an exhaustive household budget or a ranking of every CPI category.

## Dependencies and setup

Use R, Quarto, Pandoc, and Python 3 for the optional isolated preview and independent numerical verification. Python performs no substantive price analysis; acquisition, transformations, summary values, and the Plotly figure use R.

Install the R dependencies once:

```r
install.packages(c("plotly", "htmlwidgets", "jsonlite", "rmarkdown", "knitr"))
```

Pandoc is used to save self-contained HTML and comes with Quarto. It must be discoverable by `rmarkdown::pandoc_available()`. On systems where it is not on PATH, set `RSTUDIO_PANDOC` to the directory containing the installed Pandoc executable. For example, the tested local RStudio installation uses:

```sh
export RSTUDIO_PANDOC=/Applications/RStudio.app/Contents/Resources/app/quarto/bin/tools/aarch64
```

That path is a macOS example, not a required folder layout. If packages were installed to a custom library, make it discoverable with `R_LIBS_USER`. No repository code changes are needed. Actual R/package versions are saved in `results/session-info.txt`; they document the tested environment, but this post has no dependency lockfile.

## Reproduce from the saved public snapshots

From the repository root:

```sh
Rscript posts/everyday-prices/run.R
python3 posts/everyday-prices/verify.py
python3 posts/everyday-prices/build_preview.py
```

The first command checks the snapshot checksums and data, regenerates all tables and values, builds the Plotly widget, and saves self-contained HTML. It makes no network requests. The second independently recomputes the arithmetic with Python's standard library. The third renders an isolated Quarto copy into `posts/everyday-prices/preview/Blog-Post-7.html`. Use `--quarto /path/to/quarto` if necessary. It accepts either source draft status and leaves the source unchanged. The resulting local review copy is labeled unpublished and embeds its assets.

`results/price-explorer.html` is the standalone interactive chart. `index.qmd` reads the generated monthly table and summary, then calls the same `R/figure.R` function to construct its widget using the installed packages. This avoids serializing machine-specific package paths into a saved R widget. Rendering the article alone does not reacquire or reanalyze raw inputs. Rerun `run.R` after changing data or analysis. Do not manually edit generated figures, tables, or summary values.

The preview omits website category navigation because a standalone file has no blog listing to navigate. It retains the article's title, author, date, prose, figure, and sources. The original Quarto source keeps its categories for the website.

An optional browser check is in `checks/browser.mjs`. It requires Node.js, Playwright, and a local Chrome installation. Set `CHROME_PATH` to the Chrome executable if it differs from the default macOS location, then run `node posts/everyday-prices/checks/browser.mjs` from the repository root. The script blocks HTTP/HTTPS requests while testing the self-contained preview, exercises the controls, verifies plotted endpoints, and writes `results/browser-validation.json`. Screenshots stay in the ignored preview folder. A touch device or screen reader is not tested by this mouse-based check.

To deliberately obtain new download snapshots of this fixed historical window:

```sh
Rscript posts/everyday-prices/run.R --refresh
```

This contacts FRED, validates all six responses before replacing the saved batch, and records new retrieval times and checksums. Historical source values can be revised, so preserve the supplied snapshots to reproduce this version exactly. The fixed requested window does not extend automatically with the current date.

## Public data and permissions

All six series originate at the U.S. Bureau of Labor Statistics and are distributed by FRED, Federal Reserve Bank of St. Louis. They are monthly CPI-U indexes, U.S. city average, **not seasonally adjusted**, originally **1982-1984 = 100**.

| Reader label | FRED series and original concept |
| --- | --- |
| Overall CPI | [CPIAUCNS](https://fred.stlouisfed.org/series/CPIAUCNS), all items |
| Groceries | [CUUR0000SAF11](https://fred.stlouisfed.org/series/CUUR0000SAF11), food at home |
| Rent | [CUUR0000SEHA](https://fred.stlouisfed.org/series/CUUR0000SEHA), rent of primary residence |
| Electricity | [CUUR0000SEHF01](https://fred.stlouisfed.org/series/CUUR0000SEHF01), electricity |
| Gasoline | [CUUR0000SETB01](https://fred.stlouisfed.org/series/CUUR0000SETB01), gasoline, all types |
| Clothing | [CPIAPPNS](https://fred.stlouisfed.org/series/CPIAPPNS), apparel |

The public aggregate CSVs are kept unchanged in `data/raw/`. `provenance.json` records exact request URLs, series IDs, UTC retrieval times, MD5 checksums, and row counts. FRED's CSV endpoint needs no API key. Each response covers December 2018 through December 2024, including the twelve earlier months needed to calculate annual inflation from December 2019 onward.

BLS [copyright guidance](https://www.bls.gov/opub/copyright-information.htm) places its published data in the public domain; the individual FRED pages tag these series "Public Domain: Citation Requested." Sources are attributed in the article and figure. These are already published aggregate indexes. No respondent records, private extracts, additional survey weighting, credentials, or restricted microdata are involved.

Additional primary documentation:

- [CPI frequently asked questions](https://www.bls.gov/cpi/questions-and-answers.htm): coverage, average price changes, and household differences.
- [CPI concepts](https://www.bls.gov/opub/hom/cpi/concepts.htm): what an index measures and how to interpret changes.
- [Seasonal adjustment questions](https://www.bls.gov/cpi/seasonal-adjustment/questions-and-answers.htm): recurring seasonal influences and adjusted versus unadjusted indexes.
- [Rent methodology](https://www.bls.gov/cpi/factsheets/owners-equivalent-rent-and-rent.htm): occupied rental homes and continuing rents.
- [Motor fuel methodology](https://www.bls.gov/cpi/factsheets/motor-fuel.htm): gasoline coverage.

## Measurement and checks

For raw category index `I[t]`:

```text
Cumulative change (%) = 100 * (I[t] / I[December 2019] - 1)
Annual inflation (%)  = 100 * (I[t] / I[same month a year earlier] - 1)
```

The calendar includes every requested month, and annual comparisons use explicit numeric year/month keys. Missing months cause a failure; they are not removed before a row lag, interpolated, or treated as zero. No cross-series arithmetic join is needed: each series is validated on the same calendar before stacking the long table. There are 73 raw months per series and 61 displayed months per series, or 366 displayed series-month rows.

The analysis checks:

- Exactly six unique configured series and an exact match to the manifest.
- Raw-file MD5 integrity, expected date/value column names, unique ordered dates, and the complete monthly calendar.
- Finite positive raw indexes and available exact prior-year matches for every displayed point.
- Unique series/month keys, zero cumulative change at the baseline, and finite computed values.
- Explicit category-only endpoint ranks. Overall CPI remains a benchmark rather than a sixth category.

`verify.py` independently recomputes saved monthly calculations, endpoint and summary values, peak annual rates, and endpoint sensitivity from the raw snapshots. Neither check establishes that BLS sampling or source measurement is error-free. Browser interaction checks are recorded separately in `results/browser-validation.json`; numerical checks alone cannot establish usable controls.

The endpoint sensitivity table compares December 2023 and December 2024 with the same December 2019 baseline. It documents whether this specific one-year shift changes category ordering; it is not a claim that ranks are invariant to every possible baseline or endpoint. The article's grocery peak refers to the maximum annual rate within the displayed December 2019 to December 2024 window. The subsequent change compares index levels, not percentage-point changes in inflation.

## Interpretive limits

- CPI-U measures average price changes for urban consumers. An index is not a household's dollar bill, a literal fixed shopping list, or a cross-category comparison of dollar price levels. Its internal expenditure weights do not become each reader's weights.
- Do not average the selected categories or treat them as their contributions to overall inflation. They are selected examples, not an exhaustive decomposition.
- These NSA series suit comparisons with actual unadjusted index levels; December-to-December endpoints match seasons, but within-year movements can reflect seasonality. A year-over-year rate compares the same calendar month.
- National rent indexes include continuing tenants and do not measure new asking rents alone, mortgage costs, or house purchase prices.
- No standard errors, significance tests, or causal model are estimated. Decimal differences should not be interpreted as exact or statistically established rankings, especially groceries versus rent.
- No earnings, household substitution, local spending shares, or quality-of-life measures are analyzed. The post cannot estimate purchasing power, household welfare, or policy effects.
- This endpoint precedes the October 2025 CPI data-collection gap. The chart does not silently bridge that later gap or make claims about 2025 or 2026.

## Files

```text
everyday-prices/
  index.qmd                    article and computed prose values
  run.R                        offline analysis entry point; optional --refresh
  R/acquire.R                  public snapshot acquisition and provenance
  R/analysis.R                 calendar checks, changes, summaries, sensitivity
  R/figure.R                   Plotly figure and interaction definitions
  config/series.csv            exact series IDs, reader labels, visual encodings
  data/raw/                    public unchanged CSVs and retrieval manifest
  results/tables/              monthly values, endpoints, peak rates, audit
  results/summary.json          computed values used in the article
  results/validation.json       checks performed by the R pipeline
  results/price-explorer.html   self-contained standalone figure
  results/session-info.txt      tested R/package environment
  verify.py                    independent arithmetic verification
  checks/browser.mjs           optional actual-browser interaction checks
  build_preview.py             isolated unpublished Quarto preview
  preview/                     local review HTML, excluded from Git
```
