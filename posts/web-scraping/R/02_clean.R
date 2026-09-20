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
here::i_am("posts/web-scraping/R/02_clean.R")

POST_DIR       <- here("posts", "web-scraping")
RAW_FILE       <- file.path(POST_DIR, "data", "raw", "postings_raw.csv")
POSTINGS_FILE  <- file.path(POST_DIR, "data", "processed", "postings.csv")
SKILLS_FILE    <- file.path(POST_DIR, "data", "processed", "skills_long.csv")

dir.create(file.path(POST_DIR, "data", "processed"), recursive = TRUE,
           showWarnings = FALSE)
dir.create(file.path(POST_DIR, "results", "tables"), recursive = TRUE,
           showWarnings = FALSE)
exclusions <- read_csv(file.path(POST_DIR, "data", "manual", "exclusions.csv"),
                       show_col_types = FALSE)
raw <- read_csv(RAW_FILE, show_col_types = FALSE)
stopifnot(nrow(raw) > 0)
stopifnot(all(exclusions$comment_id %in% raw$comment_id))


# ---- One observation = one retained top-level hiring comment ----
# A comment may advertise several roles; employers may post more than once.
# Targeted manual review decisions are saved as data, not edits to raw input.

keep_job_postings <- function(data) {
  data |>
    filter(indent == 0, !is.na(text), str_trim(text) != "") |>
    anti_join(exclusions, by = "comment_id") |>
    distinct(comment_id, .keep_all = TRUE)
}


# ---- the thread's posting convention ----
# The first line is pipe-delimited:
#   COMPANY | Location | Full-time | ONSITE | url
# Company is usually first; the field is an approximate label only.
# It is not a validated employer identifier; the other fields appear in no fixed
# order, so flag keywords rather than reading positions.

add_header_fields <- function(data) {
  data |>
    mutate(
      header    = str_squish(str_extract(text, "^[^\n]+")),
      company   = str_squish(str_extract(header, "^[^|]+")),
      remote    = str_detect(header, regex("remote", ignore_case = TRUE)),
      onsite    = str_detect(header, regex("onsite", ignore_case = TRUE)),
      hybrid    = str_detect(header, regex("hybrid", ignore_case = TRUE)),
      posted_at = as.POSIXct(substr(posted_at, 1, 19),
                             format = "%Y-%m-%dT%H:%M:%S", tz = "UTC"),
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
              "(?i)\\brust\\b", "(?i:\\bgolang\\b)|\\b(?:Go|GO)\\b(?![ -]+(?i:to[ -]+market|for[ ]+it))", "(?<!Terran )\\bR\\b(?![&+])",
              "(?i)\\breact\\b", "(?i)\\baws\\b", "(?i)\\bkubernetes\\b|\\bk8s\\b",
              "(?i)\\bdocker\\b", "(?i)\\bpostgres(ql)?\\b", "(?i)\\bspark\\b",
              "(?i)\\bterraform\\b", "(?i)\\bmachine learning\\b",
              "(?i)\\bllms?\\b|\\bgenai\\b", "(?i)\\bscala\\b", "(?i)\\bruby\\b")
)

# These are keyword categories, not a complete skill taxonomy.
# SQL means the literal token; Postgres is a separate category. Do not sum them.
# Case-sensitive R excludes the known Terran R rocket false positive.
# Go excludes Go-To-Market / Go for it and includes the observed GO/VUE spelling.
write_csv(skills, file.path(POST_DIR, "data", "processed", "skill_dictionary.csv"))

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

audit <- raw |>
  mutate(stage = case_when(
    is.na(indent) | indent != 0 ~ "Reply or missing depth",
    is.na(text) | str_trim(text) == "" ~ "Missing or empty top-level text",
    comment_id %in% exclusions$comment_id ~ "Excluded after targeted review",
    TRUE ~ "Retained hiring comment"
  )) |>
  count(thread, stage, name = "comments")
write_csv(audit, file.path(POST_DIR, "results", "tables", "cleaning_audit.csv"))
message("raw comments:  ", nrow(raw))
message("job postings:  ", nrow(postings))
message("excluded top-level comments (missing text or review): ",
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