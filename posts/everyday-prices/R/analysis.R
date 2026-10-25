analyze_cpi <- function(post_dir, series) {
  if (!requireNamespace("jsonlite", quietly = TRUE)) stop("Install jsonlite first.")
  stopifnot(nrow(series) == 6L, !anyDuplicated(series$series_id), !anyDuplicated(series$label))
  raw_dir <- file.path(post_dir, "data", "raw")
  manifest_path <- file.path(raw_dir, "provenance.json")
  if (!file.exists(manifest_path)) stop("Snapshots missing. First run: Rscript run.R --refresh")
  manifest <- jsonlite::fromJSON(manifest_path)
  if (!setequal(manifest$files$series_id, series$series_id)) stop("Snapshot manifest IDs differ.")
  expected_dates <- seq(as.Date("2018-12-01"), as.Date("2024-12-01"), by = "month")
  baseline <- as.Date("2019-12-01")
  end <- as.Date("2024-12-01")
  data <- vector("list", nrow(series))
  audit <- vector("list", nrow(series))
  for (i in seq_len(nrow(series))) {
    id <- series$series_id[i]
    row <- manifest$files[manifest$files$series_id == id, ]
    if (nrow(row) != 1L) stop("Duplicate manifest ID: ", id)
    path <- file.path(raw_dir, paste0(id, ".csv"))
    if (!file.exists(path) || unname(tools::md5sum(path)) != row$md5) stop("Snapshot checksum differs: ", id)
    raw <- read.csv(path, stringsAsFactors = FALSE, check.names = FALSE)
    if (!identical(names(raw), c("observation_date", id))) stop("Unexpected columns: ", id)
    dates <- as.Date(raw$observation_date)
    if (anyNA(dates) || anyDuplicated(dates) || !identical(dates, expected_dates)) {
      stop("Dates must be a unique, ordered, complete monthly calendar: ", id)
    }
    index <- suppressWarnings(as.numeric(raw[[id]]))
    if (any(!is.finite(index) | index <= 0)) stop("Missing or invalid CPI index: ", id)
    baseline_index <- index[dates == baseline]
    # Explicit month keys prevent a missing month from turning a 12-row lag into a different interval.
    month_key <- as.integer(format(dates, "%Y")) * 12L + as.integer(format(dates, "%m"))
    prior <- match(month_key - 12L, month_key)
    annual <- 100 * (index / index[prior] - 1)
    cumulative <- 100 * (index / baseline_index - 1)
    keep <- dates >= baseline & dates <= end
    if (anyNA(annual[keep])) stop("Missing prior-year match in displayed window: ", id)
    data[[i]] <- data.frame(series_id = id, label = series$label[i], date = dates[keep],
      index = index[keep], baseline_index = baseline_index,
      cumulative_pct = cumulative[keep], annual_pct = annual[keep])
    audit[[i]] <- data.frame(series_id = id, raw_rows = nrow(raw),
      duplicate_dates = anyDuplicated(dates), missing_values = sum(is.na(index)),
      displayed_months = sum(keep), checksum_match = TRUE,
      baseline_cumulative_pct = cumulative[dates == baseline])
  }
  monthly <- do.call(rbind, data)
  audit <- do.call(rbind, audit)
  stopifnot(nrow(monthly) == 366L, all(audit$displayed_months == 61L),
    all(audit$baseline_cumulative_pct == 0),
    !anyDuplicated(monthly[c("series_id", "date")]),
    all(is.finite(monthly$cumulative_pct)), all(is.finite(monthly$annual_pct)))
  endpoint <- monthly[monthly$date == end, c("series_id", "label", "cumulative_pct", "annual_pct")]
  endpoint$category_rank <- NA_integer_
  cats <- endpoint$label != "Overall CPI"
  endpoint$category_rank[cats] <- rank(-endpoint$cumulative_pct[cats], ties.method = "min")
  peak_annual <- do.call(rbind, lapply(split(monthly, monthly$series_id), function(x) {
    z <- x[which.max(x$annual_pct), ]
    data.frame(series_id = z$series_id, label = z$label, peak_date = z$date, peak_annual_pct = z$annual_pct)
  }))
  gas <- monthly[monthly$label == "Gasoline", ]
  gas_peak <- gas[which.max(gas$index), ]
  groceries <- monthly[monthly$label == "Groceries", ]
  grocery_peak_rate <- groceries[which.max(groceries$annual_pct), ]
  december <- monthly[format(monthly$date, "%m") == "12", ]
  # Endpoint sensitivity: compare the ordering at the end of 2023 and 2024.
  sensitivity <- december[december$date %in% as.Date(c("2023-12-01", "2024-12-01")), ]
  sensitivity$category_rank <- NA_integer_
  for (d in unique(sensitivity$date)) {
    idx <- sensitivity$date == d & sensitivity$label != "Overall CPI"
    sensitivity$category_rank[idx] <- rank(-sensitivity$cumulative_pct[idx], ties.method = "min")
  }
  summary <- list(baseline = as.character(baseline), endpoint = as.character(end),
    categories = 5L, months_per_series = 61L, series = endpoint,
    gas_peak_date = as.character(gas_peak$date),
    gas_fall_from_peak_pct = 100 * (tail(gas$index, 1) / gas_peak$index - 1),
    grocery_peak_inflation_date = as.character(grocery_peak_rate$date),
    grocery_peak_inflation_pct = grocery_peak_rate$annual_pct,
    grocery_change_after_peak_inflation_pct = 100 * (tail(groceries$index, 1) / grocery_peak_rate$index - 1),
    peak_annual_inflation = peak_annual)
  result_dir <- file.path(post_dir, "results")
  dir.create(file.path(result_dir, "tables"), recursive = TRUE, showWarnings = FALSE)
  write.csv(monthly, file.path(result_dir, "tables", "monthly.csv"), row.names = FALSE)
  write.csv(endpoint, file.path(result_dir, "tables", "endpoint.csv"), row.names = FALSE)
  write.csv(peak_annual, file.path(result_dir, "tables", "peak-annual-inflation.csv"), row.names = FALSE)
  write.csv(audit, file.path(result_dir, "tables", "audit.csv"), row.names = FALSE)
  write.csv(sensitivity, file.path(result_dir, "tables", "endpoint-sensitivity.csv"), row.names = FALSE)
  jsonlite::write_json(summary, file.path(result_dir, "summary.json"), pretty = TRUE, auto_unbox = TRUE, digits = 12)
  jsonlite::write_json(list(source_files = 6L, raw_months_per_series = 73L,
    displayed_rows = nrow(monthly), missing_displayed_values = sum(!is.finite(monthly$index)),
    unique_series_month_keys = TRUE, complete_monthly_calendars = TRUE,
    twelve_month_matches_verified = TRUE, snapshot_md5_verified = TRUE),
    file.path(result_dir, "validation.json"), pretty = TRUE, auto_unbox = TRUE)
  list(monthly = monthly, summary = summary)
}
