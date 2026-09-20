# ==============================================================
# 02_clean.R - raw comments to analysis-ready tables
#
# Reads  data/raw/postings_raw.csv
# Writes data/processed/postings.csv     one row per posting
#        data/processed/skills_long.csv  one row per posting-skill
# ==============================================================

library(dplyr)
library(stringr)
library(readr)
library(here)

POST_DIR       <- here("posts", "web-scraping")
RAW_FILE       <- file.path(POST_DIR, "data", "raw", "postings_raw.csv")
POSTINGS_FILE  <- file.path(POST_DIR, "data", "processed", "postings.csv")
SKILLS_FILE    <- file.path(POST_DIR, "data", "processed", "skills_long.csv")

raw <- read_csv(RAW_FILE, show_col_types = FALSE)
stopifnot(nrow(raw) > 0)


# ---- one job = one top-level comment ----

keep_job_postings <- function(data) {
  data |>
    filter(indent == 0, !is.na(text)) |>
    distinct(comment_id, .keep_all = TRUE)
}


# ---- the thread's posting convention ----
# The first line is pipe-delimited:
#   COMPANY | Location | Full-time | ONSITE | url
# Company is reliably first; the other fields appear in no fixed
# order, so flag keywords rather than reading positions.

add_header_fields <- function(data) {
  data |>
    mutate(
      header    = str_squish(str_extract(text, "^[^\n]+")),
      company   = str_squish(str_extract(header, "^[^|]+")),
      remote    = str_detect(header, regex("remote", ignore_case = TRUE)),
      onsite    = str_detect(header, regex("onsite", ignore_case = TRUE)),
      hybrid    = str_detect(header, regex("hybrid", ignore_case = TRUE)),
      posted_at = as.POSIXct(substr(posted_at, 1, 19), tz = "UTC"),
      n_words   = str_count(text, "\\S+")
    )
}

postings <- raw |>
  keep_job_postings() |>
  add_header_fields()


# ---- which technologies does each posting mention? ----
# Word boundaries decide everything here. Bare "R" would match
# every capital R, "Go" would match the verb. \\b anchors to word
# boundaries; (?i) makes a pattern case-insensitive; the ambiguous
# ones stay case-sensitive deliberately.
#
# Note \\bsql\\b does NOT match PostgreSQL or MySQL - there is no
# word boundary inside those words. That is a measurement choice,
# not an accident.

skills <- tibble(
  skill = c("Python", "SQL", "JavaScript", "TypeScript", "Java",
            "C++", "Rust", "Go", "R", "React", "AWS", "Kubernetes",
            "Docker", "Postgres", "Spark", "Terraform",
            "Machine learning", "LLMs", "Scala", "Ruby"),
  pattern = c("(?i)\\bpython\\b", "(?i)\\bsql\\b", "(?i)\\bjavascript\\b",
              "(?i)\\btypescript\\b", "(?i)\\bjava\\b(?!script)", "\\bC\\+\\+",
              "(?i)\\brust\\b", "\\bGolang\\b|\\bgolang\\b|\\bGo\\b", "\\bR\\b(?![&+])",
              "(?i)\\breact\\b", "(?i)\\baws\\b", "(?i)\\bkubernetes\\b|\\bk8s\\b",
              "(?i)\\bdocker\\b", "(?i)\\bpostgres(ql)?\\b", "(?i)\\bspark\\b",
              "(?i)\\bterraform\\b", "(?i)\\bmachine learning\\b",
              "(?i)\\bllms?\\b|\\bgenai\\b", "(?i)\\bscala\\b", "(?i)\\bruby\\b")
)

# create an empty container, loop, store each result
keep_cols <- c("comment_id", "thread", "company", "remote", "onsite", "hybrid")
matches   <- list()

for (i in seq_len(nrow(skills))) {
  mentioned        <- str_detect(postings$text, skills$pattern[i])
  matched          <- postings[mentioned, keep_cols]
  matched$skill    <- skills$skill[i]
  matches[[i]]     <- matched
}

skills_long <- bind_rows(matches)


# ---- validate after cleaning ----

stopifnot(nrow(postings) > 0)
stopifnot(anyDuplicated(postings$comment_id) == 0)
stopifnot(nrow(skills_long) > 0)
stopifnot(all(skills_long$comment_id %in% postings$comment_id))

message("raw comments:  ", nrow(raw))
message("job postings:  ", nrow(postings))
message("dropped (no text or duplicate): ",
        sum(raw$indent == 0, na.rm = TRUE) - nrow(postings))


# ---- save ----

postings |>
  select(-text) |>
  write_csv(POSTINGS_FILE)

write_csv(skills_long, SKILLS_FILE)

message("\nPostings by thread and work arrangement:")
print(count(postings, thread, remote))
message("\nTop 10 technologies:")
print(head(count(skills_long, skill, sort = TRUE), 10))