# Descriptive keyword shares. Run after 02_clean.R; no network access.
library(dplyr)
library(tidyr)
library(ggplot2)
library(readr)
library(here)
here::i_am("posts/web-scraping/R/03_analyze.R")

POST_DIR <- here("posts", "web-scraping")
FIG_DIR <- file.path(POST_DIR, "results", "figures")
TAB_DIR <- file.path(POST_DIR, "results", "tables")
dir.create(FIG_DIR, recursive = TRUE, showWarnings = FALSE)
dir.create(TAB_DIR, recursive = TRUE, showWarnings = FALSE)
postings <- read_csv(file.path(POST_DIR, "data", "processed", "postings.csv"),
                     show_col_types = FALSE)
skills_long <- read_csv(file.path(POST_DIR, "data", "processed", "skills_long.csv"),
                        show_col_types = FALSE)
dictionary <- read_csv(file.path(POST_DIR, "data", "processed", "skill_dictionary.csv"),
                       show_col_types = FALSE)
totals <- count(postings, thread, name = "n_postings")
stopifnot(setequal(totals$thread, c("2025-09", "2026-09")))
stopifnot(all(totals$n_postings > 0))
stopifnot(!anyDuplicated(skills_long[c("comment_id", "skill")]))

# Keep all predefined categories, including those with zero matches in both years.
shares <- expand_grid(thread = totals$thread, skill = dictionary$skill) |>
  left_join(count(skills_long, thread, skill), by = c("thread", "skill")) |>
  mutate(n = coalesce(n, 0L)) |>
  left_join(totals, by = "thread") |>
  mutate(share = n / n_postings)
stopifnot(all(shares$share >= 0 & shares$share <= 1))
s25 <- shares |> filter(thread == "2025-09") |>
  select(skill, n_2025 = n, share_2025 = share)
s26 <- shares |> filter(thread == "2026-09") |>
  select(skill, n_2026 = n, share_2026 = share)
trend <- left_join(s25, s26, by = "skill") |>
  mutate(change_pp = 100 * (share_2026 - share_2025)) |>
  arrange(desc(share_2026), skill)
stopifnot(nrow(trend) == nrow(dictionary))
write_csv(trend, file.path(TAB_DIR, "skill_trends.csv"))
write_csv(totals, file.path(TAB_DIR, "sample_sizes.csv"))

n_2025 <- totals$n_postings[totals$thread == "2025-09"]
n_2026 <- totals$n_postings[totals$thread == "2026-09"]
# Ties at rank 12 are deliberately included and explained in the caption.
fig_demand <- trend |>
  slice_max(share_2026, n = 12, with_ties = TRUE) |>
  ggplot(aes(100 * share_2026, reorder(skill, share_2026))) +
  geom_col(fill = "steelblue") +
  labs(title = "Python leads the measured technology mentions",
       subtitle = paste0("September 2026 HN thread: ", n_2026, " retained hiring comments"),
       x = "Hiring comments mentioning the category (%)", y = NULL,
       caption = "Source: Hacker News; saved snapshot dated 19 September 2026.\nKeyword mentions may overlap; ties at rank 12 included.") +
  theme_minimal(base_size = 12) +
  theme(panel.grid.major.y = element_blank(),
        panel.grid.minor = element_blank())
ggsave(file.path(FIG_DIR, "skill_share_2026.png"), fig_demand,
       width = 9, height = 6.5, dpi = 300)

# A nonrandom set of postings does not justify population-wide significance claims.
# Show observed differences without p-value coloring or a 'within noise' claim.
fig_change <- trend |>
  ggplot(aes(change_pp, reorder(skill, change_pp))) +
  geom_vline(xintercept = 0, colour = "grey60", linetype = "dashed") +
  geom_point(colour = "steelblue", size = 2.5) +
  labs(title = "TypeScript and React have lower shares in the later snapshot",
       subtitle = paste0("2026 minus 2025; ", n_2026, " versus ", n_2025,
                         " retained hiring comments"),
       x = "Observed difference (percentage points)", y = NULL,
       caption = "Source: Hacker News September threads; snapshot dated 19 September 2026.\nDescriptive comparison; different employers and an incomplete 2026 month.") +
  theme_minimal(base_size = 12) +
  theme(panel.grid.major.y = element_blank(),
        panel.grid.minor = element_blank())
ggsave(file.path(FIG_DIR, "skill_change.png"), fig_change,
       width = 9, height = 7.5, dpi = 300)
writeLines(capture.output(sessionInfo()), file.path(TAB_DIR, "session-info.txt"))
print(totals)
print(trend, n = Inf)
