# ==============================================================
# 03_analyze.R - year-over-year comparison of skill demand
#
# Reads  data/processed/postings.csv, skills_long.csv
# Writes output/tables/skill_trends.csv
#        output/figures/skill_share_2026.png
#        output/figures/skill_change.png
# ==============================================================

library(dplyr)
library(ggplot2)
library(readr)

postings    <- read_csv("data/processed/postings.csv",    show_col_types = FALSE)
skills_long <- read_csv("data/processed/skills_long.csv", show_col_types = FALSE)


# --- 1. Share, not count --------------------------------------
# 2025 had 299 postings and 2026 had 261, so raw counts aren't
# comparable across years. Share of postings mentioning a skill is.

totals <- count(postings, thread, name = "n_postings")

shares <- skills_long |>
  count(thread, skill) |>
  left_join(totals, by = "thread") |>
  mutate(share = n / n_postings)


# --- 2. One row per skill, both years side by side ------------

s25 <- shares |> filter(thread == "2025-09") |> select(skill, n_2025 = n, share_2025 = share)
s26 <- shares |> filter(thread == "2026-09") |> select(skill, n_2026 = n, share_2026 = share)

trend <- full_join(s25, s26, by = "skill") |>
  mutate(across(where(is.numeric), \(x) coalesce(x, 0)),
         change_pp = 100 * (share_2026 - share_2025)) |>
  arrange(desc(share_2026))

write_csv(trend, "output/tables/skill_trends.csv")


# --- 3. What's in demand now ----------------------------------

p1 <- trend |>
  slice_head(n = 12) |>
  ggplot(aes(x = 100 * share_2026, y = reorder(skill, share_2026))) +
  geom_col(fill = "steelblue") +
  labs(
    title    = "TODO - a title that states the finding",
    subtitle = paste0("Share of ", totals$n_postings[totals$thread == "2026-09"],
                      " job postings, Hacker News hiring thread, September 2026"),
    x = "% of postings mentioning the skill",
    y = NULL
  ) +
  theme_minimal(base_size = 12)

ggsave("output/figures/skill_share_2026.png", p1, width = 8, height = 5, dpi = 300)


# --- 4. What's moving -----------------------------------------

p2 <- trend |>
  filter(n_2025 + n_2026 >= 20) |>   # ignore skills too rare to read into
  ggplot(aes(x = change_pp, y = reorder(skill, change_pp), fill = change_pp > 0)) +
  geom_col() +
  geom_vline(xintercept = 0, colour = "grey30") +
  scale_fill_manual(values = c("TRUE" = "steelblue", "FALSE" = "tomato"), guide = "none") +
  labs(
    title    = "TODO - a title that states the finding",
    subtitle = "Change in share of postings, September 2025 to September 2026",
    x = "Percentage-point change",
    y = NULL
  ) +
  theme_minimal(base_size = 12)

ggsave("output/figures/skill_change.png", p2, width = 8, height = 5, dpi = 300)


message("\nSkill trends:")
print(trend, n = Inf)