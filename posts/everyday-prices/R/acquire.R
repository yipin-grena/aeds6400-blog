# Download only public aggregate CPI series. Preserve one complete retrieval batch.
acquire_cpi <- function(post_dir, series) {
  if (!requireNamespace("jsonlite", quietly = TRUE)) stop("Install jsonlite first.")
  raw_dir <- file.path(post_dir, "data", "raw")
  dir.create(raw_dir, recursive = TRUE, showWarnings = FALSE)
  staging <- tempfile("cpi-download-")
  dir.create(staging)
  on.exit(unlink(staging, recursive = TRUE), add = TRUE)
  records <- vector("list", nrow(series))
  for (i in seq_len(nrow(series))) {
    id <- series$series_id[i]
    url <- paste0("https://fred.stlouisfed.org/graph/fredgraph.csv?id=", id,
                  "&cosd=2018-12-01&coed=2024-12-01")
    path <- file.path(staging, paste0(id, ".csv"))
    status <- utils::download.file(url, path, mode = "wb", quiet = FALSE)
    if (status != 0) stop("Download failed: ", id)
    x <- read.csv(path, stringsAsFactors = FALSE, check.names = FALSE)
    if (!identical(names(x), c("observation_date", id)) || nrow(x) == 0L) {
      stop("Unexpected download schema: ", id)
    }
    dates <- as.Date(x$observation_date)
    expected <- seq(as.Date("2018-12-01"), as.Date("2024-12-01"), by = "month")
    values <- suppressWarnings(as.numeric(x[[id]]))
    if (anyNA(dates) || anyDuplicated(dates) || !identical(dates, expected) ||
        any(!is.finite(values) | values <= 0)) stop("Invalid snapshot: ", id)
    records[[i]] <- list(series_id = id, label = series$label[i], url = url,
                         retrieved_utc = format(Sys.time(), "%Y-%m-%dT%H:%M:%SZ", tz = "UTC"),
                         file = paste0(id, ".csv"),
                         md5 = unname(tools::md5sum(path)), rows = nrow(x))
  }
  # No new batch replaces the old files until every response has passed checks.
  for (r in records) {
    if (!file.copy(file.path(staging, r$file), file.path(raw_dir, r$file), overwrite = TRUE)) {
      stop("Could not save snapshot: ", r$file)
    }
  }
  jsonlite::write_json(list(source = "U.S. Bureau of Labor Statistics via FRED",
    frequency = "monthly", seasonal_adjustment = "not seasonally adjusted",
    original_units = "Index 1982-1984 = 100", files = records),
    file.path(raw_dir, "provenance.json"), pretty = TRUE, auto_unbox = TRUE)
}
