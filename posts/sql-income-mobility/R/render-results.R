#!/usr/bin/env Rscript
# Render figures and a readable report using saved aggregate tables only.
# Dependencies: base R and jsonlite (for the source analysis audit).

renderer_arg <- grep("^--file=", commandArgs(FALSE), value = TRUE)
renderer_path <- if (sys.nframe() > 0L) sys.frame(1L)$ofile else sub("^--file=", "", renderer_arg)
if (length(renderer_path) != 1L) stop("Run this script with Rscript.", call. = FALSE)
renderer_directory <- dirname(normalizePath(renderer_path, mustWork = TRUE))
source(file.path(renderer_directory, "validate-results.R"))

format_count <- function(x) format(x, big.mark = ",", scientific = FALSE, trim = TRUE)
format_ige <- function(x) sprintf("%.3f", x)
format_interval <- function(low, high) paste(format_ige(low), "to", format_ige(high))
measure <- function(data, key) data[match(key, data$measure), , drop = FALSE]
contrast <- function(data, key) data[match(key, data$comparison), , drop = FALSE]

draw_estimate_figure <- function(data, labels, title, subtitle, notes, path) {
  # Explicit margins keep titles, category labels and sample notes inside the PNG.
  png(path, width = 1600, height = 1000, res = 180, bg = "white")
  on.exit(dev.off(), add = TRUE)
  par(mar = c(5.4, 5.5, 5.4, 1.4), oma = c(3.1, 0, 0, 0), family = "sans", las = 1,
      fg = "#34434B", col.axis = "#34434B", col.lab = "#34434B")
  x <- seq_len(nrow(data))
  limits <- c(min(0, min(data$ci_lower) - 0.035), max(data$ci_upper) + 0.085)
  plot(x, data$ige, type = "n", xlim = c(0.5, length(x) + 0.5), ylim = limits,
       axes = FALSE, xlab = "", ylab = "Intergenerational family income elasticity", cex.lab = 1.03)
  ticks <- pretty(limits, n = 6L)
  ticks <- ticks[ticks >= limits[1L] & ticks <= limits[2L]]
  abline(h = ticks, col = "#E5EBEE", lwd = 0.9)
  axis(2, at = ticks, labels = sprintf("%.1f", ticks), tick = FALSE, cex.axis = 1.0)
  axis(1, at = x, labels = labels, tick = FALSE, line = 0.6, cex.axis = 0.96)
  segments(x, data$ci_lower, x, data$ci_upper, col = "#28718C", lwd = 2.3)
  segments(x - 0.055, data$ci_lower, x + 0.055, data$ci_lower, col = "#28718C", lwd = 1.4)
  segments(x - 0.055, data$ci_upper, x + 0.055, data$ci_upper, col = "#28718C", lwd = 1.4)
  points(x, data$ige, pch = 21, bg = "#14506A", col = "white", cex = 1.65, lwd = 1.2)
  text(x + 0.10, data$ige + 0.012, format_ige(data$ige), adj = c(0, 0), cex = 1.0, col = "#14506A")
  mtext(title, side = 3L, line = 3.0, adj = 0, font = 2L, cex = 1.20, col = "#163B4B")
  mtext(subtitle, side = 3L, line = 1.45, adj = 0, cex = 0.88, col = "#52636C")
  mtext(notes, side = 1L, outer = TRUE, line = 0.7, adj = 0.055, cex = 0.79, col = "#52636C")
}

make_figures <- function(results, output) {
  main_keys <- c("one_year_each", "averaged_parent_one_year_child", "averaged_each_age40_44")
  main <- results$estimates[match(main_keys, results$estimates$measure), ]
  notes <- paste0("Same ", format_count(main$children[1L]), " children; unweighted PSID sample.\n",
                  "Lines show 95% intervals from resampling families of origin.")
  draw_estimate_figure(main, c("One observation\neach generation", "Average parents,\none child observation", "Average both\ngenerations"),
                       "How income averaging changes the estimate", "Adult child income measured at ages 40 to 44", notes,
                       file.path(output, "income-averages.png"))
  age <- results$lifecycle_coverage
  labels <- paste0("About age ", (age$age_start + age$age_end) / 2L, "\n(", age$age_start, " to ", age$age_end, ")")
  notes <- paste0("Same ", format_count(results$lifecycle$children[1L]), " children and parental income average at every age.\n",
                  "Unweighted PSID sample. Lines show 95% intervals from resampling families of origin.")
  draw_estimate_figure(results$lifecycle, labels, "One income observation at each career stage",
                       "One adult child observation per age window; fixed parental income average", notes,
                       file.path(output, "child-age.png"))
}

