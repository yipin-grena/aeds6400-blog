# AEDS 6400 — Computational Methods for Economists

Blog posts by Yipin Zhang (grenaz@sas.upenn.edu), Fall 2026.

**Published site:** https://yipin-grena.github.io/aeds6400-blog/

## Posts

| # | Post | Code and replication |
|---|------|----------------------|
| 1 | [What is a p-value?](https://yipin-grena.github.io/aeds6400-blog/posts/p-values/) | `posts/p-values/` |
| 2 | [Python leads technology mentions in Hacker News hiring posts](https://yipin-grena.github.io/aeds6400-blog/posts/web-scraping/) | [`posts/web-scraping/`](posts/web-scraping/README.md) |
| 3 | [Did labor-force participation recover equally across age groups?](https://yipin-grena.github.io/aeds6400-blog/posts/cps-participation/) | [`posts/cps-participation/`](posts/cps-participation/README.md) |
| 4 | [Inflation fell first, unemployment rose later: The U.S. experience through 2024](https://yipin-grena.github.io/aeds6400-blog/posts/inflation-unemployment/) | [`posts/inflation-unemployment/`](posts/inflation-unemployment/README.md) |

## Repository layout

This is a Quarto blog. Each post is a self-contained folder under `posts/`
holding its own code, data, and results, so a post can be reproduced without
the rest of the site.

```
aeds6400-blog/
├── _quarto.yml              site configuration
├── index.qmd                home page and post listing
├── docs/                    rendered GitHub Pages site
└── posts/
    ├── p-values/            Blog Post 1
    ├── web-scraping/        Blog Post 2
    ├── cps-participation/   Blog Post 3
    │   ├── index.qmd
    │   ├── README.md
    │   ├── run.R
    │   ├── R/analysis.R
    │   ├── data/raw/        local IPUMS extract, excluded from Git
    │   └── results/         aggregate tables and figures
    └── inflation-unemployment/  Blog Post 4
        ├── index.qmd
        ├── README.md
        ├── run.R
        ├── verify.py
        ├── R/               acquisition and analysis scripts
        ├── data/raw/        saved FRED CSVs and provenance
        └── results/         tables, sensitivity check and figures
```

## Reproducing a post

Clone the repository and open `aeds6400-blog.Rproj` in RStudio. All paths
resolve through `here()`, so no `setwd()` is required.

```r
source(here::here("posts", "web-scraping", "R", "01_scrape.R"))
source(here::here("posts", "web-scraping", "R", "02_clean.R"))
source(here::here("posts", "web-scraping", "R", "03_analyze.R"))
```

For Blog Post 2, step 1 reads committed HTML snapshots rather than contacting the source site,
so the analysis reproduces with no network requests. Per-post details,
including data provenance and the scraping ethics checklist, are in each
post's own README.

For Blog Post 3, obtain the IPUMS extract described in [its README](posts/cps-participation/README.md), then run from the repository root:

```sh
Rscript posts/cps-participation/run.R
```

This regenerates the aggregate results and charts. Rendering uses the committed aggregate results, so the raw microdata are only needed to rerun the analysis.

For Blog Post 4, run `Rscript posts/inflation-unemployment/run.R` from the repository root to reproduce from the committed FRED snapshots. Add `--refresh` only to download revised data. See [its README](posts/inflation-unemployment/README.md) for definitions and dependencies.

Render the site with `quarto render` from the repository root.

## Environment

R 4.5.1. Package versions are recorded separately in `posts/web-scraping/results/session-info.txt` and `posts/cps-participation/results/session-info.txt`. Blog Post 4 records its environment in `posts/inflation-unemployment/results/session-info.txt`. Each post README lists its dependencies and data requirements.
