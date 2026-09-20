# ==============================================================
# 03_analyze.R - year-over-year comparison of skill demand
#
# Writes results/tables/skill_trends.csv
#        results/figures/skill_share_2026.png
#        results/figures/skill_change.png
# ==============================================================

library(dplyr)
library(ggplot2)
library(readr)
library(here)

POST_DIR   <- here("posts", "web-scraping")
FIG_DIR    <- file.path(POST_DIR, "results", "figures")
TAB_DIR    <- file.path(POST_DIR, "results", "tables")
TREND_FILE <- file.path(TAB_DIR, "skill_trends.csv")

dir.create(FIG_DIR, recursive = TRUE, showWarnings = FALSE)
dir.create(TAB_DIR, recursive = TRUE, showWarnings = FALSE)

postings    <- read_csv(file.path(POST_DIR, "data", "processed", "postings.csv"),
                        show_col_types = FALSE)
skills_long <- read_csv(file.path(POST_DIR, "data", "processed", "skills_long.csv"),
                        show_col_types = FALSE)


# ---- 1. share, not count ----
# The two threads have different numbers of postings, so raw counts
# are not comparable across years.

totals <- count(postings, thread, name = "n_postings")
n_2025 <- totals$n_postings[totals$thread == "2025-09"]
n_2026 <- totals$n_postings[totals$thread == "2026-09"]

shares <- skills_long |>
  count(thread, skill) |>
  left_join(totals, by = "thread") |>
  mutate(share = n / n_postings)


# ---- 2. one row per skill ----

s25 <- shares |> filter(thread == "2025-09") |> select(skill, n_2025 = n, share_2025 = share)
s26 <- shares |> filter(thread == "2026-09") |> select(skill, n_2026 = n, share_2026 = share)

trend <- full_join(s25, s26, by = "skill") |>
  mutate(across(where(is.numeric), \(x) coalesce(x, 0)),
         change_pp = 100 * (share_2026 - share_2025))


# ---- 3. which changes exceed sampling noise? ----
# With roughly 280 postings a year, a difference of a few percentage
# points is indistinguishable from chance. Test each one.

trend$p_value <- NA_real_
for (i in seq_len(nrow(trend))) {
  if (trend$n_2025[i] + trend$n_2026[i] >= 20) {
    test <- prop.test(c(trend$n_2025[i], trend$n_2026[i]), c(n_2025, n_2026))
    trend$p_value[i] <- test$p.value
  }
}

trend <- arrange(trend, desc(share_2026))
write_csv(trend, TREND_FILE)


# ---- 4. figures ----

fig_demand <- trend |>
  slice_max(share_2026, n = 12) |>
  ggplot(aes(100 * share_2026, reorder(skill, share_2026))) +
  geom_col(fill = "steelblue") +
  labs(title = "TODO - a title that states the finding",
       subtitle = paste0("Share of ", n_2026, " job postings, September 2026"),
       x = "% of postings mentioning the skill", y = NULL) +
  theme_minimal(base_size = 12)

ggsave(file.path(FIG_DIR, "skill_share_2026.png"),
       fig_demand,
       width = 8, height = 5, dpi = 300)

fig_change <- trend |>
  filter(n_2025 + n_2026 >= 20) |>
  mutate(significant = p_value < 0.05) |>
  ggplot(aes(change_pp, reorder(skill, change_pp), fill = significant)) +
  geom_col() +
  geom_vline(xintercept = 0, colour = "grey30") +
  scale_fill_manual(values = c("TRUE" = "steelblue", "FALSE" = "grey78"),
                    labels = c("TRUE" = "p < 0.05", "FALSE" = "within noise"),
                    name = NULL) +
  labs(title = "TODO - a title that states the finding",
       subtitle = "Change in share of postings, September 2025 to September 2026",
       x = "Percentage-point change", y = NULL) +
  theme_minimal(base_size = 12) +
  theme(legend.position = "bottom")

ggsave(file.path(FIG_DIR, "skill_change.png"),
       fig_change, width = 8, height = 5, dpi = 300)

message("postings: ", n_2025, " (2025) and ", n_2026, " (2026)")
message("changes significant at p < 0.05: ", sum(trend$p_value < 0.05, na.rm = TRUE))
print(trend, n = Inf)