markdown_table <- function(headers, rows) {
  paste(c(paste0("| ", paste(headers, collapse = " | "), " |"),
          paste0("| ", paste(rep("---", length(headers)), collapse = " | "), " |"),
          apply(rows, 1L, function(row) paste0("| ", paste(row, collapse = " | "), " |"))), collapse = "\n")
}

write_report <- function(results, output, include_figures = TRUE) {
  main <- results$estimates
  single <- measure(main, "one_year_each")
  parent_only <- measure(main, "averaged_parent_one_year_child")
  averaged <- measure(main, "averaged_each_age40_44")
  difference <- contrast(results$contrasts, "averaged_each_age40_44 minus one_year_each")
  lifecycle <- results$lifecycle
  averages <- results$lifecycle_averages
  age <- results$lifecycle_coverage
  lifecycle_difference <- contrast(results$lifecycle_contrasts,
                                   "child_single_age40_44 minus child_single_age25_29")
  endpoint_text <- if (lifecycle_difference$ci_lower <= 0 && lifecycle_difference$ci_upper >= 0)
    "The interval includes zero, so this comparison does not clearly distinguish the endpoint difference from zero."
  else "The interval excludes zero in this retained sample."
  if (any(diff(lifecycle$ige) > 0) && any(diff(lifecycle$ige) < 0))
    endpoint_text <- paste(endpoint_text, "The sequence is not monotonic across these age windows.")
  metadata <- results$metadata
  main_keys <- c("one_year_each", "averaged_parent_one_year_child", "averaged_each_age40_44")
  rows <- main[match(main_keys, main$measure), ]
  main_table <- markdown_table(c("Income measure", "Estimated IGE", "95% family bootstrap interval"), cbind(
    c("One observation for each generation", "Average parental income, one child observation", "Average both generations"),
    format_ige(rows$ige), format_interval(rows$ci_lower, rows$ci_upper)))
  lifecycle_table <- markdown_table(c("Adult child age window", "One child observation: IGE", "95% family bootstrap interval", "Average child income: IGE"),
    cbind(paste(age$age_start, "to", age$age_end), format_ige(lifecycle$ige),
          format_interval(lifecycle$ci_lower, lifecycle$ci_upper), format_ige(averages$ige)))
  coverage_table <- markdown_table(c("Adult child age window", "Mean selected age", "Income years"), cbind(
    paste(age$age_start, "to", age$age_end), sprintf("%.2f", age$mean_selected_age),
    paste(age$first_income_year, "to", age$last_income_year)))
  sensitivity <- results$sensitivity
  sensitivity_text <- paste0("With the linear cohort and sex adjustment on the same main sample, the one-observation and averaged estimates are ",
                              format_ige(single$cohort_sex_adjusted_ige), " and ", format_ige(averaged$cohort_sex_adjusted_ige), ".")
  if (nrow(sensitivity)) {
    sensitivity_single <- measure(sensitivity, "one_year_each")
    sensitivity_average <- measure(sensitivity, "averaged_each_age40_44")
    sensitivity_text <- paste0(sensitivity_text, " Restricting to consistent age histories retains ",
      format_count(sensitivity_single$children), " children; those two estimates are ", format_ige(sensitivity_single$ige),
      " and ", format_ige(sensitivity_average$ige), ".")
  } else {
    sensitivity_text <- paste(sensitivity_text, "The age-quality restriction did not retain enough children to estimate that sensitivity.")
  }
  parent_coverage <- measure(results$coverage, "parent_15_19")
  main_child_coverage <- measure(results$coverage, "child_40_44")
  paragraphs <- c(
    "# Real PSID results for Blog Post 6",
    paste0("The income averaging comparison uses the same **", format_count(single$children), " adult children** from **",
           format_count(single$origin_family_clusters), " families of origin** in every specification. The career-stage comparison uses its own common sample of **",
           format_count(lifecycle$children[1L]), " adult children** from **", format_count(lifecycle$origin_family_clusters[1L]),
           " families of origin**, with positive single-observation income at every stage. Estimates are unweighted and describe the retained PSID sample."),
    "## Income averaging",
    "Adult child income is measured at ages 40 to 44 in all three specifications.",
    main_table,
    paste0("Averaging income for both generations changes the IGE from ", format_ige(single$ige), " to ", format_ige(averaged$ige),
           ". The paired difference is ", format_ige(difference$ige_difference), ", with a 95% family bootstrap interval of ",
           format_interval(difference$ci_lower, difference$ci_upper), ". Averaging parental income alone gives ", format_ige(parent_only$ige),
           ". Averaging adult child income as well gives a ", if (averaged$ige < parent_only$ige) "lower" else "higher", " point estimate than that intermediate specification."),
    paste0("Parental averages contain ", format_count(parent_coverage$min_observations), " to ", format_count(parent_coverage$max_observations),
           " observations per child (median ", format_count(parent_coverage$median_observations), "). Mature adult child averages contain ",
           format_count(main_child_coverage$min_observations), " to ", format_count(main_child_coverage$max_observations), " observations (median ",
           format_count(main_child_coverage$median_observations), ")."),
    if (include_figures) "![Income averaging comparison](income-averages.png)" else NULL,
    "## One observation at each career stage",
    "Each estimate uses one selected adult child income observation from its age window and the same parental income average. Selection is nearest the midpoint of the age window, with the earlier income year breaking ties. The child sample is held fixed across all four windows. The final column also averages child income within each window on this same career-stage sample, so the one-observation and average columns can be compared within a window.",
    lifecycle_table,
    paste0("Holding the parental income average fixed, the one-observation IGE is ", format_ige(lifecycle$ige[1L]), " at ages ",
           age$age_start[1L], " to ", age$age_end[1L], " and ", format_ige(lifecycle$ige[4L]), " at ages ", age$age_start[4L], " to ", age$age_end[4L],
           ". The paired difference is ", format_ige(lifecycle_difference$ige_difference), ", with a 95% family bootstrap interval of ",
           format_interval(lifecycle_difference$ci_lower, lifecycle_difference$ci_upper), ". ", endpoint_text),
    if (include_figures) "![One adult child income observation at each career stage](child-age.png)" else NULL,
    coverage_table,
    "The comparison holds the number of selected child observations at one per stage. Calendar period and family circumstances still change with age. It does not identify a true lifetime IGE or the amount of lifecycle bias.",
    "## Checks and limitations",
    "A higher IGE means a stronger association between parental and adult child family income. It is not the causal effect of giving parents more money.",
    paste0("Confidence intervals use ", format_count(metadata$bootstrap_repetitions), " paired bootstrap draws that resample families of origin. The same draw is used across specifications within each comparison. Separate family-cluster standard errors are saved in the aggregate tables."),
    paste0("Income is converted to ", metadata$dollar_base_year, " dollars before averaging. Parental income is measured in the child's co-resident family at approximate ages ",
           metadata$parent_income_ages[1L], " to ", metadata$parent_income_ages[2L], ". Adult child income requires reference person or spouse/partner status. Family membership is observed at interview, while income covers the previous calendar year."),
    "Survey weights were not supplied. The sample requires linked parents and repeated observations, so it does not represent all US children. The income measure is family income, rather than personal earnings.",
    sensitivity_text,
    "The source analysis checks compound identifiers, household income consistency, foreign keys, identical samples and positive finite regression inputs. It also verifies the simple OLS slope against an independent covariance calculation. The R aggregate check independently verifies measure keys, counts, finite estimates and intervals, paired differences, age coverage and wave totals before rendering this report.",
    "Only aggregate results and figures are saved. The normalized tables and matched records stay in memory. [Replication details](../../README-real.md).")
  writeLines(paste(paragraphs, collapse = "\n\n"), file.path(output, "REPORT.md"), useBytes = TRUE)
}

if (sys.nframe() == 0L) {
  args <- result_arguments(commandArgs(TRUE), renderer_directory, figures = TRUE)
  results <- read_aggregate_results(args$output)
  if (!args$no_figures) make_figures(results, args$output)
  write_report(results, args$output, include_figures = !args$no_figures)
  writeLines(trimws(capture.output(sessionInfo()), which = "right"),
             file.path(args$output, "r-environment.txt"))
  cat("Aggregate checks passed. Saved REPORT.md", if (!args$no_figures) "and two figures", "in", args$output, "\n")
}
