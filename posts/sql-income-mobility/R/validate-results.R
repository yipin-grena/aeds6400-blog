#!/usr/bin/env Rscript
# Independently check saved aggregate results. No respondent records are read.

check <- function(ok, message) {
  if (!isTRUE(ok)) stop(message, call. = FALSE)
}

script_directory <- function() {
  arg <- grep("^--file=", commandArgs(FALSE), value = TRUE)
  check(length(arg) == 1L, "Run this script with Rscript.")
  dirname(normalizePath(sub("^--file=", "", arg), mustWork = TRUE))
}

result_arguments <- function(args, directory, figures = FALSE) {
  output <- file.path(directory, "..", "results", "real")
  no_figures <- FALSE
  while (length(args)) {
    flag <- args[1L]
    args <- args[-1L]
    if (flag == "--output") {
      check(length(args) > 0L && !startsWith(args[1L], "--"), "--output needs a path.")
      output <- args[1L]
      args <- args[-1L]
    } else if (flag == "--no-figures" && figures) {
      no_figures <- TRUE
    } else if (flag %in% c("--help", "-h")) {
      cat("Usage: Rscript", if (figures) "R/render-results.R" else "R/validate-results.R",
          "[--output PATH]", if (figures) "[--no-figures]" else "", "\n")
      quit(status = 0L)
    } else {
      stop(paste("Unknown argument:", flag), call. = FALSE)
    }
  }
  list(output = normalizePath(output, mustWork = TRUE), no_figures = no_figures)
}

read_table <- function(output, name, columns, key) {
  path <- file.path(output, paste0(name, ".csv"))
  check(file.exists(path), paste("Missing aggregate input:", basename(path)))
  data <- read.csv(path, stringsAsFactors = FALSE, check.names = FALSE)
  check(all(columns %in% names(data)), paste("Missing columns in", basename(path)))
  check(!anyNA(data[key]) && !anyDuplicated(data[key]), paste("Missing or duplicate keys in", basename(path)))
  data
}

finite_columns <- function(data, columns, label) {
  check(all(vapply(data[columns], is.numeric, logical(1L))), paste("Nonnumeric values in", label))
  check(all(is.finite(as.matrix(data[columns]))), paste("Nonfinite values in", label))
}

integer_counts <- function(values, label, minimum = 0L) {
  check(length(values) > 0L && all(is.finite(values) & values >= minimum & values == floor(values)),
        paste("Invalid counts in", label))
}

same_keys <- function(values, expected, label) {
  check(setequal(values, expected), paste("Unexpected measure keys in", label))
}

validate_estimates <- function(data, keys, label) {
  same_keys(data$measure, keys, label)
  numeric <- setdiff(names(data), "measure")
  finite_columns(data, numeric, label)
  integer_counts(data$children, label, 1L)
  integer_counts(data$origin_family_clusters, label, 2L)
  check(all(data$origin_family_clusters <= data$children), paste("Clusters exceed children in", label))
  check(length(unique(data$children)) == 1L && length(unique(data$origin_family_clusters)) == 1L,
        paste("Samples differ within", label))
  check(all(data$cluster_se >= 0 & data$cohort_sex_adjusted_cluster_se >= 0),
        paste("Negative standard errors in", label))
  check(all(data$ci_lower <= data$ci_upper), paste("Reversed intervals in", label))
}

validate_contrasts <- function(data, estimates, label, required) {
  check(setequal(required, data$comparison), paste("Unexpected or missing paired comparison in", label))
  finite_columns(data, c("ige_difference", "ci_lower", "ci_upper"), label)
  check(all(data$ci_lower <= data$ci_upper), paste("Reversed intervals in", label))
  for (i in seq_len(nrow(data))) {
    keys <- strsplit(data$comparison[i], " minus ", fixed = TRUE)[[1L]]
    check(length(keys) == 2L && all(keys %in% estimates$measure), paste("Unknown contrast keys in", label))
    slopes <- estimates$ige[match(keys, estimates$measure)]
    check(abs(data$ige_difference[i] - (slopes[1L] - slopes[2L])) < 1e-10,
          paste("Contrast does not match estimates in", label))
  }
}

