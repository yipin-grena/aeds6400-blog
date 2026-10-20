suppressPackageStartupMessages({
  library(dplyr)
  library(tidyr)
  library(ggplot2)
  library(readr)
})

# Run from the project root. Raw files are never changed.
age_levels <- c("16-24", "25-54", "55-64", "65+")

read_extract <- function(raw_dir = "data/raw") {
  xml <- list.files(raw_dir, "\\.xml$", full.names = TRUE)
  csv <- list.files(raw_dir, "\\.csv(\\.gz)?$", full.names = TRUE)
  if (length(xml) == 1L) {
    # DDI supplies the field boundaries and implied decimal scaling.
    ddi <- xml2::read_xml(xml)
    vars <- xml2::xml_find_all(ddi, ".//*[local-name()='var']")
    names <- xml2::xml_attr(vars, "name")
    keep <- names %in% c("YEAR", "MONTH", "ASECFLAG", "SERIAL", "PERNUM", "AGE", "LABFORCE", "WTFINL")
    vars <- vars[keep]; names <- names[keep]
    loc <- xml2::xml_find_first(vars, "./*[local-name()='location']")
    positions <- readr::fwf_positions(as.integer(xml2::xml_attr(loc, "StartPos")),
      as.integer(xml2::xml_attr(loc, "EndPos")), col_names = names)
    filename <- xml2::xml_text(xml2::xml_find_first(ddi, ".//*[local-name()='fileName']"))
    data_file <- file.path(raw_dir, filename)
    if (!file.exists(data_file) && file.exists(paste0(data_file, ".gz"))) data_file <- paste0(data_file, ".gz")
    if (!file.exists(data_file)) stop("Missing data file named by the XML: ", data_file)
    dat <- readr::read_fwf(data_file, positions, col_types = paste(rep("d", length(names)), collapse = ""),
      progress = FALSE, show_col_types = FALSE, lazy = FALSE)
    if (nrow(readr::problems(dat))) stop("Fixed-width parsing errors; check data/codebook match.")
    decimals <- as.integer(xml2::xml_attr(vars, "dcml"))
    for (i in seq_along(names)) dat[[names[i]]] <- dat[[names[i]]] / 10^decimals[i]
    return(dat)
  }
  if (length(xml) == 0L && length(csv) == 1L) {
    return(readr::read_csv(csv, show_col_types = FALSE))
  }
  stop("Supply one IPUMS CPS extract in data/raw: XML + DAT.GZ (preferred), or one CSV/CSV.GZ. See EXTRACT-INSTRUCTIONS.md.")
}

analyze_cps <- function(raw) {
  required <- c("YEAR", "MONTH", "ASECFLAG", "SERIAL", "PERNUM", "AGE", "LABFORCE", "WTFINL")
  absent <- setdiff(required, names(raw))
  if (length(absent)) stop("Missing variables: ", paste(absent, collapse = ", "))
  d <- raw |> select(all_of(required)) |> mutate(across(everything(), as.numeric))
  d <- d |> filter(YEAR %in% 2019:2024)
  if (!nrow(d)) stop("No 2019-2024 records.")
  if (anyNA(d[c("YEAR", "MONTH", "SERIAL", "PERNUM")])) stop("Missing record identifiers.")
  if (any(d$ASECFLAG == 1, na.rm = TRUE)) stop("ASEC records detected. Select only Basic Monthly samples.")
  if (any(is.na(d$ASECFLAG[d$MONTH == 3]) | d$ASECFLAG[d$MONTH == 3] != 2)) stop("March records must be flagged as March Basic (ASECFLAG = 2).")
  if (anyDuplicated(d[c("YEAR", "MONTH", "SERIAL", "PERNUM")])) stop("Duplicate within-month person records.")
  expected <- expand_grid(YEAR = 2019:2024, MONTH = 1:12)
  observed <- distinct(d, YEAR, MONTH)
  if (nrow(anti_join(expected, observed, by = c("YEAR", "MONTH"))) ||
      nrow(anti_join(observed, expected, by = c("YEAR", "MONTH")))) {
    stop("The analysis requires all 72 Basic Monthly samples, January 2019-December 2024.")
  }
  audit <- tibble(
    stage = c("Input person-months, 2019-2024", "Age 16+ with defined civilian labor-force status", "Positive finite weights"),
    records = c(nrow(d), sum(d$AGE >= 16 & d$LABFORCE %in% c(1, 2), na.rm = TRUE),
                sum(d$AGE >= 16 & d$LABFORCE %in% c(1, 2) & is.finite(d$WTFINL) & d$WTFINL > 0, na.rm = TRUE))
  )
  d <- d |> filter(AGE >= 16, LABFORCE %in% c(1, 2), is.finite(WTFINL), WTFINL > 0) |>
    mutate(age_group = factor(case_when(AGE < 25 ~ "16-24", AGE < 55 ~ "25-54", AGE < 65 ~ "55-64", TRUE ~ "65+"), levels = age_levels),
           in_labor_force = LABFORCE == 2)
  monthly <- d |> group_by(YEAR, MONTH, age_group) |>
    summarise(n = n(), population = sum(WTFINL), labor_force = sum(WTFINL * in_labor_force), .groups = "drop") |>
    mutate(rate = labor_force / population) |> group_by(YEAR, MONTH) |>
    mutate(share = population / sum(population)) |> ungroup()
  summarize_monthly_cps(monthly, audit)
}

