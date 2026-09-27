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
  if (nrow(monthly) != 72L * 4L || any(!is.finite(monthly$rate))) stop("Missing age-group/month cells.")
  stopifnot(all(monthly$rate >= 0 & monthly$rate <= 1))
  # Each month receives equal weight in the annual mean of monthly rates.
  # Counts are person-month observations, not distinct people.
  annual <- monthly |> group_by(YEAR, age_group) |>
    summarise(rate = mean(rate), n_person_months = sum(n), .groups = "drop")
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
  list(monthly = monthly, annual = annual, changes = changes, overall = overall, audit = audit)
}

make_figures <- function(a) {
  palette <- c("16-24" = "#0072B2", "25-54" = "#009E73", "55-64" = "#D55E00", "65+" = "#CC79A7")
  common <- theme_minimal(base_size = 13) + theme(panel.grid.minor = element_blank(),
    plot.title = element_text(face = "bold"), plot.caption = element_text(hjust = 0, size = 9), legend.position = "bottom")
  caption <- "Source: IPUMS CPS, Census Bureau and BLS. Civilians age 16+; WTFINL weights.\nAnnual means of 12 monthly rates; not seasonally adjusted."
  p1 <- ggplot(a$annual, aes(YEAR, 100 * rate, color = age_group, group = age_group)) +
    geom_line(linewidth = 0.9) + geom_point(size = 2.1) + facet_wrap(~age_group, ncol = 2) +
    scale_color_manual(values = palette, guide = "none") + scale_x_continuous(breaks = 2019:2024) +
    scale_y_continuous(limits = c(0, 100)) +
    labs(title = "Labor-force participation by age group", subtitle = "Labor-force participation, 2019-2024", x = NULL, y = "Share in the labor force (%)", caption = caption) + common
  p2 <- ggplot(a$changes, aes(change_pp, age_group, color = age_group)) +
    geom_vline(xintercept = 0, linetype = "dashed", color = "grey55") +
    geom_segment(aes(x = 0, xend = change_pp, yend = age_group), linewidth = 1) + geom_point(size = 3) +
    scale_color_manual(values = palette, guide = "none") +
    labs(title = "How far did participation move from its 2019 baseline?", subtitle = "2024 annual mean minus 2019 annual mean", x = "Change in participation (percentage points)", y = "Age group", caption = caption) + common
  long <- a$overall |> pivot_longer(c(observed, standardized), names_to = "series", values_to = "rate") |>
    group_by(series) |> mutate(change_pp = 100 * (rate - rate[YEAR == 2019])) |> ungroup() |>
    mutate(series = recode(series, observed = "Observed age mix", standardized = "Fixed 2019 age mix"))
  p3 <- ggplot(long, aes(YEAR, change_pp, color = series, linetype = series)) +
    geom_hline(yintercept = 0, color = "grey70") + geom_line(linewidth = 1) + geom_point(size = 2.3) +
    scale_color_manual(values = c("Observed age mix" = "#0072B2", "Fixed 2019 age mix" = "#D55E00")) +
    scale_x_continuous(breaks = 2019:2024) +
    labs(title = "Separating participation from changes in the age mix", subtitle = "Change in overall participation from 2019", x = NULL, y = "Change (percentage points)", color = NULL, linetype = NULL,
      caption = paste0(caption, "\nStandardization fixes four age-group shares to the corresponding calendar month in 2019.")) + common
  list(trends = p1, changes = p2, age_mix = p3)
}

run_analysis <- function(root = ".") {
  a <- analyze_cps(read_extract(file.path(root, "data/raw")))
  dir.create(file.path(root, "results/tables"), recursive = TRUE, showWarnings = FALSE)
  dir.create(file.path(root, "results/figures"), recursive = TRUE, showWarnings = FALSE)
  for (name in names(a)) write_csv(a[[name]], file.path(root, "results/tables", paste0(name, ".csv")))
  plots <- make_figures(a)
  for (name in names(plots)) ggsave(file.path(root, "results/figures", paste0(name, ".png")), plots[[name]], width = 9, height = 6, dpi = 300)
  saveRDS(a, file.path(root, "results/analysis.rds"))
  capture.output(sessionInfo(), file = file.path(root, "results/session-info.txt"))
  invisible(a)
}