read_aggregate_results <- function(output) {
  check(requireNamespace("jsonlite", quietly = TRUE), "Install the jsonlite R package to read validation.json.")
  age_start <- c(25L, 30L, 35L, 40L)
  age_end <- age_start + 4L
  lifecycle_keys <- paste0("child_single_age", age_start, "_", age_end)
  lifecycle_average_keys <- paste0("child_average_age", age_start, "_", age_end)
  main_keys <- c("one_year_each", "averaged_parent_one_year_child", "averaged_each_age40_44",
                 paste0("averaged_each_age", age_start[1:3], "_", age_end[1:3]))
  estimate_columns <- c("measure", "children", "origin_family_clusters", "ige", "cluster_se",
                        "ci_lower", "ci_upper", "cohort_sex_adjusted_ige", "cohort_sex_adjusted_cluster_se")
  estimates <- read_table(output, "estimates", estimate_columns, "measure")
  lifecycle <- read_table(output, "lifecycle-estimates", estimate_columns, "measure")
  lifecycle_averages <- read_table(output, "lifecycle-averages", estimate_columns, "measure")
  validate_estimates(estimates, main_keys, "estimates.csv")
  validate_estimates(lifecycle, lifecycle_keys, "lifecycle-estimates.csv")
  validate_estimates(lifecycle_averages, lifecycle_average_keys, "lifecycle-averages.csv")
  lifecycle <- lifecycle[match(lifecycle_keys, lifecycle$measure), ]
  lifecycle_averages <- lifecycle_averages[match(lifecycle_average_keys, lifecycle_averages$measure), ]
  check(all(lifecycle$children == lifecycle_averages$children) &&
          all(lifecycle$origin_family_clusters == lifecycle_averages$origin_family_clusters),
        "Single observations and lifecycle averages have different samples.")

  contrast_columns <- c("comparison", "ige_difference", "ci_lower", "ci_upper")
  contrasts <- read_table(output, "contrasts", contrast_columns, "comparison")
  lifecycle_contrasts <- read_table(output, "lifecycle-contrasts", contrast_columns, "comparison")
  validate_contrasts(contrasts, estimates, "contrasts.csv", c(
    "averaged_parent_one_year_child minus one_year_each", "averaged_each_age40_44 minus one_year_each",
    "averaged_each_age40_44 minus averaged_each_age25_29"))
  validate_contrasts(lifecycle_contrasts, rbind(lifecycle, lifecycle_averages), "lifecycle-contrasts.csv",
                     c(paste(lifecycle_keys[4L], "minus", lifecycle_keys[1L]),
                       paste(lifecycle_average_keys[4L], "minus", lifecycle_average_keys[1L]),
                       paste(lifecycle_average_keys, "minus", lifecycle_keys)))

  coverage_columns <- c("measure", "children", "min_observations", "median_observations", "max_observations",
                         "mean_measurement_age", "mean_single_measurement_age", "earliest_income_year", "latest_income_year")
  coverage <- read_table(output, "coverage", coverage_columns, "measure")
  same_keys(coverage$measure, c("parent_15_19", paste0("child_", age_start, "_", age_end)), "coverage.csv")
  finite_columns(coverage, setdiff(coverage_columns, "measure"), "coverage.csv")
  integer_counts(as.matrix(coverage[c("children", "min_observations", "max_observations")]), "coverage.csv", 1L)
  check(all(coverage$children == estimates$children[1L]), "Coverage and main sample counts disagree.")
  check(all(coverage$min_observations <= coverage$median_observations &
              coverage$median_observations <= coverage$max_observations), "Inconsistent observation coverage.")
  check(all(coverage$earliest_income_year <= coverage$latest_income_year), "Reversed income year coverage.")
  lifecycle_coverage_columns <- c("age_start", "age_end", "children", "min_selected_age", "mean_selected_age",
                                  "max_selected_age", "first_income_year", "last_income_year")
  lifecycle_coverage <- read_table(output, "lifecycle-coverage", lifecycle_coverage_columns, "age_start")
  finite_columns(lifecycle_coverage, lifecycle_coverage_columns, "lifecycle-coverage.csv")
  same_keys(lifecycle_coverage$age_start, age_start, "lifecycle-coverage.csv")
  lifecycle_coverage <- lifecycle_coverage[match(age_start, lifecycle_coverage$age_start), ]
  integer_counts(as.matrix(lifecycle_coverage[c("children", "first_income_year", "last_income_year")]),
                 "lifecycle-coverage.csv", 1L)
  check(all(lifecycle_coverage$age_end == age_end) && all(lifecycle_coverage$children == lifecycle$children),
        "Lifecycle coverage windows or sample counts disagree.")
  check(all(lifecycle_coverage$age_start <= lifecycle_coverage$min_selected_age &
              lifecycle_coverage$min_selected_age <= lifecycle_coverage$mean_selected_age &
              lifecycle_coverage$mean_selected_age <= lifecycle_coverage$max_selected_age &
              lifecycle_coverage$max_selected_age <= lifecycle_coverage$age_end),
        "Selected lifecycle ages fall outside their window.")
  check(all(lifecycle_coverage$first_income_year <= lifecycle_coverage$last_income_year),
        "Reversed lifecycle income year coverage.")

  sensitivity <- read_table(output, "age-quality-sensitivity",
                            c("restriction", "measure", "children", "origin_family_clusters", "ige", "cluster_se"), "measure")
  if (nrow(sensitivity)) {
    same_keys(sensitivity$measure, main_keys, "age-quality-sensitivity.csv")
    finite_columns(sensitivity, c("children", "origin_family_clusters", "ige", "cluster_se"), "age-quality-sensitivity.csv")
    integer_counts(sensitivity$children, "age-quality-sensitivity.csv", 1L)
    integer_counts(sensitivity$origin_family_clusters, "age-quality-sensitivity.csv", 2L)
    check(length(unique(sensitivity$children)) == 1L && all(sensitivity$children <= estimates$children[1L]) &&
            all(sensitivity$origin_family_clusters <= sensitivity$children) && all(sensitivity$cluster_se >= 0),
          "Inconsistent age-quality sensitivity counts or errors.")
  }
  flow <- read_table(output, "sample-flow", c("stage", "children"), "stage")
  integer_counts(flow$children, "sample-flow.csv")
  main_stage <- match("Final common sample with positive single-year incomes", flow$stage)
  check(!is.na(main_stage) && flow$children[main_stage] == estimates$children[1L], "Main sample flow count disagrees.")
  waves <- read_table(output, "wave-validation", c("survey_year", "income_year", "current_members", "family_units",
                      "income_missing_or_out_of_range", "bottomcoded_income_excluded", "topcoded_income_retained_at_cap",
                      "valid_nonpositive_income", "missing_person_age", "conflicting_family_incomes"), "survey_year")
  finite_columns(waves, names(waves), "wave-validation.csv")
  integer_counts(as.matrix(waves), "wave-validation.csv")
  check(all(waves$income_year == waves$survey_year - 1L) && all(waves$conflicting_family_incomes == 0L),
        "Invalid income timing or unresolved family income conflicts.")
  metadata_path <- file.path(output, "validation.json")
  check(file.exists(metadata_path), "Missing aggregate input: validation.json")
  metadata <- jsonlite::fromJSON(metadata_path)
  audit <- metadata$validation
  check(is.list(audit), "Missing validation audit in validation.json.")
  for (name in c("family_income_conflicts", "duplicate_person_years", "duplicate_family_years"))
    check(isTRUE(audit[[name]] == 0L), paste("Unresolved audit count:", name))
  check(sum(waves$current_members) == audit$person_years_rows && sum(waves$family_units) == audit$family_years_rows,
        "Wave totals do not match normalized table counts.")
  check(isTRUE(metadata$checks$common_sample_across_specifications) &&
          isTRUE(metadata$checks$positive_finite_regression_inputs) &&
          isTRUE(metadata$checks$simple_ols_independently_verified) && isTRUE(metadata$checks$foreign_keys_valid) &&
          identical(metadata$checks$respondent_level_outputs_saved, FALSE), "Required source analysis checks did not pass.")
  integer_counts(metadata$bootstrap_repetitions, "bootstrap repetitions", 200L)
  check(all(coverage$min_observations[coverage$measure == "parent_15_19"] >= metadata$parent_min_observations) &&
          all(coverage$min_observations[coverage$measure != "parent_15_19"] >= metadata$child_min_observations),
        "Income coverage does not meet the stated minimum observation counts.")
  for (sample in c("main", "lifecycle")) {
    covariates <- metadata$covariates[[sample]]
    expected <- if (sample == "main") estimates$children[1L] else lifecycle$children[1L]
    required_counts <- c("children", "birth_year_proxy_nonmissing", "sex_known", "sex_missing", "female_children")
    check(is.list(covariates) && all(required_counts %in% names(covariates)),
          paste("Missing covariate counts for", sample))
    integer_counts(unlist(covariates[required_counts]), paste(sample, "covariates"))
    check(covariates$children == expected && covariates$birth_year_proxy_nonmissing == expected &&
            covariates$sex_known + covariates$sex_missing == expected &&
            covariates$female_children <= covariates$sex_known, paste("Inconsistent covariate counts for", sample))
  }
  check(is.list(metadata$lifecycle) && metadata$lifecycle$children == lifecycle$children[1L] &&
          metadata$lifecycle$origin_family_clusters == lifecycle$origin_family_clusters[1L] &&
          metadata$lifecycle$base_children - metadata$lifecycle$excluded_single_incomes == metadata$lifecycle$children,
        "Lifecycle metadata counts disagree.")
  integer_counts(unlist(metadata$lifecycle[c("base_children", "children", "excluded_single_incomes", "origin_family_clusters")]),
                 "lifecycle metadata")
  list(estimates = estimates, contrasts = contrasts, lifecycle = lifecycle,
       lifecycle_averages = lifecycle_averages, lifecycle_contrasts = lifecycle_contrasts,
       coverage = coverage, lifecycle_coverage = lifecycle_coverage, sensitivity = sensitivity,
       flow = flow, waves = waves, metadata = metadata)
}

if (sys.nframe() == 0L) {
  args <- result_arguments(commandArgs(TRUE), script_directory())
  results <- read_aggregate_results(args$output)
  cat("Aggregate checks passed:", nrow(results$estimates), "main estimates,",
      nrow(results$lifecycle), "lifecycle estimates, paired differences, coverage and source audits.\n")
}