# The raw-data and aggregate-only routes use the same validated summaries.
summarize_monthly_cps <- function(monthly, audit) {
  required <- c("YEAR", "MONTH", "age_group", "n", "population", "labor_force", "rate", "share")
  absent <- setdiff(required, names(monthly))
  if (length(absent)) stop("Missing monthly columns: ", paste(absent, collapse = ", "))
  monthly <- monthly |> mutate(age_group = factor(age_group, levels = age_levels))
  if (nrow(monthly) != 72L * 4L ||
      anyNA(monthly[c("YEAR", "MONTH", "age_group")]) ||
      any(!monthly$YEAR %in% 2019:2024) || any(!monthly$MONTH %in% 1:12) ||
      anyDuplicated(monthly[c("YEAR", "MONTH", "age_group")])) {
    stop("Expected one cell for every age group in each of the 72 months.")
  }
  stopifnot(all(is.finite(monthly$population) & monthly$population > 0),
            all(is.finite(monthly$n) & monthly$n > 0),
            all(is.finite(monthly$rate) & monthly$rate >= 0 & monthly$rate <= 1),
            all(is.finite(monthly$share) & monthly$share >= 0 & monthly$share <= 1),
            all(is.finite(monthly$labor_force)),
            all(abs(monthly$rate - monthly$labor_force / monthly$population) < 1e-10))
  share_check <- monthly |> group_by(YEAR, MONTH) |>
    mutate(expected_share = population / sum(population)) |> ungroup()
  stopifnot(all(abs(share_check$share - share_check$expected_share) < 1e-10))
  # Each month receives equal weight in the annual mean of monthly rates.
  # Counts are person-month observations, not distinct people.
  annual <- monthly |> group_by(YEAR, age_group) |>
    summarise(rate = mean(rate), n_person_months = sum(n), .groups = "drop")
  # Average the monthly weighted population shares, not raw sample counts or
  # population totals pooled across months. These are distinct from rates.
  annual_shares <- monthly |> group_by(YEAR, age_group) |>
    summarise(share = mean(share), .groups = "drop")
  annual_share_totals <- annual_shares |> group_by(YEAR) |>
    summarise(total_share = sum(share), .groups = "drop")
  stopifnot(nrow(annual_shares) == 6L * 4L,
            all(is.finite(annual_shares$share)),
            all(annual_shares$share >= 0 & annual_shares$share <= 1),
            all(abs(annual_share_totals$total_share - 1) < 1e-10))
  share_changes <- annual_shares |> filter(YEAR %in% c(2019, 2024)) |>
    pivot_wider(names_from = YEAR, values_from = share, names_prefix = "share_") |>
    mutate(change_pp = 100 * (share_2024 - share_2019))
  stopifnot(nrow(share_changes) == 4L, abs(sum(share_changes$change_pp)) < 1e-10)
  changes <- annual |> filter(YEAR %in% c(2019, 2024)) |>
    select(YEAR, age_group, rate) |> pivot_wider(names_from = YEAR, values_from = rate, names_prefix = "rate_") |>
    mutate(change_pp = 100 * (rate_2024 - rate_2019))
  # Match each month to that calendar month's 2019 age shares. This anchors
  # both series to the same 2019 value and does not pool population totals.
  base_shares <- monthly |> filter(YEAR == 2019) |> select(MONTH, age_group, base_share = share)
  overall_monthly <- monthly |> left_join(base_shares, by = c("MONTH", "age_group"), relationship = "many-to-one") |>
    group_by(YEAR, MONTH) |>
    summarise(observed = sum(share * rate), standardized = sum(base_share * rate), .groups = "drop")
  overall <- overall_monthly |> group_by(YEAR) |>
    summarise(observed = mean(observed), standardized = mean(standardized), .groups = "drop")
  stopifnot(abs(overall$observed[overall$YEAR == 2019] - overall$standardized[overall$YEAR == 2019]) < 1e-10)
  list(monthly = monthly, annual = annual, annual_shares = annual_shares,
       share_changes = share_changes, changes = changes, overall = overall, audit = audit)
}

