# ==============================================================
# 01_scrape.R - Hacker News "Who is hiring?" job postings
#
# Collects top-level comments (= one job posting each) from two
# monthly hiring threads a year apart.
#
# Run this BY HAND, once. index.qmd never touches the site; it
# reads the saved CSV instead.
#
# robots.txt for news.ycombinator.com, checked 2026-09-19:
#   /item?       allowed      <- the thread pages, what we fetch
#   /submitted?  DISALLOWED   <- so the thread IDs below were found
#                by hand in a browser, never scraped
#   Crawl-delay: 30           <- honoured by DELAY_SEC
#
# Working directory must be posts/web-scraping/
# ==============================================================

library(rvest)
library(httr)
library(robotstxt)
library(dplyr)
library(purrr)
library(readr)

# --- Settings -------------------------------------------------

USER_AGENT <- "AEDS 6400 coursework (grenaz@sas.upenn.edu)"  # TODO your email
DELAY_SEC  <- 30    # HN's robots.txt asks for 30 seconds
MAX_PAGES  <- 15    # safety stop, in case the loop misbehaves
HTML_CACHE <- "data/raw/html"
RAW_OUT    <- "data/raw/postings_raw.csv"

# Thread IDs, looked up by hand (not scraped - /submitted? is disallowed)
threads <- tribble(
  ~label,     ~item_id,
  "2026-09",  49522897L,
  "2025-09",  45093192L
)

dir.create(HTML_CACHE, recursive = TRUE, showWarnings = FALSE)


# --- 1. Confirm robots.txt permits what we're about to do -----

if (!isTRUE(paths_allowed("https://news.ycombinator.com/item", bot = "*"))) {
  stop("robots.txt disallows /item - stop here, do not work around it.")
}


# --- 2. Fetch one page: cached, rate-limited, identified ------
# Cached pages are re-read from disk, so fixing a parsing mistake
# and re-running costs the site nothing.

fetch_page <- function(item_id, p) {
  name <- sprintf("hn_%d_p%02d", item_id, p)
  path <- file.path(HTML_CACHE, paste0(name, ".html"))
  
  if (file.exists(path)) {
    message("cached:   ", name)
    return(read_html(path))
  }
  
  url <- sprintf("https://news.ycombinator.com/item?id=%d&p=%d", item_id, p)
  message("fetching: ", url)
  
  resp <- GET(url, user_agent(USER_AGENT))
  stop_for_status(resp)
  writeBin(content(resp, "raw"), path)
  
  Sys.sleep(DELAY_SEC)
  read_html(path)
}


# --- 3. Pull the comments out of one page ---------------------
# Each comment is a <tr class="athing comtr">. The td.ind cell
# carries the reply depth, so indent == 0 identifies a top-level
# comment - in these threads, one employer's job posting.
#
# html_elements() (plural) gets one node per comment; then
# html_element() (singular) inside each one returns NA for a
# missing field instead of a shorter vector, which keeps the
# columns aligned.

parse_page <- function(page) {
  rows <- html_elements(page, "tr.athing.comtr")
  if (length(rows) == 0) return(NULL)
  
  tibble(
    comment_id = html_attr(rows, "id"),
    indent     = rows |> html_element("td.ind")       |> html_attr("indent") |> as.integer(),
    poster     = rows |> html_element("a.hnuser")     |> html_text2(),
    posted_at  = rows |> html_element("span.age")     |> html_attr("title"),
    text       = rows |> html_element("div.commtext") |> html_text2()
  )
}


# --- 4. Walk the pages until we stop seeing new comments ------
# HN serves short threads whole and paginates long ones with
# &p=2, &p=3. When you run past the end it hands back page 1
# again rather than an empty page, so stopping on "no new
# comment IDs" is safer than stopping on "no rows".

scrape_thread <- function(item_id, label) {
  out  <- list()
  seen <- character(0)
  
  for (p in seq_len(MAX_PAGES)) {
    got <- parse_page(fetch_page(item_id, p))
    if (is.null(got) || nrow(got) == 0) break
    
    got <- dplyr::filter(got, !comment_id %in% seen)
    if (nrow(got) == 0) break
    
    seen     <- c(seen, got$comment_id)
    out[[p]] <- got
  }
  
  list_rbind(out) |>
    mutate(thread = label, item_id = item_id)
}

raw <- threads |>
  pmap(\(label, item_id) scrape_thread(item_id, label)) |>
  list_rbind() |>
  mutate(scraped_at = Sys.time())


# --- 5. Save --------------------------------------------------

write_csv(raw, RAW_OUT)

message("\n", nrow(raw), " comments written to ", RAW_OUT)
message(sum(raw$indent == 0, na.rm = TRUE), " of them are top-level job postings")
print(count(raw, thread, top_level = indent == 0))