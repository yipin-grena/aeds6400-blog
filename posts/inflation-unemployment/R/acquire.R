# Public FRED CSV endpoint; no API key is needed. Refresh is explicit.
acquire_data <- function(root, refresh = FALSE) {
  ids <- c("CPIAUCSL", "UNRATE")
  raw_dir <- file.path(root, "data/raw")
  dir.create(raw_dir, recursive = TRUE, showWarnings = FALSE)
  if (!refresh && all(file.exists(file.path(raw_dir, paste0(ids, ".csv"))))) return(invisible(NULL))
  if (!refresh) stop("Snapshot incomplete. Run with --refresh to download all series.")
  metadata <- lapply(ids, function(id) {
    url <- paste0("https://fred.stlouisfed.org/graph/fredgraph.csv?id=", id, "&cosd=2014-01-01&coed=2024-12-01")
    dest <- file.path(raw_dir, paste0(id, ".csv"))
    download.file(url, dest, mode = "wb", method = "libcurl", quiet = TRUE)
    x <- read.csv(dest, na.strings = c(".", ""))
    stopifnot(id %in% names(x), nrow(x) > 0)
    data.frame(series_id = id, url = url, retrieved_utc = format(Sys.time(), tz = "UTC", usetz = TRUE),
      md5 = unname(tools::md5sum(dest)))
  })
  write.csv(do.call(rbind, metadata), file.path(raw_dir, "provenance.csv"), row.names = FALSE)
}