make_figures <- function(a) {
  palette <- c("16-24" = "#0072B2", "25-54" = "#009E73", "55-64" = "#D55E00", "65+" = "#CC79A7")
  common <- theme_minimal(base_size = 13) + theme(panel.grid.minor = element_blank(),
    plot.title = element_text(face = "bold"), plot.caption = element_text(hjust = 0, size = 9), legend.position = "bottom")
  caption <- "Source: IPUMS CPS, Census Bureau and BLS. Civilians age 16+; WTFINL weights.\nAnnual means of 12 monthly rates; not seasonally adjusted."
  trends <- a$annual |> group_by(age_group) |>
    mutate(change_pp = 100 * (rate - rate[YEAR == 2019])) |> ungroup()
  p1 <- ggplot(trends, aes(YEAR, change_pp, color = age_group, group = age_group)) +
    geom_hline(yintercept = 0, color = "grey55", linetype = "dashed") +
    geom_line(linewidth = 0.9) + geom_point(size = 2.1) + facet_wrap(~age_group, ncol = 2) +
    scale_color_manual(values = palette, guide = "none") + scale_x_continuous(breaks = 2019:2024) +
    labs(title = "Prime-age participation recovered; 65+ did not",
      subtitle = "Change from each age group's 2019 participation rate",
      x = NULL, y = "Change (percentage points)", caption = caption) + common
  shares_plot <- a$share_changes |>
    mutate(age_group = factor(as.character(age_group), levels = rev(age_levels)),
           change_label = sprintf("%+.2f", change_pp),
           share_label = sprintf("%.2f%% to %.2f%%", 100 * share_2019, 100 * share_2024),
           label_x = change_pp + if_else(change_pp >= 0, 0.08, -0.08),
           label_hjust = if_else(change_pp >= 0, 0, 1))
  p2 <- ggplot(shares_plot, aes(change_pp, age_group, fill = age_group)) +
    geom_vline(xintercept = 0, color = "grey55", linewidth = 0.5) +
    geom_col(width = 0.55) +
    geom_text(aes(x = label_x, label = change_label, hjust = label_hjust),
              size = 3.9, show.legend = FALSE) +
    geom_text(aes(x = 3.45, label = share_label), hjust = 1, size = 3.8,
              color = "grey25", show.legend = FALSE) +
    annotate("text", x = 3.45, y = 4.65, label = "2019 to 2024 shares", hjust = 1,
             size = 3.8, fontface = "bold", color = "grey25") +
    scale_fill_manual(values = palette, guide = "none") +
    scale_x_continuous(limits = c(-1.5, 3.55), breaks = c(-1, 0, 1, 2), expand = c(0, 0)) +
    scale_y_discrete(expand = expansion(add = c(0.55, 0.9))) +
    labs(title = "Adults 65 and older became a larger share of the population",
      subtitle = "Change in population shares from 2019 to 2024",
      x = "Change in population share (percentage points)", y = "Age group",
      caption = paste0("IPUMS CPS, Census Bureau and BLS. Eligible civilians age 16+; WTFINL weights.\n",
                       "Each annual share is the average of 12 monthly weighted population shares.")) +
    common + theme(panel.grid.major.y = element_blank())
  long <- a$overall |> pivot_longer(c(observed, standardized), names_to = "series", values_to = "rate") |>
    group_by(series) |> mutate(change_pp = 100 * (rate - rate[YEAR == 2019])) |> ungroup() |>
    mutate(series = recode(series, observed = "Observed age mix", standardized = "Fixed 2019 age mix"))
  p3 <- ggplot(long, aes(YEAR, change_pp, color = series, linetype = series)) +
    geom_hline(yintercept = 0, color = "grey70") + geom_line(linewidth = 1) + geom_point(size = 2.3) +
    scale_color_manual(values = c("Observed age mix" = "#0072B2", "Fixed 2019 age mix" = "#D55E00")) +
    scale_x_continuous(breaks = 2019:2024) +
    labs(title = "Separating participation from changes in the age mix", subtitle = "Change in overall participation from 2019", x = NULL, y = "Change (percentage points)", color = NULL, linetype = NULL,
      caption = paste0(caption, "\nStandardization fixes four age-group shares to the corresponding calendar month in 2019.")) + common
  list(trends = p1, age_shares = p2, age_mix = p3)
}

run_analysis <- function(root = ".", from_aggregates = FALSE) {
  if (from_aggregates) {
    monthly <- read_csv(file.path(root, "results/tables/monthly.csv"), show_col_types = FALSE)
    audit <- read_csv(file.path(root, "results/tables/audit.csv"), show_col_types = FALSE)
    a <- summarize_monthly_cps(monthly, audit)
  } else {
    a <- analyze_cps(read_extract(file.path(root, "data/raw")))
  }
  dir.create(file.path(root, "results/tables"), recursive = TRUE, showWarnings = FALSE)
  dir.create(file.path(root, "results/figures"), recursive = TRUE, showWarnings = FALSE)
  # Preserve the input CSVs when reproducing from saved aggregates.
  tables_to_write <- if (from_aggregates) setdiff(names(a), c("monthly", "audit")) else names(a)
  for (name in tables_to_write) write_csv(a[[name]], file.path(root, "results/tables", paste0(name, ".csv")))
  plots <- make_figures(a)
  for (name in names(plots)) ggsave(file.path(root, "results/figures", paste0(name, ".png")), plots[[name]], width = 9, height = 6, dpi = 300)
  saveRDS(a, file.path(root, "results/analysis.rds"))
  writeLines(trimws(capture.output(sessionInfo()), which = "right"),
             file.path(root, "results/session-info.txt"))
  invisible(a)
}
