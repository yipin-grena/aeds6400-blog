suppressPackageStartupMessages({library(dplyr); library(tidyr); library(ggplot2)})
read_series <- function(root, id) {
  x <- read.csv(file.path(root, "data/raw", paste0(id, ".csv")), na.strings = c(".", ""))
  stopifnot(id %in% names(x))
  out <- data.frame(date = as.Date(x[[1]]), value = x[[id]])
  out <- out[out$date >= as.Date("2014-01-01") & out$date <= as.Date("2024-12-01"), ]
  out <- out[order(out$date), ]
  expected <- seq(as.Date("2014-01-01"), as.Date("2024-12-01"), by = "month")
  stopifnot(!anyDuplicated(out$date), identical(out$date, expected), all(is.finite(out$value)))
  names(out)[2] <- id
  out
}
run_analysis <- function(root) {
  cpi <- read_series(root, "CPIAUCSL")
  u <- read_series(root, "UNRATE")
  stopifnot(all(cpi$CPIAUCSL > 0), all(u$UNRATE >= 0 & u$UNRATE <= 100))
  d <- inner_join(cpi, u, by = "date", relationship = "one-to-one") |>
    mutate(inflation = 100 * (CPIAUCSL / lag(CPIAUCSL, 12) - 1)) |>
    filter(date >= as.Date("2015-01-01")) |>
    mutate(period = factor(case_when(date < as.Date("2020-01-01") ~ "2015-2019: Before COVID",
      date < as.Date("2022-01-01") ~ "2020-2021: Disruption", TRUE ~ "2022-2024: Inflation and cooling"),
      levels = c("2015-2019: Before COVID", "2020-2021: Disruption", "2022-2024: Inflation and cooling")))
  stopifnot(nrow(d) == 120, all(is.finite(d$inflation)))
  peak <- d[which.max(d$inflation), ]
  u_peak <- d[which.max(d$UNRATE), ]
  end <- tail(d, 1)
  post_peak <- d |> filter(date >= peak$date)
  trough <- post_peak[which.min(post_peak$UNRATE), ]
  # Quarterly means clarify chronological movement; not a fitted Phillips curve.
  q <- d |> mutate(year = as.integer(format(date, "%Y")), quarter = (as.integer(format(date, "%m")) - 1) %/% 3 + 1) |>
    group_by(year, quarter) |> summarise(inflation = mean(inflation), unemployment = mean(UNRATE), n = n(), .groups = "drop") |>
    mutate(label = paste0(year, " Q", quarter))
  stopifnot(all(q$n == 3))
  q_path <- q |> filter(year >= 2022) |> mutate(next_u = lead(unemployment), next_pi = lead(inflation))
  # Select comparison dates using inflation alone, not an unemployment minimum.
  # This retrospective rule depends on the chosen endpoint and is not a break test.
  start_q <- q_path[which.max(q_path$inflation), ]
  end_q <- tail(q, 1)
  candidates <- q_path |> filter(year * 4 + quarter > start_q$year * 4 + start_q$quarter)
  sensitivity <- bind_rows(lapply(c(0.4, 0.5, 0.6), function(fraction) {
    threshold <- start_q$inflation - fraction * (start_q$inflation - end_q$inflation)
    middle <- candidates |> filter(inflation <= threshold) |> slice_head(n = 1)
    stopifnot(nrow(middle) == 1)
    tibble(fraction = fraction, threshold = threshold, cutoff = middle$label,
      early_inflation_drop = start_q$inflation - middle$inflation,
      early_unemployment_change = middle$unemployment - start_q$unemployment,
      later_inflation_drop = middle$inflation - end_q$inflation,
      later_unemployment_change = end_q$unemployment - middle$unemployment)
  }))
  comparison <- sensitivity |> filter(fraction == 0.5)
  split_q <- q |> filter(label == comparison$cutoff)
  a <- list(monthly = d, quarterly = q, peak = peak, u_peak = u_peak,
    end = end, trough = trough, sensitivity = sensitivity,
    start_q = start_q, split_q = split_q, comparison = comparison)
  dir.create(file.path(root, "results/tables"), recursive = TRUE, showWarnings = FALSE)
  write.csv(d, file.path(root, "results/tables/monthly.csv"), row.names = FALSE)
  write.csv(q, file.path(root, "results/tables/quarterly.csv"), row.names = FALSE)
  write.csv(sensitivity, file.path(root, "results/tables/cutoff_sensitivity.csv"), row.names = FALSE)
  saveRDS(a, file.path(root, "results/analysis.rds"))
  theme <- theme_minimal(base_size = 13) + theme(panel.grid.minor = element_blank(),
    plot.title = element_text(face = "bold"), plot.caption = element_text(hjust = 0, size = 9), legend.position = "bottom")
  src <- "Source: BLS via FRED (CPIAUCSL, UNRATE). Seasonally adjusted monthly series.\nInflation = 12-month percentage change in CPI; unemployment = percent of labor force."
  long <- d |> filter(date >= as.Date("2022-01-01")) |> select(date, inflation, UNRATE) |> pivot_longer(-date) |>
    mutate(name = recode(name, inflation = "CPI inflation (12-month % change)", UNRATE = "Unemployment (% of labor force)"))
  markers <- bind_rows(
    tibble(date = peak$date, value = peak$inflation, name = "CPI inflation (12-month % change)",
      label = paste0(format(peak$date, "%b %Y"), ": ", sprintf("%.1f%%", peak$inflation))),
    tibble(date = trough$date, value = trough$UNRATE, name = "Unemployment (% of labor force)",
      label = paste0(format(trough$date, "%b %Y"), ": ", sprintf("%.1f%%", trough$UNRATE))))
  endpoints <- long |> filter(date == end$date)
  p1 <- ggplot(long, aes(date, value, color = name)) + geom_line(linewidth = 0.8) +
    geom_vline(xintercept = peak$date, linetype = "dotted", color = "grey60") +
    geom_point(data = markers, size = 2.5) +
    geom_text(data = markers, aes(label = label), nudge_y = 0.45, color = "grey20", size = 3.2) +
    geom_point(data = endpoints, size = 2.3) +
    geom_text(data = endpoints, aes(label = sprintf("%.1f%%", value)), hjust = 1.1,
      nudge_y = 0.4, size = 3.2, color = "grey20") +
    facet_wrap(~name, ncol = 1) + scale_color_manual(values = c("#D55E00", "#0072B2"), guide = "none") +
    scale_x_date(breaks = as.Date(c("2022-01-01", "2023-01-01", "2024-01-01")), date_labels = "%Y") +
    scale_y_continuous(limits = c(0, 10), breaks = seq(0, 10, 2)) +
    labs(title = "Inflation turned down before unemployment turned up",
      subtitle = "Monthly U.S. rates, 2022 through 2024; dotted line marks the inflation peak",
      x = NULL, y = "Percent", caption = src) + theme
  p2 <- ggplot(d, aes(UNRATE, inflation, color = period, shape = period)) + geom_point(size = 2.2, alpha = 0.8) +
    scale_color_manual(values = c("#009E73", "#0072B2", "#D55E00")) +
    labs(title = "Similar unemployment rates came with different inflation", subtitle = "Each point is a month; colors distinguish calendar periods", x = "Unemployment (% of labor force)", y = "CPI inflation (12-month % change)", color = NULL, shape = NULL, caption = src) + theme +
    guides(color = guide_legend(nrow = 3), shape = guide_legend(nrow = 3))
  p3 <- ggplot(q_path, aes(unemployment, inflation)) +
    geom_segment(data = q_path |> filter(!is.na(next_u)), aes(xend = next_u, yend = next_pi), color = "#59656F", linewidth = 0.7, arrow = grid::arrow(type = "closed", length = grid::unit(0.075, "inches"))) +
    geom_point(aes(color = factor(year)), size = 2.7) +
    geom_text(data = q_path |> filter(label %in% c("2022 Q1", "2022 Q2", "2023 Q2", "2023 Q4", "2024 Q4")), aes(label = label), nudge_y = 0.22, size = 3.1, check_overlap = FALSE) +
    scale_color_manual(values = c("#D55E00", "#009E73", "#0072B2")) +
    scale_x_continuous(limits = c(3.3, 4.35), breaks = seq(3.4, 4.2, .2)) +
    scale_y_continuous(expand = expansion(mult = c(.08, .12))) +
    labs(title = "Inflation fell as unemployment rose modestly", subtitle = "Quarterly averages, 2022-2024; arrows follow time (zoomed horizontal scale)", x = "Unemployment (% of labor force)", y = "Mean 12-month CPI inflation (%)", color = "Year", caption = paste0(src, "\nQuarterly values are means of three monthly rates, not annualized quarterly inflation.")) + theme
  for (name in c("timeline", "scatter", "path")) {
    plot <- switch(name, timeline = p1, scatter = p2, path = p3)
    ggsave(file.path(root, "results/figures", paste0(name, ".png")), plot, width = 9, height = 6.5, dpi = 220)
  }
  capture.output(sessionInfo(), file = file.path(root, "results/session-info.txt"))
  invisible(a)
}
