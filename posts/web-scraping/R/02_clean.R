# ==============================================================
# 02_clean.R - turn raw comments into analysis-ready tables
#
# Reads  data/raw/postings_raw.csv
# Writes data/processed/postings.csv    one row per job posting
#        data/processed/skills_long.csv one row per posting-skill pair
# ==============================================================

library(dplyr)
library(stringr)
library(readr)

raw <- read_csv("data/raw/postings_raw.csv", show_col_types = FALSE)
message("raw comments: ", nrow(raw))


# --- 1. Keep only the job postings ----------------------------
# indent == 0 is a top-level comment, which in these threads is
# one employer's posting. Deeper comments are questions and chatter.

postings <- raw |>
  filter(indent == 0, !is.na(text)) |>
  distinct(comment_id, .keep_all = TRUE)

message("job postings: ", nrow(postings))


# --- 2. Pull structure out of the header line -----------------
# The thread has a posting convention: the first line is pipe-
# delimited, e.g.
#   QUOBYTE | Berlin, Germany | Full-time | ONSITE | https://...
# The company name is reliably first, but the remaining fields
# appear in no fixed order, so we flag keywords rather than
# reading positions.

postings <- postings |>
  mutate(
    header    = str_squish(str_extract(text, "^[^\n]+")),
    company   = str_squish(str_extract(header, "^[^|]+")),
    remote    = str_detect(header, regex("remote", ignore_case = TRUE)),
    onsite    = str_detect(header, regex("onsite", ignore_case = TRUE)),
    hybrid    = str_detect(header, regex("hybrid", ignore_case = TRUE)),
    posted_at = as.POSIXct(substr(posted_at, 1, 19), tz = "UTC"),
    n_words   = str_count(text, "\\S+")
  )


# --- 3. Which technologies does each posting mention? ---------
# Word boundaries matter enormously here. A bare "R" would match
# every capital R in the text, "Go" would match the word "go",
# and "C" would match almost everything. So: (?i) makes a pattern
# case-insensitive, \\b anchors to word boundaries, and the
# genuinely ambiguous ones stay case-sensitive on purpose.
#
# THIS LIST IS YOUR CALL. Add what matters to your question,
# drop what doesn't, and be ready to defend it in the post.

skills <- tribble(
  ~skill,              ~pattern,
  "Python",            "(?i)\\bpython\\b",
  "SQL",               "(?i)\\bsql\\b",
  "JavaScript",        "(?i)\\bjavascript\\b",
  "TypeScript",        "(?i)\\btypescript\\b",
  "Java",              "(?i)\\bjava\\b(?!script)",
  "C++",               "\\bC\\+\\+",
  "Rust",              "(?i)\\brust\\b",
  "Go",                "\\bGolang\\b|\\bgolang\\b|\\bGo\\b",
  "R",                 "\\bR\\b(?![&+])",
  "React",             "(?i)\\breact\\b",
  "AWS",               "(?i)\\baws\\b",
  "Kubernetes",        "(?i)\\bkubernetes\\b|\\bk8s\\b",
  "Docker",            "(?i)\\bdocker\\b",
  "Postgres",          "(?i)\\bpostgres(ql)?\\b",
  "Spark",             "(?i)\\bspark\\b",
  "Terraform",         "(?i)\\bterraform\\b",
  "Machine learning",  "(?i)\\bmachine learning\\b",
  "LLMs",              "(?i)\\bllms?\\b|\\bgenai\\b",
  "Scala",             "(?i)\\bscala\\b",
  "Ruby",              "(?i)\\bruby\\b"
)

skills_long <- postings |>
  select(comment_id, thread, company, remote, onsite, hybrid, text) |>
  cross_join(skills) |>
  mutate(mentioned = str_detect(text, pattern)) |>
  filter(mentioned) |>
  select(-text, -pattern, -mentioned)


# --- 4. Save and sanity-check ---------------------------------

postings |>
  select(-text) |>
  write_csv("data/processed/postings.csv")

write_csv(skills_long, "data/processed/skills_long.csv")

message("\nPostings by thread and work arrangement:")
print(count(postings, thread, remote))

message("\nTop 10 technologies mentioned:")
print(skills_long |> count(skill, sort = TRUE) |> head(10))