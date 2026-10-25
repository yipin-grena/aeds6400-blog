#!/usr/bin/env Rscript
# Run from any working directory; install dependencies as described in README.md.
args <- commandArgs(trailingOnly = FALSE)
script <- sub("^--file=", "", args[grepl("^--file=", args)])
if (length(script) != 1L) stop("Run this entry point with Rscript.")
post_dir <- dirname(normalizePath(script))
if (!rmarkdown::pandoc_available()) {
  stop("Pandoc is required to save self-contained HTML. See README.md for Quarto/Pandoc setup.")
}
source(file.path(post_dir, "R", "acquire.R"))
source(file.path(post_dir, "R", "analysis.R"))
source(file.path(post_dir, "R", "figure.R"))
refresh <- "--refresh" %in% commandArgs(trailingOnly = TRUE)
series <- read.csv(file.path(post_dir, "config", "series.csv"), stringsAsFactors = FALSE)
if (refresh) acquire_cpi(post_dir, series)
results <- analyze_cpi(post_dir, series)
widget <- make_price_figure(results$monthly, series)
widget_dependencies <- tempfile("price-explorer-dependencies-", tmpdir = file.path(post_dir, "results"))
tryCatch(
  htmlwidgets::saveWidget(widget, file.path(post_dir, "results", "price-explorer.html"),
                          selfcontained = TRUE, libdir = widget_dependencies),
  finally = unlink(widget_dependencies, recursive = TRUE)
)
writeLines(capture.output(sessionInfo()), file.path(post_dir, "results", "session-info.txt"))
message("Saved validated results and interactive figure. No website build or publication performed.")
