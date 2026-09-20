# Blog Post 2: technology mentions in Hacker News hiring comments

This project uses rvest to parse public HTML from two September hiring threads,
then compares technology mentions and suggests a focused learning project.
It describes the saved comments, not all employers, vacancies, or skill requirements.

## Sources and snapshot

- September 2025: https://news.ycombinator.com/item?id=45093192
- September 2026: https://news.ycombinator.com/item?id=49522897
- Acquisition metadata: `data/raw/metadata.csv`, dated 2026-09-19 21:29:46 EDT.
- Source HTML: `data/raw/html/`; original extracted comments: `data/raw/postings_raw.csv`.
- HN robots guidance: https://news.ycombinator.com/robots.txt
- Official API alternative: https://github.com/HackerNews/API

The metadata record the original script run; per-page request timestamps were
not recorded. Re-reading cached pages must not overwrite that date with today's
date. The September 2026 month was incomplete at acquisition. The two saved
threads are not matched samples of employers or equal completed-month censuses.

The original scraper caches HTML, uses a descriptive user agent and waits 30
seconds after each uncached page request. The current robots file specifies a
30-second crawl delay and does not disallow `/item`; it does not support the old
claim that `/submitted` is disallowed. Robots guidance alone is not blanket
permission. No logins, paywalls, CAPTCHAs or access controls are bypassed.
For production work the official API would generally be preferable; rvest is
used here to satisfy the educational HTML-scraping exercise.

## Folder structure

- `R/01_scrape.R`: rvest extraction, cached by default; no new requests unless enabled.
- `R/02_clean.R`: sample selection, documented exclusions and keyword matching.
- `R/03_analyze.R`: descriptive shares, tables, figures and session information.
- `data/raw/`: original HTML, raw extracted comments and original metadata.
- `data/manual/exclusions.csv`: targeted review decisions by comment ID and reason.
- `data/processed/`: generated posting metadata, matches and dictionary.
- `results/tables/`: generated shares, sample sizes, cleaning audit and R environment.
- `results/figures/`: generated PNGs used by the article.
- `index.qmd`: article, inline numbers and code that recreates its results.

An older `output/` folder, if present, is unused legacy output. The current article
reads only `results/`. Do not use an old CSV from `output/` to interpret this revision.

## Install dependencies

Open the repository's `aeds6400-blog.Rproj` in RStudio. Install R, RStudio and
Quarto if they are not already installed. Quarto is required for rendering.
In the R Console, run once:

```r
install.packages(c("dplyr", "tidyr", "stringr", "ggplot2", "readr",
                   "knitr", "here", "rvest", "httr", "robotstxt"))
```

The original screenshot shows R 4.5.1. The replacement source has been inspected
and its counts independently recalculated, but must be executed in R before
submission. Each analysis run saves the actual environment to
`results/tables/session-info.txt`. For a fully pinned environment, optionally use
`renv::init()` and `renv::snapshot()` at the project root after a successful run;
commit the lockfile and let future users run `renv::restore()`.

## Reproduce from the saved raw CSV (no network)

Restart R. From the repository root in the R Console:

```r
source(here::here("posts", "web-scraping", "R", "02_clean.R"))
source(here::here("posts", "web-scraping", "R", "03_analyze.R"))
```

Or in the Terminal, from the repository root:

```bash
Rscript posts/web-scraping/R/02_clean.R
Rscript posts/web-scraping/R/03_analyze.R
quarto render posts/web-scraping/index.qmd
quarto render
```

The article itself sources only the cleaning and analysis scripts, so a direct
render also regenerates its tables and saved figures. It does not run the scraper.
The final command rebuilds the complete website, including the listing page.
The project configuration places rendered website files in `docs/`.

## Reproduce rvest extraction from the cached HTML

From the R Console at the project root:

```r
options(hn.allow_network = FALSE)
source(here::here("posts", "web-scraping", "R", "01_scrape.R"))
```

This parses the saved HTML with rvest and rewrites the raw CSV. It must fail if a
required cached page is absent instead of silently accessing the website.
It preserves existing acquisition metadata. Then rerun cleaning and analysis.
Page 2 repeats page 1 in each saved thread; duplicate comment IDs terminate
collection. The MAX_PAGES limit raises an error if reached with new comments.

For a genuinely fresh scrape, use a separate copy of this post directory and
separate raw-output paths. Preserve the original snapshot, review current source
rules, and deliberately enable `options(hn.allow_network = TRUE)` there.
Do not mix new pages with old cached pages or describe a later scrape as the
original snapshot. Fresh collection may change counts and requires renewed review.
The scraper raises an error rather than saving a mixed snapshot over existing metadata.

## Measurement choices and checks

One observation is a retained top-level hiring comment, not a unique employer or
a single vacancy. Replies, missing-text comments and ten explicitly documented
review exclusions are removed. Employers can have multiple distinct comments;
several jobs may be advertised in one comment. No unique-employer analysis is claimed.
The `company` and work-arrangement fields are rough header extractions, not
validated identifiers, and are not used to make the article's recommendations.

The exclusions are five entries per year: discussion, job-seeking/service offers,
a thread-navigation promotion, or text insufficient to identify an advertisement.
Targeted review is not a guarantee that every remaining comment is classified
perfectly. Raw data are unchanged; the exclusion file makes decisions reproducible.

The dictionary is defined in `02_clean.R` and exported as `skill_dictionary.csv`:

- A comment contributes at most one match per category.
- SQL counts the literal SQL token; Postgres includes Postgres/PostgreSQL.
- LLMs includes LLM/LLMs and GenAI, but is not an exhaustive AI category.
- Machine learning matches that phrase, not every ML/AI abbreviation.
- JavaScript/TypeScript match their full names, not all JS/TS aliases.
- Go includes Golang (case-insensitive) and Go/GO, excluding the identified
  Go-To-Market and Go-for-it false positives.
- R excludes the identified Terran R rocket false positive. No verified match
  remains under this narrow rule; this is not proof of zero demand for R.
- All 20 categories are retained even if their counts are zero in both years.

Shares divide matches by every retained hiring comment in that year, including
comments mentioning none of the dictionary categories. Categories overlap, so
shares need not sum to 100%. Postgres and SQL shares cannot simply be added.
Known matching limitations remain. Mentions can describe stacks or incidental
context rather than mandatory qualifications. No linked job pages were scraped.

The revised analysis is descriptive. It does not use p-value colors or claim
that nonsignificant differences are 'within noise'. It makes no representative
population, causal, matched-employer, or employment-outcome claims.

## Expected results for this snapshot

- Raw comments: 863; replies: 284; top-level entries: 579.
- Missing-text top-level entries: 19; targeted review exclusions: 10.
- Retained: 550 total; 294 in 2025, 256 in 2026.
- Python: 79/294 and 71/256 (26.9% and 27.7%).
- TypeScript: 84/294 and 52/256 (28.6% and 20.3%).
- React: 82/294 and 51/256 (27.9% and 19.9%).
- Go: 26/294 and 15/256; R: 0 in both years.

The first chart includes ties at rank 12. The second shows all 20 categories.
Both are saved by ggsave at 300 dpi. The article reads these same image files,
avoiding separate versions of the plotted analysis.

## Submission

Review the rendered article, dates, labels, source links and GitHub link.
Commit the source, documented review decisions, reproducibility inputs and updated
site output. Publish through this repository's existing GitHub Pages configuration.
Submit BOTH the published article URL and the GitHub repository URL. A local
`docs/.../index.html` file or preview URL is not the public submission URL.
