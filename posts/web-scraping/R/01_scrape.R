# ==============================================================
# 01_scrape.R - Hacker News "Who is hiring?" job postings
#
# Run by hand. index.qmd reads the saved CSV and never scrapes.
#
# Why scrape at all? Class 5 puts an official API above scraping,
# and Hacker News has one. The assignment requires rvest, so this
# collects the same data from public HTML instead.
#
# robots.txt (news.ycombinator.com, checked 2026-09-19):
#   /item?       allowed
#   /submitted?  DISALLOWED - thread IDs were found by hand
#   Crawl-delay: 30
# ==============================================================

library(rvest)
library(httr)
library(robotstxt)
library(dplyr)
library(readr)
library(here)

# ---- setup: paths and settings in one place ----

POST_DIR  <- here("posts", "web-scraping")
HTML_DIR  <- file.path(POST_DIR, "data", "raw", "html")
RAW_FILE  <- file.path(POST_DIR, "data", "raw", "postings_raw.csv")
META_FILE <- file.path(POST_DIR, "data", "raw", "metadata.csv")

BASE_URL   <- "https://news.ycombinator.com/item"
USER_AGENT <- "AEDS 6400 coursework (grenaz@sas.upenn.edu)"
DELAY_SEC  <- 30    # robots.txt asks for 30
MAX_PAGES  <- 15    # safety stop

threads <- tibble(
  label   = c("2025-09", "2026-09"),
  item_id = c(45093192L, 49522897L)
)

dir.create(HTML_DIR, recursive = TRUE, showWarnings = FALSE)


# ---- 1. is scraping permitted? ----

stopifnot(paths_allowed(BASE_URL, bot = "*"))


# ---- 2. fetch one page: cached, delayed, identified ----

fetch_page <- function(item_id, p) {
  path <- file.path(HTML_DIR, sprintf("hn_%d_p%02d.html", item_id, p))
  
  if (file.exists(path)) {
    message("cached:   ", basename(path))
    return(read_html(path))
  }
  
  url <- sprintf("%s?id=%d&p=%d", BASE_URL, item_id, p)
  message("fetching: ", url)
  
  response <- GET(url, user_agent(USER_AGENT))
  stop_for_status(response)
  writeBin(content(response, "raw"), path)
  
  Sys.sleep(DELAY_SEC)
  read_html(path)
}


# ---- 3. extract the comments from one page ----
# indent == 0 marks a top-level comment, which in these threads is
# one employer's job posting. html_element() (singular) inside each
# comment returns NA for a missing field, keeping columns aligned.

parse_page <- function(page) {
  rows <- html_elements(page, "tr.athing.comtr")
  if (length(rows) == 0) return(NULL)
  
  tibble(
    comment_id = html_attr(rows, "id"),
    indent     = as.integer(html_attr(html_element(rows, "td.ind"), "indent")),
    poster     = html_text2(html_element(rows, "a.hnuser")),
    posted_at  = html_attr(html_element(rows, "span.age"), "title"),
    text       = html_text2(html_element(rows, "div.commtext"))
  )
}


# ---- 4. walk one thread's pages ----
# HN serves short threads whole and returns page 1 again past the
# end, so stop when no new comment IDs appear.

scrape_thread <- function(item_id, label) {
  collected <- list()
  seen      <- character(0)
  
  for (p in seq_len(MAX_PAGES)) {
    page_data <- parse_page(fetch_page(item_id, p))
    if (is.null(page_data)) break
    
    page_data <- page_data[!page_data$comment_id %in% seen, ]
    if (nrow(page_data) == 0) break
    
    seen           <- c(seen, page_data$comment_id)
    collected[[p]] <- page_data
  }
  
  result <- bind_rows(collected)
  result$thread <- label
  result
}


# ---- 5. loop over threads: create, loop, store ----

scraped <- list()
for (i in seq_len(nrow(threads))) {
  scraped[[i]] <- scrape_thread(threads$item_id[i], threads$label[i])
}
raw <- bind_rows(scraped)


# ---- 6. validate immediately ----
# Acquisition succeeding is not the same as the data being correct.

stopifnot(nrow(raw) > 0)
stopifnot(anyDuplicated(raw$comment_id) == 0)
stopifnot(all(raw$thread %in% threads$label))

message("comments scraped: ", nrow(raw))
message("top-level postings: ", sum(raw$indent == 0, na.rm = TRUE))
message("share missing text: ", round(100 * mean(is.na(raw$text)), 1), "%")
print(table(raw$thread, top_level = raw$indent == 0))


# ---- 7. save the data and its provenance ----

write_csv(raw, RAW_FILE)

metadata <- tibble(
  source              = "Hacker News, Ask HN: Who is hiring?",
  thread              = threads$label,
  source_url          = paste0(BASE_URL, "?id=", threads$item_id),
  accessed_at         = format(Sys.time(), "%Y-%m-%d %H:%M:%S %Z"),
  robots_txt          = "https://news.ycombinator.com/robots.txt",
  crawl_delay_seconds = DELAY_SEC,
  comments_collected  = sapply(threads$label, function(x) sum(raw$thread == x))
)

write_csv(metadata, META_FILE)
message("wrote ", RAW_FILE, " and ", META_FILE)