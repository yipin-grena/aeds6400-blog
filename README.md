# AEDS 6400 — Computational Methods for Economists

Blog posts by Yipin Zhang (grenaz@sas.upenn.edu), Fall 2026.

**Published site:** https://yipin-grena.github.io/aeds6400-blog/

## Posts

| # | Post | Code and replication |
|---|------|----------------------|
| 1 | [What is a p-value?](https://yipin-grena.github.io/aeds6400-blog/posts/p-values/) | `posts/p-values/` |
| 2 | [Python leads technology mentions in Hacker News hiring posts](https://yipin-grena.github.io/aeds6400-blog/posts/web-scraping/) | [`posts/web-scraping/`](posts/web-scraping/README.md) |

## Repository layout

This is a Quarto blog. Each post is a self-contained folder under `posts/`
holding its own code, data, and results, so a post can be reproduced without
the rest of the site.

```
aeds6400-blog/
├── _quarto.yml              site configuration
├── index.qmd                home page and post listing
├── docs/                    rendered site served by GitHub Pages
└── posts/
    ├── p-values/
    └── web-scraping/        Blog Post 2 (see its README)
        ├── index.qmd        the post
        ├── README.md        data sources, ethics, replication steps
        ├── R/               01_scrape, 02_clean, 03_analyze
        ├── data/raw/        scraped CSV, provenance, cached HTML
        ├── data/processed/  analysis-ready tables
        └── results/         figures and tables
```

## Reproducing a post

Clone the repository and open `aeds6400-blog.Rproj` in RStudio. All paths
resolve through `here()`, so no `setwd()` is required.

```r
source(here::here("posts", "web-scraping", "R", "01_scrape.R"))
source(here::here("posts", "web-scraping", "R", "02_clean.R"))
source(here::here("posts", "web-scraping", "R", "03_analyze.R"))
```

Step 1 reads committed HTML snapshots rather than contacting the source site,
so the analysis reproduces with no network requests. Per-post details,
including data provenance and the scraping ethics checklist, are in each
post's own README.

Render the site with `quarto render` from the repository root.

## Environment

R 4.5.1. Package versions used for the most recent run of Blog Post 2 are
recorded in `posts/web-scraping/results/session-info.txt`.
